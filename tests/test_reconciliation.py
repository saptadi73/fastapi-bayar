from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.gateways.midtrans.client import MidtransSnapClient
from app.services.reconciliation_service import reconcile_attempt


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status,payload,expected", [
    (404, {}, None), (200, {"status_code": "404"}, None),
    (200, {"order_id": "OTHER"}, "GATEWAY_ORDER_MISMATCH"),
    (401, {}, "GATEWAY_INQUIRY_FAILED"),
    (200, [], "INVALID_GATEWAY_RESPONSE"),
    (200, {"order_id": "ORDER", "transaction_status": "pending"}, "pending"),
])
async def test_inquiry_transport(http_status, payload, expected):
    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == "https://api.sandbox.midtrans.com/v2/ORDER/status"
        assert request.headers["Authorization"] == "Basic dGVzdDo="
        return httpx.Response(http_status, json=payload)
    real_client = httpx.AsyncClient
    with patch("app.gateways.midtrans.client.httpx.AsyncClient", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
        adapter = MidtransSnapClient(Settings(midtrans_server_key="test", midtrans_environment="SANDBOX"))
        if expected and expected.startswith(("GATEWAY", "INVALID")):
            with pytest.raises(AppError) as error:
                await adapter.get_status("ORDER")
            assert error.value.code == expected
        else:
            result = await adapter.get_status("ORDER")
            assert (result.get("transaction_status") if result else None) == expected


@pytest.mark.asyncio
async def test_not_found_does_not_mutate_ledger():
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(gateway="MIDTRANS", gateway_order_id="ORDER")
    adapter = SimpleNamespace(get_status=AsyncMock(return_value=None))
    with patch("app.services.reconciliation_service.apply_midtrans_event", new_callable=AsyncMock) as apply:
        result = await reconcile_attempt(db, uuid4(), adapter)
    assert result["status"] == "UNRESOLVED"
    apply.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_inquiry_uses_shared_ledger_processor():
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(gateway="MIDTRANS", gateway_order_id="ORDER")
    payload = {"order_id": "ORDER", "gross_amount": "100000.00", "transaction_status": "settlement"}
    adapter = SimpleNamespace(get_status=AsyncMock(return_value=payload))
    with patch("app.services.reconciliation_service.apply_midtrans_event", new_callable=AsyncMock, return_value={"status": "PAID"}) as apply:
        result = await reconcile_attempt(db, uuid4(), adapter)
    assert result["status"] == "PAID"
    assert apply.call_args.kwargs["source"] == "RECONCILIATION"
