import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import get_settings
from app.core.database import Base
from app.models.payment import CallbackDelivery, CheckoutSession, Client, PaymentTransaction, Service, PaymentAttempt, ReconciliationCase
from app.services import worker_service
from app.services.callback_service import callback_signature, deliver_pending_callbacks
from app.services.maintenance_service import cleanup_expired_checkouts


@pytest.mark.asyncio
async def test_periodic_recovers_without_logging_secrets(caplog):
    stop = asyncio.Event()
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("secret-must-not-appear")
        stop.set()
        return {"done": 1}

    await worker_service.periodic_job("test", operation, 0.001, stop)
    assert calls == 2
    assert "RuntimeError" in caplog.text
    assert "secret-must-not-appear" not in caplog.text


@pytest.mark.asyncio
async def test_stop_does_not_start_another_job():
    stop = asyncio.Event()
    stop.set()
    operation = AsyncMock()
    await worker_service.periodic_job("test", operation, 100, stop)
    operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_once_selects_jobs_and_propagates_failure(monkeypatch):
    callback = AsyncMock(return_value={"succeeded": 0})
    cleanup = AsyncMock(side_effect=RuntimeError("failure"))
    monkeypatch.setattr(worker_service, "callback_tick", callback)
    monkeypatch.setattr(worker_service, "cleanup_tick", cleanup)
    with pytest.raises(RuntimeError):
        await worker_service.run_worker(asyncio.Event(), jobs="cleanup", once=True)
    callback.assert_not_awaited()
    cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_rejects_unbounded_batch():
    with pytest.raises(ValueError):
        await cleanup_expired_checkouts(AsyncMock(), 10001)


@pytest_asyncio.fixture
async def worker_db():
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Opt-in local PostgreSQL")
    schema = "test_worker_" + uuid.uuid4().hex
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
            client = Client(code="WORKER", name="Worker", api_secret="legacy", callback_secret="callback-test",
                            callback_url="https://event.example/callback",
                            allowed_callback_urls=["https://event.example/callback"])
            db.add(client)
            await db.flush()
            service = Service(client_id=client.id, code="EVENT", name="Event")
            db.add(service)
            await db.flush()
            payment = PaymentTransaction(payment_no="WORKER-PAY", client_id=client.id,
                                         service_id=service.id, external_reference="REF", amount=100,
                                         customer_name="Guest")
            db.add(payment)
            await db.commit()
            payment_id, client_id = payment.id, client.id
        yield sessions, payment_id, client_id
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(DropSchema(schema, cascade=True))
        await admin.dispose()


async def add_delivery(sessions, payment_id, **kwargs):
    async with sessions() as db:
        delivery = CallbackDelivery(payment_id=payment_id, event_type="payment.paid",
                                    callback_url="https://event.example/callback",
                                    payload={"amount": 100}, **kwargs)
        db.add(delivery)
        await db.commit()
        return delivery.id


def mock_http(monkeypatch, handler):
    factory = httpx.AsyncClient
    monkeypatch.setattr("app.services.callback_service.httpx.AsyncClient",
                        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.asyncio
async def test_two_workers_do_not_send_same_delivery(worker_db, monkeypatch):
    sessions, payment_id, _ = worker_db
    ids = [await add_delivery(sessions, payment_id) for _ in range(2)]
    sent = []
    both_sending = asyncio.Event()

    async def handler(request):
        sent.append(request.headers["X-Event-ID"])
        assert request.headers["X-Signature"] == callback_signature(
            {"amount": 100}, "callback-test", request.headers["X-Timestamp"])
        if len(sent) == 2:
            both_sending.set()
        # Both rows belong to one payment/client. Locks must not block the second worker.
        await asyncio.wait_for(both_sending.wait(), timeout=5)
        return httpx.Response(204)

    mock_http(monkeypatch, handler)

    async def run():
        async with sessions() as db:
            return await deliver_pending_callbacks(db, limit=1)

    results = await asyncio.gather(run(), run())
    assert sum(row["succeeded"] for row in results) == 2
    assert len(set(sent)) == 2
    async with sessions() as db:
        rows = list((await db.scalars(select(CallbackDelivery).where(CallbackDelivery.id.in_(ids)))).all())
        assert all(row.status == "SUCCEEDED" and row.attempt_no == 1 for row in rows)


@pytest.mark.asyncio
async def test_retry_due_time_and_attempt_cap(worker_db, monkeypatch):
    sessions, payment_id, _ = worker_db
    delivery_id = await add_delivery(sessions, payment_id)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503)

    mock_http(monkeypatch, handler)
    async with sessions() as db:
        result = await deliver_pending_callbacks(db)
        assert result["retry"] == 1
        row = await db.get(CallbackDelivery, delivery_id)
        assert row.status == "RETRY" and row.next_retry_at > datetime.now(timezone.utc)
    async with sessions() as db:
        assert not any((await deliver_pending_callbacks(db)).values())
        row = await db.get(CallbackDelivery, delivery_id)
        row.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        row.attempt_no = get_settings().callback_max_attempts - 1
        await db.commit()
    async with sessions() as db:
        assert (await deliver_pending_callbacks(db))["dead_letter"] == 1
        assert (await db.get(CallbackDelivery, delivery_id)).status == "DEAD_LETTER"
    assert len(requests) == 2
    assert requests[0].headers["X-Event-ID"] == requests[1].headers["X-Event-ID"]


@pytest.mark.asyncio
async def test_inactive_client_is_not_contacted(worker_db, monkeypatch):
    sessions, payment_id, client_id = worker_db
    await add_delivery(sessions, payment_id)
    async with sessions() as db:
        (await db.get(Client, client_id)).active = False
        await db.commit()

    def handler(request):
        pytest.fail("Inactive client must not receive network calls")

    mock_http(monkeypatch, handler)
    async with sessions() as db:
        assert (await deliver_pending_callbacks(db))["dead_letter"] == 1


@pytest.mark.asyncio
async def test_cleanup_bounded_preserves_active_and_ledger(worker_db):
    sessions, payment_id, _ = worker_db
    now = datetime.now(timezone.utc)
    async with sessions() as db:
        for i in range(4):
            db.add(CheckoutSession(payment_id=payment_id,
                                   token_hash=hashlib.sha256(str(i).encode()).hexdigest(),
                                   expires_at=now + timedelta(hours=1 if i == 3 else -1)))
        await db.commit()
    async with sessions() as db:
        assert await cleanup_expired_checkouts(db, 2) == {"expired_checkouts_deleted": 2}
    async with sessions() as db:
        assert await cleanup_expired_checkouts(db, 2) == {"expired_checkouts_deleted": 1}
        assert await db.scalar(select(func.count()).select_from(CheckoutSession)) == 1
        assert await db.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
        assert await cleanup_expired_checkouts(db) == {"expired_checkouts_deleted": 0}


@pytest.mark.asyncio
async def test_worker_commits_previous_event_before_later_failure(worker_db, monkeypatch):
    sessions, payment_id, _ = worker_db
    first = await add_delivery(sessions, payment_id)
    second = await add_delivery(sessions, payment_id)
    monkeypatch.setattr(worker_service, "SessionLocal", sessions)
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Simulated process failure")
        return httpx.Response(200)

    mock_http(monkeypatch, handler)
    with pytest.raises(RuntimeError):
        await worker_service.callback_tick()
    async with sessions() as db:
        assert (await db.get(CallbackDelivery, first)).status == "SUCCEEDED"
        row = await db.get(CallbackDelivery, second)
        assert row.status == "PENDING" and row.attempt_no == 0


@pytest.mark.asyncio
async def test_network_timeout_schedules_retry(worker_db, monkeypatch):
    sessions, payment_id, _ = worker_db
    delivery_id = await add_delivery(sessions, payment_id)

    def handler(request):
        raise httpx.ReadTimeout("simulated timeout", request=request)

    mock_http(monkeypatch, handler)
    async with sessions() as db:
        assert (await deliver_pending_callbacks(db))["retry"] == 1
        row = await db.get(CallbackDelivery, delivery_id)
        assert row.status == "RETRY" and row.attempt_no == 1


@pytest.mark.asyncio
async def test_reconciliation_worker_claims_once_and_records_result(worker_db, monkeypatch):
    sessions, payment_id, _ = worker_db
    async with sessions() as db:
        attempt = PaymentAttempt(payment_id=payment_id, attempt_no=1, gateway="MIDTRANS",
                                 channel_code="MIDTRANS_SNAP", gateway_order_id="RECON-ORDER", status="UNKNOWN")
        db.add(attempt)
        await db.flush()
        case = ReconciliationCase(attempt_id=attempt.id, reason="Worker test")
        db.add(case)
        await db.commit()
        case_id, attempt_id = case.id, attempt.id
    monkeypatch.setattr(worker_service, "SessionLocal", sessions)
    monkeypatch.setattr("app.services.reconciliation_worker_service.SessionLocal", sessions)
    monkeypatch.setattr("app.services.reconciliation_worker_service.get_settings",
                        lambda: get_settings().model_copy(update={"worker_reconciliation_batch_size": 10}))

    async def inquiry(db, wanted_attempt, adapter):
        assert wanted_attempt == attempt_id
        return {"attempt_id": str(attempt_id), "status": "UNRESOLVED"}

    monkeypatch.setattr("app.services.reconciliation_worker_service.reconcile_attempt", inquiry)
    result = await worker_service.reconciliation_tick()
    assert result == {"claimed": 1, "completed": 1, "failed": 0}
    async with sessions() as db:
        saved = await db.get(ReconciliationCase, case_id)
        assert saved.status == "COMPLETED" and saved.result_status == "UNRESOLVED"
    assert (await worker_service.reconciliation_tick()) == {"claimed": 0, "completed": 0, "failed": 0}


@pytest.mark.asyncio
async def test_reconciliation_worker_marks_provider_error(worker_db, monkeypatch):
    sessions, payment_id, _ = worker_db
    async with sessions() as db:
        attempt = PaymentAttempt(payment_id=payment_id, attempt_no=1, gateway="MIDTRANS",
                                 channel_code="MIDTRANS_SNAP", gateway_order_id="RECON-ERROR", status="UNKNOWN")
        db.add(attempt)
        await db.flush()
        case = ReconciliationCase(attempt_id=attempt.id, reason="Worker error test")
        db.add(case)
        await db.commit()
        case_id = case.id
    monkeypatch.setattr(worker_service, "SessionLocal", sessions)
    monkeypatch.setattr("app.services.reconciliation_worker_service.SessionLocal", sessions)
    monkeypatch.setattr("app.services.reconciliation_worker_service.get_settings",
                        lambda: get_settings().model_copy(update={"worker_reconciliation_batch_size": 10}))
    from app.core.errors import AppError
    async def inquiry(db, attempt_id, adapter):
        raise AppError("GATEWAY_INQUIRY_FAILED", "provider failed", 502)
    monkeypatch.setattr("app.services.reconciliation_worker_service.reconcile_attempt", inquiry)
    assert (await worker_service.reconciliation_tick()) == {"claimed": 1, "completed": 0, "failed": 1}
    async with sessions() as db:
        saved = await db.get(ReconciliationCase, case_id)
        assert saved.status == "FAILED" and saved.error_code == "GATEWAY_INQUIRY_FAILED"
