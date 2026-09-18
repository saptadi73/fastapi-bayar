import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.admin_security import COOKIE_NAME, digest, csrf_for
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.models.admin import AdminSession, AdminUser
from app.models.payment import Client, Service, PaymentTransaction, PaymentAttempt, PaymentStatusHistory
from app.models.payment import ReconciliationCase


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in PostgreSQL")
@pytest.mark.asyncio
async def test_admin_ledger_filters_permissions_pagination_and_redaction(monkeypatch):
    schema = "test_admin_ledger_" + uuid.uuid4().hex
    admin = create_async_engine(get_settings().database_url, poolclass=NullPool)
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool,
                                connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = get_settings().model_copy(update={"admin_enabled": True, "public_base_url": "http://test"})
    monkeypatch.setattr("app.api.v1.admin.get_settings", lambda: settings)
    previous = app.dependency_overrides.copy()

    async def test_db():
        async with sessions() as db:
            yield db

    async with admin.begin() as conn:
        await conn.execute(CreateSchema(schema))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        now = datetime.now(timezone.utc)
        token = "a" * 43
        async with sessions() as db:
            operator = AdminUser(email="finance@example.com", display_name="Finance", role="FINANCE", password_hash="unused")
            db.add(operator)
            await db.flush()
            operator_id = operator.id
            db.add(AdminSession(token_hash=digest(token), user_id=operator.id, last_seen_at=now,
                                expires_at=now + timedelta(hours=1)))
            payments = []
            for i in range(2):
                client = Client(code=f"CLIENT-{i}", name="Portal", api_secret="hidden-credential")
                db.add(client)
                await db.flush()
                svc = Service(client_id=client.id, code="EVENT", name="Event")
                db.add(svc)
                await db.flush()
                payment = PaymentTransaction(client_id=client.id, service_id=svc.id, payment_no=f"PAY-{i}",
                    external_reference="SAME-REF", event_id="EVT-1", event_name="Event Snapshot",
                    amount=1000, customer_name="private-name", customer_email="private@example.com",
                    metadata_json={"private": "sensitive-metadata"}, return_url="https://private.example/result",
                    created_at=now + timedelta(seconds=i))
                db.add(payment)
                await db.flush()
                payments.append(payment)
                for n in range(2):
                    db.add(PaymentAttempt(payment_id=payment.id, attempt_no=n+1, gateway="MIDTRANS",
                        channel_code="MIDTRANS_SNAP", gateway_order_id=f"ORDER-{i}-{n}",
                        instructions={"token": "hidden-checkout-token"}))
                    db.add(PaymentStatusHistory(payment_id=payment.id, from_status=None, to_status="CREATED",
                        source="API", reason="sensitive-reason", occurred_at=now + timedelta(seconds=n)))
            await db.commit()
        app.dependency_overrides[get_db] = test_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
            base = "/api/v1/admin/payments"
            assert (await api.get(base)).status_code == 401
            api.cookies.set(COOKIE_NAME, token, path="/api/v1/admin")
            all_rows = await api.get(base)
            assert all_rows.status_code == 200 and len(all_rows.json()["data"]) == 2
            first = (await api.get(base, params={"limit": 1})).json()
            second = (await api.get(base, params={"limit": 1, "offset": 1})).json()
            assert first["meta"]["has_more"] and not second["meta"]["has_more"]
            assert first["data"][0]["id"] != second["data"][0]["id"]
            assert (await api.get(base, params={"event_id": "EVT-1"})).status_code == 422
            filtered = await api.get(base, params={"client_id": str(payments[0].client_id), "event_id": "EVT-1",
                                                  "service_id": str(payments[0].service_id), "status": "CREATED"})
            assert [r["id"] for r in filtered.json()["data"]] == [str(payments[0].id)]
            assert (await api.get(base, params={"status": "PAID"})).json()["data"] == []
            assert (await api.get(base, params={"reference_id": "MISSING"})).json()["data"] == []
            date_rows = await api.get(base, params={"created_from": now.isoformat(),
                                                   "created_to": (now + timedelta(seconds=1)).isoformat()})
            assert len(date_rows.json()["data"]) == 1
            for params in ({"created_from": "2026-01-01T12:00:00"}, {"status": "UNKNOWN-STATUS"},
                           {"limit": 101}, {"offset": -1},
                           {"created_from": now.isoformat(), "created_to": now.isoformat()}):
                assert (await api.get(base, params=params)).status_code == 422
            item = base + "/" + str(payments[0].id)
            for suffix in ("", "/history", "/attempts"):
                response = await api.get(item + suffix)
                assert response.status_code == 200
                for secret in ("private@example.com", "private-name", "sensitive-metadata", "hidden-checkout-token",
                               "hidden-credential", "sensitive-reason", "private.example"):
                    assert secret not in response.text
                assert (await api.get(base + "/" + str(uuid.uuid4()) + suffix)).status_code == 404
            assert (await api.get(item + "/attempts", params={"limit": 1})).json()["meta"]["has_more"]
            assert (await api.get(item + "/history", params={"limit": 1})).json()["meta"]["has_more"]
            reconciliation = "/api/v1/admin/reconciliation"
            assert (await api.get(reconciliation)).status_code == 200
            attempt_id = (await api.get(item + "/attempts")).json()["data"][0]["id"]
            assert (await api.post(f"{reconciliation}/{attempt_id}/request", headers={"X-CSRF-Token": "bad"},
                                   json={"reason": "Inspect timeout"})).status_code == 403
            requested = await api.post(f"{reconciliation}/{attempt_id}/request", headers={"Origin": "http://test", "X-CSRF-Token": csrf_for(token)},
                                       json={"reason": "Inspect timeout"})
            assert requested.status_code == 202 and requested.json()["data"]["status"] == "REQUESTED"
            repeated = await api.post(f"{reconciliation}/{attempt_id}/request", headers={"Origin": "http://test", "X-CSRF-Token": csrf_for(token)},
                                      json={"reason": "Repeated request"})
            assert repeated.status_code == 202 and repeated.json()["data"]["status"] == "REQUESTED"
            assert (await api.get(reconciliation)).json()["meta"]["has_more"] is False
            # State remains queued; provider inquiry is intentionally outside the HTTP request.
            async with sessions() as db:
                operator.role = "FINANCE"
                await db.commit()
            assert (await api.get(reconciliation)).status_code == 200
            # API mutation requires the configured Origin in production deployment.
            for role, expected in (("INTEGRATION_ADMIN", 403), ("AUDITOR", 200), ("SUPER_ADMIN", 200)):
                async with sessions() as db:
                    (await db.get(AdminUser, operator_id)).role = role
                    await db.commit()
                assert (await api.get(item)).status_code == expected
                assert (await api.get(item + "/history")).status_code == expected
                assert (await api.get(item + "/attempts")).status_code == expected
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(DropSchema(schema, cascade=True))
        await admin.dispose()
