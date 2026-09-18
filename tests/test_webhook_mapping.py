import pytest

from app.core.errors import AppError
from app.services.webhook_service import normalize_provider_status


def test_provider_status_is_normalized():
    assert normalize_provider_status("settlement") == "PAID"
    assert normalize_provider_status("partial_refund") == "PARTIALLY_REFUNDED"


def test_unknown_provider_status_is_rejected():
    with pytest.raises(AppError):
        normalize_provider_status("some-new-provider-status")
