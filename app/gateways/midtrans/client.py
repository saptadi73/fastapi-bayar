import base64
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import AppError
from app.gateways.base import GatewayResult


class MidtransSnapClient:
    name = "MIDTRANS"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.midtrans_production_base_url if settings.midtrans_environment.upper() == "PRODUCTION" else settings.midtrans_sandbox_base_url

    def _auth_header(self) -> str:
        if not self.settings.midtrans_server_key:
            raise AppError("GATEWAY_NOT_CONFIGURED", "MIDTRANS_SERVER_KEY belum dikonfigurasi", 503)
        token = base64.b64encode(f"{self.settings.midtrans_server_key}:".encode()).decode()
        return f"Basic {token}"

    async def create_payment(self, *, order_id: str, amount: int, currency: str, customer: dict[str, Any], channel_code: str) -> GatewayResult:
        if channel_code.upper() != "MIDTRANS_SNAP":
            raise AppError("UNSUPPORTED_CHANNEL", "Midtrans adapter hanya menerima MIDTRANS_SNAP", 422)
        customer_details = {"first_name": customer.get("name", ""), "phone": customer.get("phone", "")}
        email = customer.get("email")
        if email and email.strip():
            customer_details["email"] = email.strip()
        payload = {"transaction_details": {"order_id": order_id, "gross_amount": amount}, "customer_details": customer_details}
        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": self._auth_header()}
        async with httpx.AsyncClient(timeout=self.settings.gateway_timeout_seconds) as client:
            response = await client.post(f"{self.base_url.rstrip('/')}/snap/v1/transactions", json=payload, headers=headers)
        if response.status_code >= 400:
            raise AppError("GATEWAY_CREATE_FAILED", "Midtrans menolak pembuatan transaksi", 502, {"provider_status": response.status_code})
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("token"), str) or not data["token"] or not isinstance(data.get("redirect_url"), str) or not data["redirect_url"].startswith("https://"):
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response Snap tidak lengkap", 502)
        return GatewayResult(gateway=self.name, gateway_order_id=order_id, status="PENDING", payment_url=data.get("redirect_url"), instructions={"token": data.get("token"), "redirect_url": data.get("redirect_url")})

    async def get_status(self, order_id: str) -> dict | None:
        base = self.settings.midtrans_core_production_base_url if self.settings.midtrans_environment.upper() == "PRODUCTION" else self.settings.midtrans_core_sandbox_base_url
        headers = {"Accept": "application/json", "Authorization": self._auth_header()}
        async with httpx.AsyncClient(timeout=self.settings.gateway_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = await client.get(f"{base.rstrip('/')}/v2/{quote(order_id, safe='')}/status", headers=headers)
        if response.status_code == 404:
            return None  # Snap may not yet have a selected payment method.
        if response.status_code != 200:
            raise AppError("GATEWAY_INQUIRY_FAILED", "Status inquiry provider gagal", 502)
        try:
            data = response.json()
        except ValueError:
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response inquiry bukan JSON", 502)
        if not isinstance(data, dict):
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response inquiry bukan object", 502)
        if str(data.get("status_code")) == "404":
            return None
        if data.get("order_id") != order_id:
            raise AppError("GATEWAY_ORDER_MISMATCH", "Order inquiry berbeda dari request", 502)
        return data

    async def refund(self, *, order_id: str, refund_key: str, amount: int, reason: str) -> dict:
        """Submit an idempotent Core API refund request.

        The caller must reconcile the returned transaction status before marking
        the internal refund as completed; a successful HTTP response is not the
        same as confirmed funds returned to the customer.
        """
        base = self.settings.midtrans_core_production_base_url if self.settings.midtrans_environment.upper() == "PRODUCTION" else self.settings.midtrans_core_sandbox_base_url
        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": self._auth_header()}
        payload = {"refund_key": refund_key, "amount": amount, "reason": reason[:255]}
        async with httpx.AsyncClient(timeout=self.settings.gateway_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = await client.post(f"{base.rstrip('/')}/v2/{quote(order_id, safe='')}/refund", json=payload, headers=headers)
        try:
            data = response.json()
        except ValueError:
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response refund bukan JSON", 502)
        if not isinstance(data, dict):
            raise AppError("INVALID_GATEWAY_RESPONSE", "Response refund bukan object", 502)
        if response.status_code >= 400:
            raise AppError("GATEWAY_REFUND_FAILED", "Provider menolak refund", 502, {"provider_status": response.status_code})
        if str(data.get("status_code")) != "200" or data.get("transaction_status") not in {"refund", "partial_refund"}:
            raise AppError("GATEWAY_REFUND_UNRESOLVED", "Provider belum mengonfirmasi refund", 502)
        return data
