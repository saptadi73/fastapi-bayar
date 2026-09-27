import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import AppError
from app.models.payment import PaymentStatus
from app.services.webhook_service import process_doku_notification, process_midtrans_notification, validate_midtrans_event


def notification(**changes):
    value = dict(order_id="test-order", status_code="200", gross_amount="100000.00", currency="IDR", transaction_status="settlement")
    value.update(changes)
    value["signature_key"] = hashlib.sha512((value["order_id"] + value["status_code"] + value["gross_amount"] + "test-key").encode()).hexdigest()
    return value


@pytest.mark.parametrize("changes,code", [
    ({"gross_amount": "99999.99"}, "GATEWAY_AMOUNT_MISMATCH"),
    ({"gross_amount": "NaN"}, "GATEWAY_AMOUNT_MISMATCH"),
    ({"gross_amount": "Infinity"}, "GATEWAY_AMOUNT_MISMATCH"),
    ({"gross_amount": "invalid"}, "INVALID_GATEWAY_AMOUNT"),
    ({"currency": "USD"}, "GATEWAY_CURRENCY_MISMATCH"),
    ({"transaction_status": "capture", "fraud_status": "challenge"}, "GATEWAY_REVIEW_REQUIRED"),
    ({"transaction_status": "capture"}, "GATEWAY_REVIEW_REQUIRED"),
    ({"transaction_status": "success"}, "UNKNOWN_PROVIDER_STATUS"),
])
def test_invalid_provider_facts(changes, code):
    with pytest.raises(AppError) as error:
        validate_midtrans_event(notification(**changes), SimpleNamespace(amount=100000, currency="IDR"))
    assert error.value.code == code


def test_capture_requires_fraud_accept():
    assert validate_midtrans_event(notification(transaction_status="capture", fraud_status="accept"), SimpleNamespace(amount=100000, currency="IDR")) == PaymentStatus.PAID


@pytest.mark.asyncio
async def test_invalid_signature_never_enters_deduplication():
    db = AsyncMock()
    payload = notification()
    payload["signature_key"] = "invalid"
    with patch("app.services.webhook_service.get_settings", return_value=SimpleNamespace(midtrans_server_key="test-key")):
        for _ in range(2):
            with pytest.raises(AppError) as error:
                await process_midtrans_notification(db, "test", payload, b"invalid")
            assert error.value.status_code == 401
    db.scalar.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status", ["settlement", "pending"])
async def test_paid_payment_does_not_emit_second_callback(provider_status):
    payment = SimpleNamespace(id=uuid.uuid4(), amount=100000, currency="IDR", status=PaymentStatus.PAID, winning_attempt_id=None)
    attempt = SimpleNamespace(id=uuid.uuid4(), payment_id=payment.id, status="PAID")
    events = []
    db = AsyncMock()
    db.add = events.append
    db.scalar.side_effect = [None, attempt, payment]
    with patch("app.services.webhook_service.get_settings", return_value=SimpleNamespace(midtrans_server_key="test-key")), patch("app.services.webhook_service.enqueue_payment_callback", new_callable=AsyncMock) as callback:
        result = await process_midtrans_notification(db, "test", notification(transaction_status=provider_status), b"signed-test")
    assert result["status"] == "IGNORED"
    assert payment.status == PaymentStatus.PAID
    if provider_status == "settlement":
        assert payment.winning_attempt_id == attempt.id
    assert events[0].processing_status == "IGNORED"
    assert "signature_key" not in events[0].payload
    callback.assert_not_awaited()
    db.commit.assert_awaited_once()


def doku_notification(status: str) -> dict:
    return {
        "order": {"invoice_number": "DOKU-ORDER-1", "amount": "100000"},
        "transaction": {"status": status},
    }


@pytest.mark.asyncio
async def test_doku_duplicate_delivery_is_idempotent():
    duplicate = SimpleNamespace(id=uuid.uuid4(), processing_status="PROCESSED")
    db = AsyncMock()
    db.scalar.return_value = duplicate

    result = await process_doku_notification(
        db,
        "merchant-1",
        doku_notification("SUCCESS"),
        b"same-body",
        {},
        "/api/v1/webhooks/doku/merchant-1",
        trusted_provider_response=True,
    )

    assert result["duplicate"] is True
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status", ["PENDING", "FAILED"])
async def test_doku_out_of_order_or_late_event_is_quarantined(provider_status):
    payment = SimpleNamespace(id=uuid.uuid4(), amount=100000, currency="IDR", status=PaymentStatus.PAID)
    attempt = SimpleNamespace(payment_id=payment.id, status="PAID")
    event = []
    db = AsyncMock()
    db.scalar.side_effect = [None, attempt, payment]
    db.add = event.append

    with pytest.raises(AppError) as error:
        await process_doku_notification(
            db,
            "merchant-1",
            doku_notification(provider_status),
            provider_status.encode(),
            {},
            "/api/v1/webhooks/doku/merchant-1",
            trusted_provider_response=True,
        )

    assert error.value.code == "LATE_STATUS_REVIEW_REQUIRED"
    assert event[0].processing_status == "QUARANTINED"
    db.commit.assert_awaited_once()
