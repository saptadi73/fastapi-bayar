from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from app.core.errors import AppError
from app.schemas.payment import InitiatePaymentRequest, RefundRequest
from app.services.payment_service import _validate_refund_amount


@pytest.mark.parametrize("amount", [0, -1, True, 100.0, 10.5, "100", 9223372036854775808])
def test_amount_is_strict_positive_bigint(amount):
    with pytest.raises(ValidationError):
        InitiatePaymentRequest(service_code="EVENT", reference_id="REF", event_id="EVT", event_name="Event", amount=amount, customer={"name": "Guest", "email": "guest@example.com"})
    with pytest.raises(ValidationError):
        RefundRequest(amount=amount, reason="Requested")


@pytest.mark.parametrize("overrides", [{"currency": "USD"}, {"expires_at": "2030-01-01T12:00:00"}])
def test_currency_and_timezone_contract(overrides):
    with pytest.raises(ValidationError):
        InitiatePaymentRequest(service_code="EVENT", reference_id="REF", amount=1000,
                               event_id="EVT", event_name="Event",
                               customer={"name": "Guest", "email": "guest@example.com"}, **overrides)


class ScalarDb:
    def __init__(self, value):
        self.value = value

    async def scalar(self, _query):
        return self.value


@pytest.mark.asyncio
async def test_cumulative_refund_cannot_exceed_payment_amount():
    payment = SimpleNamespace(id=uuid4(), amount=1000)

    await _validate_refund_amount(ScalarDb(600), payment, 400)

    with pytest.raises(AppError) as error:
        await _validate_refund_amount(ScalarDb(600), payment, 401)
    assert error.value.code == "REFUND_LIMIT_EXCEEDED"
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_refund_amount_cannot_exceed_payment_even_without_previous_refund():
    payment = SimpleNamespace(id=uuid4(), amount=1000)

    with pytest.raises(AppError) as error:
        await _validate_refund_amount(ScalarDb(0), payment, 1001)
    assert error.value.code == "INVALID_REFUND_AMOUNT"
