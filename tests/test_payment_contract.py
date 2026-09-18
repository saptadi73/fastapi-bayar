import pytest
from pydantic import ValidationError
from app.schemas.payment import InitiatePaymentRequest, RefundRequest


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
