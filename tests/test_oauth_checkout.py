import base64
import hashlib
import os
import time
import uuid

import httpx
import pytest
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.access import decode_access_token, hash_secret, issue_access_token, verify_secret
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.errors import AppError
from app.models.payment import CheckoutSession, Client, PaymentAttempt, PaymentTransaction, Service
from app.main import app


def test_secret_storage_and_verification():
    encoded = hash_secret("test-secret")
    assert "test-secret" not in encoded
    assert verify_secret("test-secret", encoded)
    assert not verify_secret("wrong", encoded)


@pytest.mark.parametrize("change", ["expiry", "audience", "issuer", "kind", "signature", "scope"])
def test_jwt_rejects_invalid_claims(change):
    settings = get_settings()
    from types import SimpleNamespace
    token = issue_access_token(SimpleNamespace(id=uuid.uuid4(), token_version=1), {"payments:read"})
    claims = jwt.get_unverified_claims(token)
    if change == "expiry": claims["exp"] = int(time.time()) - 30
    if change == "audience": claims["aud"] = "other"
    if change == "issuer": claims["iss"] = "other"
    if change == "kind": claims["kind"] = "checkout"
    if change == "scope": claims["scope"] = None
    key = "x" * 96 if change == "signature" else settings.jwt_secret
    altered = jwt.encode(claims, key, algorithm="HS256")
    with pytest.raises(AppError) as error:
        decode_access_token(altered)
    assert error.value.status_code == 401


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in local PostgreSQL")
@pytest.mark.asyncio
async def test_oauth_checkout_tenant_isolation_and_revocation():
    schema = "test_oauth_" + uuid.uuid4().hex
    admin = create_async_engine(get_settings().database_url, poolclass=NullPool)
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool,
                                connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    previous = app.dependency_overrides.copy()

    async def test_db():
        async with sessions() as db:
            yield db

    async with admin.begin() as conn:
        await conn.execute(CreateSchema(schema))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            clients = []
            for code in ("ONE", "TWO"):
                client = Client(code=code, name=code, api_secret="legacy",
                                oauth_secret_hash=hash_secret("test-secret"),
                                allowed_return_urls=["https://event.example.com/result"],
                                allowed_callback_urls=[], callback_url=None)
                db.add(client)
                await db.flush()
                db.add(Service(client_id=client.id, code="EVENT", name="Event"))
                clients.append(client)
            await db.commit()
            one_id = clients[0].id
        app.dependency_overrides[get_db] = test_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
            async def token(code, scope="payments:read payments:write", secret="test-secret"):
                encoded = base64.b64encode(f"{code}:{secret}".encode()).decode()
                return await api.post("/api/v1/oauth/token", data={"grant_type": "client_credentials", "scope": scope},
                                      headers={"Authorization": "Basic " + encoded})
            assert (await token("ONE", secret="wrong")).status_code == 401
            assert (await token("MISSING")).status_code == 401
            assert (await token("ONE", scope="payments:refund")).status_code == 400
            issued = await token("ONE")
            assert issued.status_code == 200 and issued.headers["cache-control"] == "no-store"
            access = issued.json()["access_token"]
            two_access = (await token("TWO")).json()["access_token"]
            readonly = (await token("ONE", "payments:read")).json()["access_token"]
            headers = {"Authorization": "Bearer " + access, "Idempotency-Key": "create-one"}
            payload = {"service_code": "EVENT", "reference_id": "ORDER-1", "amount": 100000,
                       "event_id": "EVT-1", "event_name": "Event One",
                       "customer": {"name": "Guest", "email": "guest@example.com"}, "return_url": "https://event.example.com/result"}
            assert (await api.post("/api/v1/client/payments", headers={"X-Client-ID": "ONE", "Idempotency-Key": "x"}, json=payload)).status_code == 401
            assert (await api.post("/api/v1/client/payments", headers={"Authorization": "Bearer " + readonly, "Idempotency-Key": "x"}, json=payload)).status_code == 403
            bad = dict(payload, return_url="https://evil.example/result")
            assert (await api.post("/api/v1/client/payments", headers=headers, json=bad)).status_code == 422
            created = await api.post("/api/v1/client/payments", headers=headers, json=payload)
            assert created.status_code == 201, created.text
            result = created.json()["data"]
            payment_id, number = result["payment_id"], result["payment_no"]
            checkout = result["checkout_token"]
            assert "#token=" in result["payment_url"] and "?" not in result["payment_url"]
            replay = await api.post("/api/v1/client/payments", headers=headers, json=payload)
            assert replay.json()["meta"]["idempotent_replay"]
            assert replay.json()["data"]["payment_id"] == payment_id
            assert (await api.get("/api/v1/client/payments/" + payment_id, headers={"Authorization": "Bearer " + two_access})).status_code == 404
            public = "/api/v1/public/payments/" + number
            assert (await api.get(public)).status_code == 401
            assert (await api.get(public, headers={"Authorization": "Bearer " + access})).status_code == 401
            assert (await api.get("/api/v1/client/payments/" + payment_id, headers={"Authorization": "Bearer " + checkout})).status_code == 401
            checkout_headers = {"Authorization": "Bearer " + checkout}
            second = await api.post("/api/v1/client/payments", headers={"Authorization": "Bearer " + two_access, "Idempotency-Key": "two"}, json=payload)
            assert second.status_code == 201
            second_payment = second.json()["data"]
            async with sessions() as db:
                own_attempt = PaymentAttempt(payment_id=uuid.UUID(payment_id), attempt_no=1, gateway="MIDTRANS", channel_code="MIDTRANS_SNAP", gateway_order_id="OWN", status="PENDING", instructions={"token": "own"})
                foreign_attempt = PaymentAttempt(payment_id=uuid.UUID(second_payment["payment_id"]), attempt_no=1, gateway="MIDTRANS", channel_code="MIDTRANS_SNAP", gateway_order_id="FOREIGN", status="PENDING", instructions={"token": "foreign"})
                db.add_all([own_attempt, foreign_attempt])
                await db.commit()
            assert (await api.get("/api/v1/public/attempts/" + str(own_attempt.id) + "/instructions", headers=checkout_headers)).status_code == 200
            assert (await api.get("/api/v1/public/attempts/" + str(foreign_attempt.id) + "/instructions", headers=checkout_headers)).status_code == 404
            assert (await api.get("/api/v1/public/attempts/" + str(own_attempt.id) + "/instructions")).status_code == 401
            assert (await api.get("/api/v1/public/payments/" + second_payment["payment_no"], headers=checkout_headers)).status_code == 404
            assert (await api.get(public, headers=checkout_headers)).status_code == 200
            assert (await api.get("/api/v1/public/payments/OTHER", headers=checkout_headers)).status_code == 404
            assert (await api.get(public + "/channels", headers=checkout_headers)).status_code == 200
            assert (await api.post(public + "/attempts", json={"channel_code": "MIDTRANS_SNAP"})).status_code == 401
            async with sessions() as db:
                row = await db.scalar(select(CheckoutSession).where(CheckoutSession.token_hash == hashlib.sha256(checkout.encode()).hexdigest()))
                assert row and row.token_hash != checkout
                from datetime import datetime, timedelta, timezone
                row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await db.commit()
            assert (await api.get(public, headers=checkout_headers)).status_code == 401
            fresh = await api.post("/api/v1/client/payments/" + payment_id + "/checkout", headers=headers)
            assert fresh.status_code == 200
            async with sessions() as db:
                owner = await db.get(Client, one_id)
                owner.token_version += 1
                await db.commit()
            assert (await api.get("/api/v1/client/payments/" + payment_id, headers=headers)).status_code == 401
            new_access = (await token("ONE")).json()["access_token"]
            async with sessions() as db:
                owner = await db.get(Client, one_id)
                owner.active = False
                await db.commit()
            assert (await token("ONE")).status_code == 401
            assert (await api.get("/api/v1/client/payments/" + payment_id, headers={"Authorization": "Bearer " + new_access})).status_code == 401
            assert (await api.get(public, headers={"Authorization": "Bearer " + fresh.json()["data"]["checkout_token"]})).status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(DropSchema(schema, cascade=True))
        await admin.dispose()
