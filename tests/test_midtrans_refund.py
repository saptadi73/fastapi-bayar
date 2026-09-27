import httpx
import json
import pytest
from unittest.mock import patch

from app.core.config import Settings
from app.gateways.midtrans.client import MidtransSnapClient


@pytest.mark.asyncio
async def test_midtrans_refund_uses_deterministic_key_and_accepts_partial_refund():
    seen = {}

    async def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(200, json={"status_code": "200", "transaction_status": "partial_refund",
                                         "refund_key": "RFD-1", "refund_amount": "5000"})

    real_client = httpx.AsyncClient
    with patch("app.gateways.midtrans.client.httpx.AsyncClient",
               side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
        result = await MidtransSnapClient(Settings(midtrans_server_key="test")).refund(
            order_id="ORDER-1", refund_key="RFD-1", amount=5000, reason="duplicate order")

    assert result["transaction_status"] == "partial_refund"
    assert seen["url"].endswith("/v2/ORDER-1/refund")
    payload = json.loads(seen["body"])
    assert payload["refund_key"] == "RFD-1"
    assert payload["amount"] == 5000
    assert payload["reason"] == "duplicate order"
