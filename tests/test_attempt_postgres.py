"""Opt-in real PostgreSQL test, using a disposable, uniquely named schema.

PowerShell: $env:RUN_POSTGRES_TESTS='1'; python -m pytest tests/test_attempt_postgres.py -q
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import get_settings
from app.core.database import Base
from app.core.errors import AppError
from app.gateways.base import GatewayResult
from app.models.payment import Client, PaymentAttempt, PaymentStatus, PaymentTransaction, Service
from app.services.attempt_service import create_attempt
from app.services.payment_service import cancel_owned_payment, initiate
from app.schemas.payment import InitiatePaymentRequest
from app.api.dependencies import legacy_hmac_dependency as client_dependency
from app.core.security import build_canonical, sign
from starlette.requests import Request


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requires opt-in local PostgreSQL")
@pytest.mark.asyncio
async def test_durable_attempt_concurrency_timeout_and_early_webhook():
    schema = "test_attempt_" + uuid.uuid4().hex
    admin = create_async_engine(get_settings().database_url, poolclass=NullPool)
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool,
                                connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with admin.begin() as connection:
        await connection.execute(CreateSchema(schema))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            client = Client(code="TEST", name="Test", api_secret="test")
            db.add(client)
            await db.flush()
            service = Service(client_id=client.id, code="EVENT", name="Test")
            db.add(service)
            await db.flush()
            payments = [PaymentTransaction(client_id=client.id, service_id=service.id,
                         payment_no=f"TEST-{i}", external_reference=f"TEST-{i}", amount=100000,
                         currency="IDR", status=PaymentStatus.CREATED, customer_name="Test",
                         customer_email="test@example.com", metadata_json={}) for i in range(3)]
            db.add_all(payments)
            await db.commit()
            ids = [p.id for p in payments]

        # New orders require event and payer identity; replay preserves the snapshot.
        async with sessions() as db:
            request = InitiatePaymentRequest(service_code="EVENT", reference_id="NO-EMAIL", amount=100000,
                                            event_id="EVT-1", event_name="Event One",
                                            customer={"name": "Guest", "email": "guest@example.com"})
            result, replay = await initiate(db, client, request, "no-email")
            assert not replay
            stored = await db.get(PaymentTransaction, uuid.UUID(result["payment_id"]))
            assert stored.customer_email == "guest@example.com"
            assert stored.event_id == "EVT-1"
            again, replay = await initiate(db, client, request, "no-email")
            assert replay and again == result

        async def concurrent_initiate(reference, key, amount=100000):
            async with sessions() as db:
                request = InitiatePaymentRequest(service_code="EVENT", reference_id=reference,
                                                event_id="EVT-1", event_name="Event One",
                                                amount=amount, customer={"name": "Guest", "email": "guest@example.com"})
                try:
                    return await initiate(db, client, request, key)
                except AppError as error:
                    return error.code

        same = await asyncio.wait_for(asyncio.gather(*[
            concurrent_initiate("PARALLEL-SAME", "parallel-same") for _ in range(8)
        ]), timeout=15)
        assert len({result[0]["payment_id"] for result in same}) == 1
        assert sum(not result[1] for result in same) == 1
        collision = await asyncio.gather(
            concurrent_initiate("PARALLEL-REFERENCE", "ref-a"),
            concurrent_initiate("PARALLEL-REFERENCE", "ref-b"),
        )
        assert sum(result == "DUPLICATE_REFERENCE" for result in collision) == 1
        conflict = await asyncio.gather(
            concurrent_initiate("PARALLEL-KEY", "same-key", 100000),
            concurrent_initiate("PARALLEL-KEY", "same-key", 200000),
        )
        assert sum(result == "IDEMPOTENCY_CONFLICT" for result in conflict) == 1

        # Real PostgreSQL nonce uniqueness: exactly one concurrent request authenticates.
        stamp = datetime.now(timezone.utc).isoformat()
        raw_path = b"/api/v1/client/payments"
        async def authenticate(nonce, key="key-2026-01", body=b"{}", signed_body=b"{}"):
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            scope = {"type": "http", "method": "POST", "path": raw_path.decode(),
                     "raw_path": raw_path, "query_string": b"q=a%20b", "headers": []}
            signature = sign(build_canonical("POST", raw_path.decode() + "?q=a%20b", "TEST", key, stamp, nonce, signed_body), "test")
            async with sessions() as db:
                try:
                    owner = await client_dependency(Request(scope, receive), db, "TEST", key, stamp, nonce, signature)
                    return str(owner.id)
                except AppError as error:
                    return error.code

        with patch("app.api.dependencies.get_settings", return_value=SimpleNamespace(auth_enabled=True, nonce_ttl_seconds=600)):
            authenticated = await asyncio.gather(*[authenticate("shared-nonce") for _ in range(4)])
            assert authenticated.count(str(client.id)) == 1
            assert authenticated.count("REPLAY_DETECTED") == 3
            assert await authenticate("wrong-key", key="unregistered") == "INVALID_SIGNATURE"
            assert await authenticate("body-change", body=b'{"changed":true}') == "INVALID_SIGNATURE"
            # A rejected signature must not consume the legitimate nonce.
            assert await authenticate("body-change") == str(client.id)

        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def provider(**kwargs):
            calls.append(kwargs["order_id"])
            # Independent connection proves the reservation was committed before network I/O.
            async with sessions() as observer:
                reserved = await observer.scalar(select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == kwargs["order_id"]))
                assert reserved.status == "INITIATED"
            started.set()
            await release.wait()
            return GatewayResult("MIDTRANS", kwargs["order_id"], "PENDING", instructions={"token": "test"})

        async def run(payment_id):
            async with sessions() as db:
                p = await db.get(PaymentTransaction, payment_id)
                return await create_attempt(db, p, "MIDTRANS_SNAP")

        adapter = SimpleNamespace(name="MIDTRANS", create_payment=provider)
        with patch("app.services.attempt_service.client_for_channel", return_value=adapter):
            task = asyncio.create_task(run(ids[0]))
            try:
                await asyncio.wait_for(started.wait(), timeout=10)
                with pytest.raises(AppError) as error:
                    await run(ids[0])
                assert error.value.code == "ATTEMPT_IN_PROGRESS"
                async with sessions() as db:
                    with pytest.raises(AppError) as error:
                        await cancel_owned_payment(db, client, ids[0])
                    assert error.value.code == "PROVIDER_CANCEL_REQUIRED"
            finally:
                release.set()
                first = await task
            repeated = await run(ids[0])
            assert repeated.id == first.id
            assert len(calls) == 1

        async def timeout(**kwargs):
            raise httpx.ReadTimeout("test timeout")

        adapter.create_payment = timeout
        with patch("app.services.attempt_service.client_for_channel", return_value=adapter):
            with pytest.raises(AppError) as error:
                await run(ids[1])
            assert error.value.code == "GATEWAY_OUTCOME_UNKNOWN"
            with pytest.raises(AppError) as error:
                await run(ids[1])
            assert error.value.code == "ATTEMPT_IN_PROGRESS"
            async with sessions() as db:
                attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_id == ids[1]))
                assert attempt.status == "UNKNOWN"

        async def early_paid(**kwargs):
            async with sessions() as db:
                attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.gateway_order_id == kwargs["order_id"]))
                payment = await db.get(PaymentTransaction, attempt.payment_id)
                payment.status, attempt.status = PaymentStatus.PAID, "PAID"
                await db.commit()
            return GatewayResult("MIDTRANS", kwargs["order_id"], "PENDING", instructions={"token": "test"})

        adapter.create_payment = early_paid
        with patch("app.services.attempt_service.client_for_channel", return_value=adapter):
            attempt = await run(ids[2])
            assert attempt.status == "PAID"
        async with sessions() as db:
            assert (await db.get(PaymentTransaction, ids[2])).status == PaymentStatus.PAID
    finally:
        await engine.dispose()
        # Only this test's UUID-named schema is removed, never application tables.
        async with admin.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await admin.dispose()
