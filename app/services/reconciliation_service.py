import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.gateways.midtrans.client import MidtransSnapClient
from app.gateways.doku.client import DokuDirectClient
from app.models.payment import PaymentAttempt
from app.services.webhook_service import apply_midtrans_event, process_doku_notification


async def reconcile_attempt(db: AsyncSession, attempt_id: UUID, adapter) -> dict:
    attempt = await db.get(PaymentAttempt, attempt_id)
    if not attempt or attempt.gateway not in {"MIDTRANS", "DOKU"}:
        raise AppError("ATTEMPT_NOT_FOUND", "Payment attempt provider tidak ditemukan", 404)
    order_id = attempt.gateway_order_id
    await db.rollback()  # release read transaction before provider network request
    payload = await adapter.get_status(order_id)
    if payload is None:
        return {"attempt_id": str(attempt_id), "status": "UNRESOLVED", "reason": "PROVIDER_NOT_FOUND"}
    # Defense in depth for injected adapters and future transports.
    if attempt.gateway == "MIDTRANS" and payload.get("order_id") != order_id:
        raise AppError("GATEWAY_ORDER_MISMATCH", "Order inquiry berbeda", 502)
    if attempt.gateway == "DOKU" and (payload.get("order") or {}).get("invoice_number") != order_id:
        raise AppError("GATEWAY_ORDER_MISMATCH", "Invoice inquiry berbeda", 502)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if attempt.gateway == "DOKU":
        return await process_doku_notification(db, "configured-doku", payload, raw, {}, "/api/v1/webhooks/doku/configured-doku", trusted_provider_response=True)
    return await apply_midtrans_event(db, "configured-midtrans", payload, raw, source="RECONCILIATION")
