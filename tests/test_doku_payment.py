import httpx
import pytest
from unittest.mock import patch

from app.core.config import Settings
from app.gateways.doku.client import DokuDirectClient


@pytest.mark.asyncio
async def test_doku_indomaret_payment_code_contract():
    seen = {}

    async def handler(request):
        seen["request"] = request
        return httpx.Response(200, json={"order": {"invoice_number": "PAY-1"},
            "online_to_offline_info": {"payment_code": "88888888", "how_to_pay_page": "https://doku.example/how"}})

    real_client = httpx.AsyncClient
    with patch("app.gateways.doku.client.httpx.AsyncClient",
               side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
        result = await DokuDirectClient(Settings(doku_client_id="client", doku_secret_key="secret")).create_payment(
            order_id="PAY-1", amount=10000, currency="IDR", customer={"name": "Buyer"}, channel_code="DOKU_INDOMARET")

    assert result.status == "PENDING"
    assert result.instructions["payment_code"] == "88888888"
    assert seen["request"].headers["Signature"].startswith("HMACSHA256=")
