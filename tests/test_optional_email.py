import json
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.gateways.midtrans.client import MidtransSnapClient
from app.schemas.common import CustomerInput


def test_api_invalid_email_returns_standard_error():
    from fastapi.testclient import TestClient
    from app.api.dependencies import client_dependency
    from app.core.database import get_db
    from app.main import app

    async def no_database():
        yield None

    async def test_client():
        return object()

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = no_database
    app.dependency_overrides[client_dependency] = test_client
    try:
        response = TestClient(app).post("/api/v1/client/payments", headers={"Idempotency-Key": "test-invalid-email"}, json={
            "service_code": "EVENT", "reference_id": "BAD-EMAIL", "amount": 1000,
            "customer": {"name": "Guest", "email": "invalid"},
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert any(item["loc"] == ["body", "customer", "email"] for item in response.json()["error"]["details"])
        customer = app.openapi()["components"]["schemas"]["CustomerInput"]
        assert "email" in customer["required"]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("data", [{}, {"email": None}, {"email": ""}, {"email": "  "}])
def test_identity_email_required(data):
    with pytest.raises(ValidationError):
        CustomerInput(name="Guest", **data)


def test_valid_email_trimmed():
    assert CustomerInput(name="Guest", email=" user@example.com ").email == "user@example.com"


@pytest.mark.parametrize("value", ["not-an-email", "user@", 123, [], {}])
def test_invalid_email_rejected(value):
    with pytest.raises(ValidationError):
        CustomerInput(name="Guest", email=value)


@pytest.mark.asyncio
@pytest.mark.parametrize("email", [None, "", "  ", "user@example.com"])
async def test_snap_payload_omits_absent_email(email):
    def handler(request):
        details = json.loads(request.content)["customer_details"]
        if email and email.strip():
            assert details["email"] == email
        else:
            assert "email" not in details
        return httpx.Response(201, json={"token": "test", "redirect_url": "https://app.sandbox.midtrans.com/snap/test"})
    real_client = httpx.AsyncClient
    with patch("app.gateways.midtrans.client.httpx.AsyncClient", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
        adapter = MidtransSnapClient(Settings(midtrans_server_key="test"))
        await adapter.create_payment(order_id="TEST", amount=100000, currency="IDR", customer={"name": "Guest", "email": email}, channel_code="MIDTRANS_SNAP")
