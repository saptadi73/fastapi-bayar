import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.gateways.midtrans.verifier import verify_legacy_notification
from app.gateways.doku.client import DokuDirectClient
from app.models.payment import Client, PaymentAttempt, PaymentStatus, PaymentTransaction, WebhookEvent
from app.services.callback_service import enqueue_payment_callback
from app.services.payment_service import transition


STATUS_MAP = {
    "capture": "PAID",
    "settlement": "PAID",
    "success": "PAID",
    "paid": "PAID",
    "pending": "PENDING",
    "deny": "FAILED",
    "failed": "FAILED",
    "cancel": "CANCELLED",
    "cancelled": "CANCELLED",
    "expire": "EXPIRED",
    "expired": "EXPIRED",
    "refund": "REFUNDED",
    "partial_refund": "PARTIALLY_REFUNDED",
}


def normalize_provider_status(provider_status: str) -> str:
    normalized = STATUS_MAP.get(provider_status.strip().lower())
    if not normalized:
        raise AppError("UNKNOWN_PROVIDER_STATUS", "Status provider belum memiliki mapping", 422, {"provider_status": provider_status})
    return normalized


def validate_midtrans_event(payload: dict, payment: PaymentTransaction) -> PaymentStatus:
    try:
        amount = Decimal(str(payload.get("gross_amount", "")))
    except InvalidOperation:
        raise AppError("INVALID_GATEWAY_AMOUNT", "Nominal provider tidak valid", 422)
    if not amount.is_finite() or amount != Decimal(payment.amount):
        raise AppError("GATEWAY_AMOUNT_MISMATCH", "Nominal provider berbeda dari ledger", 409)
    if payload.get("currency", "IDR") != payment.currency:
        raise AppError("GATEWAY_CURRENCY_MISMATCH", "Currency provider berbeda dari ledger", 409)
    status = payload.get("transaction_status")
    if status == "capture" and payload.get("fraud_status") != "accept":
        raise AppError("GATEWAY_REVIEW_REQUIRED", "Capture belum lolos pemeriksaan fraud", 409)
    if status not in {"capture", "settlement", "pending", "deny", "cancel", "expire", "refund", "partial_refund"}:
        raise AppError("UNKNOWN_PROVIDER_STATUS", "Status Midtrans belum didukung", 422)
    return PaymentStatus(normalize_provider_status(status))


async def process_midtrans_notification(db: AsyncSession, merchant_code: str, payload: dict[str, Any], raw_body: bytes) -> dict[str, Any]:
    settings = get_settings()
    if not isinstance(payload, dict):
        raise AppError("INVALID_WEBHOOK_BODY", "Body webhook harus object JSON", 422)
    # Authenticate every delivery, including repeats of rejected requests.
    if not settings.midtrans_server_key or not verify_legacy_notification(payload, settings.midtrans_server_key):
        raise AppError("INVALID_GATEWAY_SIGNATURE", "Signature notification Midtrans tidak valid", 401)
    return await apply_midtrans_event(db, merchant_code, payload, raw_body, source="MIDTRANS_WEBHOOK")


async def process_doku_notification(db: AsyncSession, merchant_code: str, payload: dict[str, Any], raw_body: bytes, headers: dict[str, str], request_target: str, *, trusted_provider_response: bool = False) -> dict[str, Any]:
    settings = get_settings()
    if not isinstance(payload, dict) or (not trusted_provider_response and not DokuDirectClient.verify_notification_signature(headers, raw_body, request_target, settings)):
        raise AppError("INVALID_GATEWAY_SIGNATURE", "Signature notification DOKU tidak valid", 401)
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    duplicate = await db.scalar(select(WebhookEvent).where(WebhookEvent.gateway == "DOKU", WebhookEvent.merchant_code == merchant_code, WebhookEvent.payload_hash == payload_hash))
    if duplicate:
        return {"accepted": True, "duplicate": True, "webhook_id": str(duplicate.id), "status": duplicate.processing_status}
    event = WebhookEvent(gateway="DOKU", merchant_code=merchant_code, provider_event_id=headers.get("request-id"), payload_hash=payload_hash,
                         payload={k: payload.get(k) for k in ("order", "transaction", "service", "channel")}, signature_valid=not trusted_provider_response, processing_status="RECEIVED")
    db.add(event)
    await db.flush()
    order = payload.get("order") or {}
    transaction = payload.get("transaction") or {}
    order_id = str(order.get("invoice_number") or "")
    attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.gateway == "DOKU", PaymentAttempt.gateway_order_id == order_id))
    if not attempt:
        event.processing_status = "QUARANTINED"
        await db.commit()
        raise AppError("UNKNOWN_GATEWAY_ORDER", "Order DOKU tidak ditemukan", 404, {"order_id": order_id, "webhook_id": str(event.id)})
    payment = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == attempt.payment_id).with_for_update())
    try:
        amount = Decimal(str(order.get("amount", "")))
        if amount != Decimal(payment.amount):
            raise AppError("GATEWAY_AMOUNT_MISMATCH", "Nominal DOKU berbeda dari ledger", 409)
        mapping = {"SUCCESS": PaymentStatus.PAID, "FAILED": PaymentStatus.FAILED, "EXPIRED": PaymentStatus.EXPIRED,
                   "REFUNDED": PaymentStatus.REFUNDED, "PENDING": PaymentStatus.PENDING,
                   "TIMEOUT": PaymentStatus.PENDING, "REDIRECT": PaymentStatus.PENDING}
        target = mapping.get(str(transaction.get("status") or "").upper())
        if target is None:
            raise AppError("UNKNOWN_PROVIDER_STATUS", "Status DOKU belum memiliki mapping", 422)
        current = PaymentStatus(payment.status)
        if target == PaymentStatus.REFUNDED:
            raise AppError("REFUND_RECONCILIATION_REQUIRED", "Refund DOKU memerlukan rekonsiliasi nominal", 409)
        if target == PaymentStatus.PAID and current in {PaymentStatus.PAID, PaymentStatus.REFUND_PENDING, PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED}:
            event.processing_status = "IGNORED"
        elif target == current:
            event.processing_status = "IGNORED"
        elif current in {PaymentStatus.PAID, PaymentStatus.REFUND_PENDING, PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED}:
            raise AppError("LATE_STATUS_REVIEW_REQUIRED", "Status DOKU terlambat memerlukan review", 409)
        else:
            await transition(db, payment, target, "DOKU_WEBHOOK", "Verified DOKU notification")
            attempt.status = target.value
            event.processing_status = "PROCESSED"
    except AppError:
        event.processing_status = "QUARANTINED"
        await db.commit()
        raise
    await db.commit()
    return {"accepted": True, "duplicate": False, "webhook_id": str(event.id), "status": event.processing_status, "payment_id": str(payment.id)}


async def apply_midtrans_event(db: AsyncSession, merchant_code: str, payload: dict, raw_body: bytes, *, source: str) -> dict:
    """Internal entry: caller must verify webhook or fetch authenticated provider status."""
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    lock_key = int.from_bytes(hashlib.sha256(("midtrans:" + merchant_code + ":" + str(payload.get("order_id", ""))).encode()).digest()[:8], "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    duplicate = await db.scalar(select(WebhookEvent).where(WebhookEvent.gateway == "MIDTRANS", WebhookEvent.merchant_code == merchant_code, WebhookEvent.payload_hash == payload_hash, WebhookEvent.processing_status.in_(["PROCESSED", "IGNORED"])))
    if duplicate:
        return {"accepted": True, "duplicate": True, "webhook_id": str(duplicate.id), "status": duplicate.processing_status}
    audit_payload = {k: payload[k] for k in ("order_id", "transaction_id", "transaction_status", "status_code", "gross_amount", "currency", "fraud_status") if k in payload}
    audit_payload["source"] = source
    event = WebhookEvent(gateway="MIDTRANS", merchant_code=merchant_code, provider_event_id=str(payload.get("transaction_id") or payload.get("order_id") or ""), payload_hash=payload_hash, payload=audit_payload, signature_valid=source == "MIDTRANS_WEBHOOK", processing_status="RECEIVED")
    db.add(event)
    await db.flush()
    order_id = str(payload.get("order_id") or "")
    attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.gateway == "MIDTRANS", PaymentAttempt.gateway_order_id == order_id))
    if not attempt:
        event.processing_status = "QUARANTINED"
        await db.commit()
        raise AppError("UNKNOWN_GATEWAY_ORDER", "Order Midtrans tidak ditemukan", 404, {"order_id": order_id, "webhook_id": str(event.id)})
    payment = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == attempt.payment_id).with_for_update().execution_options(populate_existing=True))
    if not payment:
        raise AppError("PAYMENT_NOT_FOUND", "Payment internal tidak ditemukan", 404)
    try:
        target = validate_midtrans_event(payload, payment)
        current = PaymentStatus(payment.status)
        protected = {PaymentStatus.PAID, PaymentStatus.REFUND_PENDING, PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED}
        if current == target or (current in protected and target not in protected):
            if target == PaymentStatus.PAID and attempt.status != "PAID":
                raise AppError("DUPLICATE_PAYMENT_REVIEW", "Attempt lain melaporkan pembayaran sukses", 409)
            if current == target == PaymentStatus.PENDING and attempt.status in {"INITIATED", "UNKNOWN"}:
                attempt.status = "PENDING"
            event.processing_status = "IGNORED"
            await db.commit()
            return {"accepted": True, "duplicate": False, "webhook_id": str(event.id), "status": "IGNORED"}
        # Refund notifications need a reconciled refund ledger, not only a status string.
        if target in {PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED}:
            raise AppError("REFUND_RECONCILIATION_REQUIRED", "Refund provider memerlukan rekonsiliasi nominal", 409)
        await transition(db, payment, target, source, "Verified Midtrans status")
    except AppError:
        event.processing_status = "QUARANTINED"
        await db.commit()
        raise
    attempt.status = target.value
    event.processing_status = "PROCESSED"
    client = await db.scalar(select(Client).where(Client.id == payment.client_id))
    if client:
        await enqueue_payment_callback(db, client, payment, f"payment.{target.value.lower()}")
    await db.commit()
    return {"accepted": True, "duplicate": False, "webhook_id": str(event.id), "payment_id": str(payment.id), "status": target.value}
