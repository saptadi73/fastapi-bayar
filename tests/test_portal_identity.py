import asyncio
import os
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import get_settings
from app.core.database import Base
from app.core.errors import AppError
from app.models.payment import Client, PaymentTransaction, Service
from app.models.portal_identity import PortalEvent, PortalUser
from app.schemas.payment import InitiatePaymentRequest
from app.services.payment_service import initiate


def payload(reference="REF", **overrides):
    return dict(service_code="EVENT", reference_id=reference, amount=10000,
                event_id="EVT-1", event_name="Event One",
                customer={"name": "Payer", "email": "Payer@EXAMPLE.com"}, **overrides)


@pytest.mark.parametrize("field,value", [("event_id", None), ("event_id", "  "),
                                       ("event_name", ""), ("event_name", " " * 3)])
def test_event_identity_required(field, value):
    data = payload()
    data[field] = value
    with pytest.raises(ValidationError) as error:
        InitiatePaymentRequest(**data)
    assert any(item["loc"] == (field,) for item in error.value.errors())


def test_email_identity_policy():
    data = payload()
    data["customer"]["email"] = " Payer+Ticket@EXAMPLE.com "
    request = InitiatePaymentRequest(**data)
    assert request.customer.email == "payer+ticket@example.com"


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in PostgreSQL")
@pytest.mark.asyncio
async def test_tenant_identity_multiple_orders_snapshot_and_constraints():
    schema = "test_identity_" + uuid.uuid4().hex
    admin = create_async_engine(get_settings().database_url, poolclass=NullPool)
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool,
                                connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with admin.begin() as conn:
        await conn.execute(CreateSchema(schema))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            clients = [Client(code=code, name=code, api_secret="test") for code in ("ONE", "TWO")]
            db.add_all(clients)
            await db.flush()
            db.add_all([Service(client_id=c.id, code="EVENT", name="Event") for c in clients])
            await db.commit()

        async def create(client, ref, event_name="Event One", email="payer@example.com"):
            data = payload(ref)
            data["event_name"] = event_name
            data["customer"]["email"] = email
            async with sessions() as db:
                return await initiate(db, client, InitiatePaymentRequest(**data), ref)

        results = await asyncio.gather(*(create(clients[0], f"ORDER-{i}") for i in range(4)))
        assert len({r[0]["payment_id"] for r in results}) == 4
        original = results[0][0]
        replay, is_replay = await create(clients[0], "ORDER-0")
        assert is_replay and replay == original
        with pytest.raises(AppError) as conflict:
            await create(clients[0], "ORDER-0", event_name="Changed")
        assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
        second, _ = await create(clients[1], "ORDER-0")
        assert second["client_id"] != original["client_id"]
        await create(clients[0], "RENAME", event_name="Renamed", email="PAYER@EXAMPLE.COM")
        async with sessions() as db:
            assert await db.scalar(select(func.count()).select_from(PortalEvent)) == 2
            assert await db.scalar(select(func.count()).select_from(PortalUser)) == 2
            events = list((await db.scalars(select(PortalEvent))).all())
            users = list((await db.scalars(select(PortalUser))).all())
            old = await db.get(PaymentTransaction, uuid.UUID(original["payment_id"]))
            assert old.event_name == "Event One" and old.customer_email == "payer@example.com"
            assert old.client_name == "ONE"
            assert next(e for e in events if e.client_id == clients[0].id).name == "Renamed"
            foreign_event = next(e for e in events if e.client_id == clients[1].id)
            foreign_user = next(u for u in users if u.client_id == clients[1].id)
            foreign_event_id, foreign_user_id = foreign_event.id, foreign_user.id
        # Composite FKs reject accidental cross-tenant links even outside service code.
        for field, foreign_id in (("event_record_id", foreign_event_id), ("portal_user_id", foreign_user_id)):
            async with sessions() as db:
                row = await db.get(PaymentTransaction, uuid.UUID(original["payment_id"]))
                setattr(row, field, foreign_id)
                with pytest.raises(IntegrityError):
                    await db.commit()
                await db.rollback()
        async with sessions() as db:
            db.add(PortalEvent(client_id=clients[0].id, event_id="EVT-1", name="Duplicate"))
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        async with sessions() as db:
            db.add(PortalUser(client_id=clients[0].id, email="payer@example.com", name="Duplicate"))
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(DropSchema(schema, cascade=True))
        await admin.dispose()
