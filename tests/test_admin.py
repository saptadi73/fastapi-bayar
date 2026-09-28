import os
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.admin_security import COOKIE_NAME, digest, hash_password, verify_password
from app.core.config import Settings, get_settings
from app.core.database import Base, get_db
from app.main import app
from app.models.admin import AdminAudit, AdminSession, AdminUser
from scripts import bootstrap_admin
from app.core.errors import AppError
from app.schemas.admin_user import UpdateAdminUser
from app.services.admin_user_service import update_user


def test_admin_password_hash():
    password = "long-admin-password!"
    encoded = hash_password(password)
    assert password not in encoded
    assert verify_password(password, encoded)
    assert not verify_password("wrong", encoded)
    assert encoded != hash_password(password)
    with pytest.raises(ValueError):
        hash_password("short")


def test_admin_disabled_in_production_until_mfa():
    settings = Settings(_env_file=None, environment="production", admin_enabled=True)
    with pytest.raises(ValueError, match="development-only"):
        settings.validate_production()


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in PostgreSQL")
@pytest.mark.asyncio
async def test_admin_sessions_permissions_csrf_rate_limit_and_isolation(monkeypatch):
    schema = "test_admin_" + uuid.uuid4().hex
    admin_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool,
                                connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = get_settings().model_copy(update={"admin_enabled": True, "admin_login_limit": 30,
                                                "public_base_url": "https://admin.test"})
    monkeypatch.setattr("app.api.v1.admin.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.admin_service.get_settings", lambda: settings)
    previous = app.dependency_overrides.copy()

    async def test_db():
        async with sessions() as db:
            yield db

    async with admin_engine.begin() as conn:
        await conn.execute(CreateSchema(schema))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        monkeypatch.setattr(bootstrap_admin, "SessionLocal", sessions)
        user_id = await bootstrap_admin.bootstrap("ADMIN@example.com", "Admin", "long-admin-password!")
        with pytest.raises(ValueError, match="sudah ada"):
            await bootstrap_admin.bootstrap("other@example.com", "Other", "different-long-password!")
        app.dependency_overrides[get_db] = test_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://admin.test") as api:
            body = {"identifier": "admin@example.com", "password": "long-admin-password!"}
            origin = {"Origin": "https://admin.test"}
            assert (await api.get("/api/v1/admin/auth/me", headers={"Authorization": "Bearer fake-client-token"})).status_code == 401
            assert (await api.post("/api/v1/admin/auth/login", json=body)).status_code == 403
            invalid = await api.post("/api/v1/admin/auth/login", headers=origin,
                                     json=dict(body, password="x" * 129))
            assert invalid.status_code == 422 and "x" * 129 not in invalid.text
            failed = await api.post("/api/v1/admin/auth/login", headers=origin, json=dict(body, password="wrong"))
            assert failed.status_code == 401
            issued = await api.post("/api/v1/admin/auth/login", headers=origin, json=body)
            assert issued.status_code == 200
            cookie_header = issued.headers["set-cookie"].lower()
            assert "httponly" in cookie_header and "secure" in cookie_header and "samesite=lax" in cookie_header
            token = api.cookies.get(COOKIE_NAME)
            csrf = issued.json()["data"]["csrf_token"]
            async with sessions() as db:
                saved = await db.get(AdminSession, digest(token))
                assert saved and saved.token_hash != token
            me = await api.get("/api/v1/admin/auth/me")
            assert me.status_code == 200 and "admin.users.read" in me.json()["data"]["permissions"]
            listing = await api.get("/api/v1/admin/users")
            assert listing.status_code == 200
            assert "password_hash" not in listing.text and body["password"] not in listing.text
            assert (await api.get("/api/v1/admin/roles")).status_code == 200
            assert (await api.get("/api/v1/admin/audit")).status_code == 200
            mutate = {**origin, "X-CSRF-Token": csrf}
            last = await api.patch(f"/api/v1/admin/users/{user_id}", headers=mutate,
                                   json={"display_name": "Admin", "role": "AUDITOR", "active": True,
                                         "expected_version": 1, "reason": "Test last admin"})
            assert last.status_code == 409 and last.json()["error"]["code"] == "LAST_SUPER_ADMIN"
            create_user = {"email": "SECOND@example.com", "display_name": "Second", "role": "AUDITOR",
                           "active": True, "password": "second-admin-password!", "reason": "New operator"}
            assert (await api.post("/api/v1/admin/users", headers=origin, json=create_user)).status_code == 403
            bad_password = await api.post("/api/v1/admin/users", headers=mutate, json={**create_user, "password": "Ab9?Zk"})
            assert bad_password.status_code == 422 and "Ab9?Zk" not in bad_password.text
            second_user = await api.post("/api/v1/admin/users", headers=mutate, json=create_user)
            assert second_user.status_code == 201
            assert "password_hash" not in second_user.text and create_user["password"] not in second_user.text
            other_id = second_user.json()["data"]["id"]
            assert second_user.json()["data"]["email"] == "second@example.com"
            assert second_user.json()["data"]["force_password_change"] is True
            assert (await api.post("/api/v1/admin/users", headers=mutate, json=create_user)).status_code == 409
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://admin.test") as other:
                credentials = {"identifier": "second@example.com", "password": create_user["password"]}
                login_other = await other.post("/api/v1/admin/auth/login", headers=origin, json=credentials)
                assert login_other.status_code == 200
                denied = await other.post("/api/v1/admin/users", json=create_user,
                                          headers={**origin, "X-CSRF-Token": login_other.json()["data"]["csrf_token"]})
                assert denied.status_code == 403
                assert denied.json()["error"]["code"] == "ADMIN_PASSWORD_CHANGE_REQUIRED"
                changed_password = await other.post("/api/v1/admin/users/password-change", headers={
                    **origin, "X-CSRF-Token": login_other.json()["data"]["csrf_token"],
                }, json={"current_password": create_user["password"],
                         "new_password": "replacement-admin-password!", "reason": "Initial sign-in"})
                assert changed_password.status_code == 200
                assert (await other.get("/api/v1/admin/auth/me")).json()["data"]["user"]["force_password_change"] is False
                credentials["password"] = "replacement-admin-password!"
                change = {"display_name": "Second", "role": "INTEGRATION_ADMIN", "active": True,
                          "expected_version": 2, "reason": "Change responsibilities"}
                changed = await api.patch(f"/api/v1/admin/users/{other_id}", headers=mutate, json=change)
                assert changed.status_code == 200 and changed.json()["data"]["version"] == 3
                assert (await other.get("/api/v1/admin/auth/me")).status_code == 401
                assert (await other.post("/api/v1/admin/auth/login", headers=origin, json=credentials)).status_code == 200
                revoked = await api.post(f"/api/v1/admin/users/{other_id}/revoke-sessions", headers=mutate,
                                         json={"expected_version": 3, "reason": "Revoke devices"})
                assert revoked.status_code == 200 and revoked.json()["data"]["version"] == 4
                assert (await other.get("/api/v1/admin/auth/me")).status_code == 401
                results = await asyncio.gather(*[
                    api.patch(f"/api/v1/admin/users/{other_id}", headers=mutate,
                              json={**change, "active": False, "expected_version": 4}) for _ in range(2)
                ])
                assert sorted(r.status_code for r in results) == [200, 409]
                assert (await other.post("/api/v1/admin/auth/login", headers=origin, json=credentials)).status_code == 401
            configuration = {"name": "Portal Event", "active": True,
                             "scopes": ["payments:read", "payments:write"],
                             "allowed_return_urls": ["https://event.example/result"],
                             "allowed_callback_urls": ["https://event.example/callback"],
                             "callback_url": "https://event.example/callback", "reason": "Onboarding"}
            create_body = {**configuration, "code": "EVENT-ADMIN", "service_code": "EVENT"}
            mutate = {**origin, "X-CSRF-Token": csrf}
            assert (await api.post("/api/v1/admin/clients", headers=origin, json=create_body)).status_code == 403
            bad = {**create_body, "callback_url": "https://unregistered.example/callback"}
            assert (await api.post("/api/v1/admin/clients", headers=mutate, json=bad)).status_code == 422
            created = await api.post("/api/v1/admin/clients", headers=mutate, json=create_body)
            assert created.status_code == 201
            record = created.json()["data"]
            client_id, initial_secret = record["id"], record["client_secret"]
            assert created.headers["cache-control"] == "no-store"
            service_base = f"/api/v1/admin/clients/{client_id}/services"
            service_body = {"code": "TICKET", "name": "Ticket Sales", "active": True, "reason": "Additional service"}
            assert (await api.post(service_base, headers=origin, json=service_body)).status_code == 403
            service_created = await api.post(service_base, headers=mutate, json=service_body)
            assert service_created.status_code == 201
            service_id = service_created.json()["data"]["id"]
            assert service_created.json()["data"]["version"] == 1
            assert (await api.post(service_base, headers=mutate, json=service_body)).status_code == 409
            service_list = await api.get(service_base)
            assert {r["code"] for r in service_list.json()["data"]} == {"EVENT", "TICKET"}
            second_client = await api.post("/api/v1/admin/clients", headers=mutate,
                                           json={**create_body, "code": "SECOND-PORTAL"})
            other_client_id = second_client.json()["data"]["id"]
            foreign_base = f"/api/v1/admin/clients/{other_client_id}/services"
            assert (await api.post(foreign_base, headers=mutate, json=service_body)).status_code == 201
            assert (await api.get(foreign_base + "/" + service_id)).status_code == 404
            update_service = {"name": "Ticket Paused", "active": False, "reason": "Maintenance", "expected_version": 1}
            assert (await api.patch(foreign_base + "/" + service_id, headers=mutate, json=update_service)).status_code == 404
            service_updates = await asyncio.gather(*[
                api.patch(service_base + "/" + service_id, headers=mutate, json=update_service) for _ in range(2)
            ])
            assert sorted(r.status_code for r in service_updates) == [200, 409]
            service_detail = (await api.get(service_base + "/" + service_id)).json()["data"]
            assert service_detail["version"] == 2 and service_detail["active"] is False
            assert (await api.post("/api/v1/admin/clients", headers=mutate, json=create_body)).status_code == 409
            detail = await api.get("/api/v1/admin/clients/" + client_id)
            listing = await api.get("/api/v1/admin/clients")
            for result in (detail, listing):
                assert result.status_code == 200 and initial_secret not in result.text
                assert record["callback_secret"] not in result.text
                records = result.json()["data"]
                records = records if isinstance(records, list) else [records]
                assert all(not {"client_secret", "callback_secret", "oauth_secret_hash", "api_secret"} & item.keys()
                           for item in records)
            issued_client = await api.post("/api/v1/oauth/token", auth=("EVENT-ADMIN", initial_secret),
                                          data={"grant_type": "client_credentials"})
            assert issued_client.status_code == 200
            old_jwt = issued_client.json()["access_token"]
            disabled_service_order = await api.post("/api/v1/client/payments",
                headers={"Authorization": "Bearer " + old_jwt, "Idempotency-Key": "disabled-service"},
                json={"service_code": "TICKET", "reference_id": "ORDER-DISABLED", "event_id": "EVT-1",
                      "event_name": "Event", "amount": 1000,
                      "customer": {"name": "Guest", "email": "guest@example.com"}})
            assert disabled_service_order.status_code == 404
            assert disabled_service_order.json()["error"]["code"] == "SERVICE_NOT_FOUND"
            rotated = await api.post(f"/api/v1/admin/clients/{client_id}/rotate-secret", headers=mutate,
                                     json={"expected_version": 1, "reason": "Rotation"})
            assert rotated.status_code == 200
            assert "callback_secret" not in rotated.json()["data"]
            assert rotated.json()["data"]["version"] == 2
            assert (await api.post(f"/api/v1/admin/clients/{client_id}/rotate-secret", headers=mutate,
                                  json={"expected_version": 1, "reason": "Stale retry"})).status_code == 409
            assert (await api.post("/api/v1/oauth/token", auth=("EVENT-ADMIN", initial_secret),
                                  data={"grant_type": "client_credentials"})).status_code == 401
            assert (await api.get("/api/v1/client/payments/" + str(uuid.uuid4()),
                                 headers={"Authorization": "Bearer " + old_jwt})).status_code == 401
            parallel = await asyncio.gather(*[
                api.patch(f"/api/v1/admin/clients/{client_id}", headers=mutate,
                          json={**configuration, "active": False, "expected_version": 2}) for _ in range(2)
            ])
            assert sorted(result.status_code for result in parallel) == [200, 409]
            updated = next(result for result in parallel if result.status_code == 200)
            assert updated.status_code == 200 and updated.json()["data"]["version"] == 3
            assert (await api.patch(f"/api/v1/admin/clients/{client_id}", headers=mutate,
                                   json={**configuration, "expected_version": 2})).status_code == 409
            assert (await api.post("/api/v1/oauth/token", auth=("EVENT-ADMIN", rotated.json()["data"]["client_secret"]),
                                  data={"grant_type": "client_credentials"})).status_code == 401
            audit_response = await api.get("/api/v1/admin/audit")
            assert initial_secret not in audit_response.text and record["callback_secret"] not in audit_response.text
            assert {"CLIENT_CREATED", "CLIENT_UPDATED", "CLIENT_SECRET_ROTATED"} <= {r["action"] for r in audit_response.json()["data"]}
            assert {"SERVICE_CREATED", "SERVICE_UPDATED"} <= {r["action"] for r in audit_response.json()["data"]}
            assert (await api.get("/api/v1/client/payments/" + str(uuid.uuid4()), headers={"Authorization": "Bearer " + token})).status_code == 401
            assert (await api.post("/api/v1/admin/auth/logout", headers=origin)).status_code == 403
            assert (await api.post("/api/v1/admin/auth/logout", headers={"Origin": "https://evil.test", "X-CSRF-Token": csrf})).status_code == 403
            async with sessions() as db:
                (await db.get(AdminUser, user_id)).role = "AUDITOR"
                await db.commit()
            assert (await api.get("/api/v1/admin/users")).status_code == 403
            assert (await api.get("/api/v1/admin/clients")).status_code == 200
            assert (await api.post("/api/v1/admin/clients", headers=mutate, json=create_body)).status_code == 403
            assert (await api.get(service_base)).status_code == 200
            assert (await api.post(service_base, headers=mutate, json=service_body)).status_code == 403
            assert (await api.get("/api/v1/admin/audit")).status_code == 200
            assert (await api.post("/api/v1/admin/auth/logout", headers={**origin, "X-CSRF-Token": csrf})).status_code == 200
            api.cookies.set(COOKIE_NAME, token, path="/api/v1/admin")
            assert (await api.get("/api/v1/admin/auth/me")).status_code == 401
            api.cookies.clear()
            issued = await api.post("/api/v1/admin/auth/login", headers=origin, json=body)
            token = api.cookies.get(COOKIE_NAME)
            async with sessions() as db:
                (await db.get(AdminSession, digest(token))).last_seen_at = datetime.now(timezone.utc) - timedelta(days=1)
                await db.commit()
            assert (await api.get("/api/v1/admin/auth/me")).status_code == 401
            await api.post("/api/v1/admin/auth/login", headers=origin, json=body)
            async with sessions() as db:
                (await db.get(AdminUser, user_id)).active = False
                await db.commit()
            assert (await api.get("/api/v1/admin/auth/me")).status_code == 401
            assert (await api.post("/api/v1/admin/auth/login", headers=origin, json=body)).status_code == 401
            settings.admin_login_limit = 1
            limited = await api.post("/api/v1/admin/auth/login", headers=origin, json=body)
            assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
            async with sessions() as db:
                actions = list((await db.scalars(select(AdminAudit.action))).all())
                assert "LOGIN_FAILED" in actions and "LOGIN_SUCCEEDED" in actions and "LOGOUT" in actions
            settings.admin_enabled = False
            assert (await api.get("/api/v1/admin/auth/me")).status_code == 503
        # Two active Super Admins concurrently demote themselves: one must survive.
        async with sessions() as db:
            roots = [AdminUser(email=f"race-{i}@example.com", display_name="Race",
                               password_hash="unused-test-only", role="SUPER_ADMIN") for i in range(2)]
            db.add_all(roots)
            await db.flush()
            for i, root in enumerate(roots):
                db.add(AdminSession(token_hash=digest(f"race-session-{i}"), user_id=root.id,
                                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                                    last_seen_at=datetime.now(timezone.utc)))
            await db.commit()

        async def demote(i):
            async with sessions() as db:
                try:
                    await update_user(db, roots[i].id, digest(f"race-session-{i}"), roots[i].id,
                                      UpdateAdminUser(display_name="Race", role="AUDITOR", active=True,
                                                      expected_version=1, reason="Concurrent self-demotion"))
                    return "updated"
                except AppError as exc:
                    return exc.code
        results = await asyncio.wait_for(asyncio.gather(demote(0), demote(1)), timeout=10)
        assert sorted(results) == ["LAST_SUPER_ADMIN", "updated"]
        async with sessions() as db:
            count = await db.scalar(select(func.count()).select_from(AdminUser).where(
                AdminUser.active.is_(True), AdminUser.role == "SUPER_ADMIN"))
            assert count == 1
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        await engine.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(DropSchema(schema, cascade=True))
        await admin_engine.dispose()
