from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class GatewayResult:
    gateway: str
    gateway_order_id: str
    status: str
    payment_url: str | None = None
    instructions: dict[str, Any] | None = None


class PaymentGateway(Protocol):
    name: str

    async def create_payment(self, *, order_id: str, amount: int, currency: str, customer: dict[str, Any], channel_code: str) -> GatewayResult: ...

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool: ...

