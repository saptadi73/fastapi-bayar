import httpx
import pytest
from unittest.mock import patch

from app.core.config import Settings
from app.gateways.doku.client import DokuDirectClient


@pytest.mark.asyncio
async def test_doku_check_status_signs_get_request_without_digest():
    seen = {}

    async def handler(request):
        seen["request"] = request
        return httpx.Response(200, json={"order": {"invoice_number": "INV-1", "amount": 1000},
                                         "transaction": {"status": "SUCCESS"}})

    real_client = httpx.AsyncClient
    with patch("app.gateways.doku.client.httpx.AsyncClient",
               side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
        result = await DokuDirectClient(Settings(doku_client_id="client", doku_secret_key="secret")).get_status("INV-1")

    assert result["transaction"]["status"] == "SUCCESS"
    assert str(seen["request"].url).endswith("/orders/v1/status/INV-1")
    assert seen["request"].headers["Signature"].startswith("HMACSHA256=")
    assert "Digest" not in seen["request"].headers
