import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import AppError
from app.gateways.base import GatewayResult


class DokuDirectClient:
    """DOKU product-specific adapter boundary.

    Direct API payload and signature differ by activated DOKU product/channel;
    do not send a generic request until merchant configuration is selected.
    """

    name = "DOKU"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.doku_production_base_url if settings.doku_environment.upper() == "PRODUCTION" else settings.doku_sandbox_base_url

    def _signature(self, request_id: str, timestamp: str, target: str) -> str:
        if not self.settings.doku_client_id or not self.settings.doku_secret_key:
            raise AppError("GATEWAY_NOT_CONFIGURED", "DOKU_CLIENT_ID/DOKU_SECRET_KEY belum dikonfigurasi", 503)
        component = f"Client-Id:{self.settings.doku_client_id}\nRequest-Id:{request_id}\nRequest-Timestamp:{timestamp}\nRequest-Target:{target}"
        encoded = base64.b64encode(hmac.new(self.settings.doku_secret_key.encode(), component.encode(), hashlib.sha256).digest()).decode()
        return f"HMACSHA256={encoded}"

    async def get_status(self, invoice_number: str) -> dict | None:
        if not invoice_number or len(invoice_number) > 128:
            raise AppError("INVALID_GATEWAY_ORDER", "Invoice DOKU tidak valid", 422)
        target = f"/orders/v1/status/{quote(invoice_number, safe='')}"
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        headers = {"Client-Id": self.settings.doku_client_id, "Request-Id": request_id,
                   "Request-Timestamp": timestamp, "Signature": self._signature(request_id, timestamp, target),
                   "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self.settings.gateway_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = await client.get(f"{self.base_url.rstrip('/')}{target}", headers=headers)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise AppError("GATEWAY_INQUIRY_FAILED", "Status inquiry DOKU gagal", 502, {"provider_status": response.status_code})
        try:
            data = response.json()
        except ValueError:
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response inquiry DOKU bukan JSON", 502)
        if not isinstance(data, dict):
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response inquiry DOKU bukan object", 502)
        actual = (data.get("order") or {}).get("invoice_number")
        if actual and actual != invoice_number:
            raise AppError("GATEWAY_ORDER_MISMATCH", "Invoice inquiry DOKU berbeda dari request", 502)
        return data

    async def create_payment(self, *, order_id: str, amount: int, currency: str, customer: dict, channel_code: str) -> GatewayResult:
        if channel_code.upper() != "DOKU_INDOMARET":
            raise AppError("UNSUPPORTED_CHANNEL", "DOKU adapter saat ini hanya mendukung DOKU_INDOMARET", 422)
        if currency != "IDR" or amount <= 0 or amount > 999999999999:
            raise AppError("UNSUPPORTED_AMOUNT", "DOKU Indomaret hanya mendukung nominal IDR yang valid", 422)
        target = "/indomaret-online-to-offline/v2/payment-code"
        request_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        name = str(customer.get("name") or "Customer")[:64]
        body = {"order": {"invoice_number": order_id, "amount": amount},
                "online_to_offline_info": {"expired_time": 60, "reusable_status": False, "info": "Payment Portal"},
                "customer": {"name": name},
                "indomaret_info": {"receipt": {"description": "Payment Portal"}}}
        if customer.get("email"):
            body["customer"]["email"] = str(customer["email"])[:128]
        import json
        digest = base64.b64encode(hashlib.sha256(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()).digest()).decode()
        component = f"Client-Id:{self.settings.doku_client_id}\nRequest-Id:{request_id}\nRequest-Timestamp:{timestamp}\nRequest-Target:{target}\nDigest:{digest}"
        signature = "HMACSHA256=" + base64.b64encode(hmac.new(self.settings.doku_secret_key.encode(), component.encode(), hashlib.sha256).digest()).decode()
        headers = {"Client-Id": self.settings.doku_client_id, "Request-Id": request_id, "Request-Timestamp": timestamp,
                   "Signature": signature, "Content-Type": "application/json", "Accept": "application/json"}
        serialized_body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        async with httpx.AsyncClient(timeout=self.settings.gateway_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = await client.post(f"{self.base_url.rstrip('/')}{target}", content=serialized_body.encode(), headers=headers)
        if response.status_code >= 400:
            raise AppError("GATEWAY_CREATE_FAILED", "DOKU menolak pembuatan payment code", 502, {"provider_status": response.status_code})
        try:
            data = response.json()
        except ValueError:
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response create DOKU bukan JSON", 502)
        code = ((data.get("online_to_offline_info") or {}).get("payment_code")) if isinstance(data, dict) else None
        invoice = ((data.get("order") or {}).get("invoice_number")) if isinstance(data, dict) else None
        if invoice != order_id or not isinstance(code, str) or not code:
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response payment code DOKU tidak lengkap", 502)
        info = data["online_to_offline_info"]
        return GatewayResult(gateway=self.name, gateway_order_id=order_id, status="PENDING",
                             instructions={"payment_code": code, "how_to_pay_page": info.get("how_to_pay_page"),
                                           "how_to_pay_api": info.get("how_to_pay_api"), "expired_date_utc": info.get("expired_date_utc")})
