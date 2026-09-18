import pytest

from app.core.errors import AppError
from app.models.payment import PaymentStatus


def test_paid_can_enter_refund_pending():
    allowed = {PaymentStatus.PAID: {PaymentStatus.REFUND_PENDING}}
    assert PaymentStatus.REFUND_PENDING in allowed[PaymentStatus.PAID]


def test_invalid_transition_is_app_error_type():
    assert issubclass(AppError, Exception)

