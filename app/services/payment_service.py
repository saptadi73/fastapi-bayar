import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.access import allow_url
from app.core.errors import AppError
from app.models.payment import Client, IdempotencyRecord, PaymentAttempt, PaymentStatus, PaymentStatusHistory, PaymentTransaction, Refund, Service
from app.schemas.payment import InitiatePaymentRequest
from app.services.portal_identity_service import resolve_portal_identity


def response_for(payment: PaymentTransaction) -> dict:
    return {"payment_id": str(payment.id), "payment_no": payment.payment_no, "reference_id": payment.external_reference, "amount": payment.amount, "currency": payment.currency, "status": payment.status.value, "expires_at": payment.expires_at.isoformat() if payment.expires_at else None,
            "client_id": str(payment.client_id), "client_name": payment.client_name,
            "event_id": payment.event_id, "event_name": payment.event_name,
            "customer": {"name": payment.customer_name, "email": payment.customer_email}}


async def initiate(db: AsyncSession, client: Client, payload: InitiatePaymentRequest, idem_key: str | None) -> tuple[dict, bool]:
    if not idem_key or not idem_key.strip() or len(idem_key) > 150:
        raise AppError("INVALID_IDEMPOTENCY_KEY", "Idempotency-Key wajib diisi (1-150 karakter)", 422)
    # Serialize initiation within a tenant; independent clients remain concurrent.
    await db.scalar(select(Client.id).where(Client.id == client.id).with_for_update())
    request_hash = hashlib.sha256(json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    if idem_key:
        existing = await db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.client_id == client.id, IdempotencyRecord.idempotency_key == idem_key))
        if existing:
            if existing.request_hash != request_hash:
                raise AppError("IDEMPOTENCY_CONFLICT", "Idempotency-Key sudah dipakai untuk request berbeda", 409)
            return existing.response_body, True
    if payload.expires_at and payload.expires_at <= datetime.now(timezone.utc):
        raise AppError("INVALID_EXPIRY", "expires_at harus di masa depan", 422)
    allow_url(payload.return_url, client.allowed_return_urls, "return_url")
    allow_url(client.callback_url, client.allowed_callback_urls, "callback_url")
    service = await db.scalar(select(Service).where(Service.client_id == client.id, Service.code == payload.service_code, Service.active.is_(True)))
    if not service:
        raise AppError("SERVICE_NOT_FOUND", "Service tidak ditemukan atau tidak aktif", 404)
    duplicate = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.client_id == client.id, PaymentTransaction.external_reference == payload.reference_id))
    if duplicate:
        raise AppError("DUPLICATE_REFERENCE", "Reference telah memiliki payment", 409, {"payment_id": str(duplicate.id)})
    payment = PaymentTransaction(client_id=client.id, service_id=service.id, payment_no=f"PAY-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}", external_reference=payload.reference_id, description=payload.description, amount=payload.amount, currency=payload.currency.upper(), customer_name=payload.customer.name, customer_email=payload.customer.email, customer_phone=payload.customer.phone, expires_at=payload.expires_at, return_url=payload.return_url, metadata_json=payload.metadata, status=PaymentStatus.CREATED)
    event, payer = await resolve_portal_identity(db, client, payload)
    payment.event_record_id = event.id
    payment.portal_user_id = payer.id
    payment.event_id = payload.event_id
    payment.event_name = payload.event_name
    payment.client_name = client.name
    db.add(payment)
    await db.flush()
    db.add(PaymentStatusHistory(payment_id=payment.id, from_status=None, to_status="CREATED", source="API", reason="Payment initiated"))
    result = response_for(payment)
    if idem_key:
        db.add(IdempotencyRecord(client_id=client.id, idempotency_key=idem_key, request_hash=request_hash, resource_id=payment.id, response_body=result))
    await db.commit()
    return result, False


async def get_owned(db: AsyncSession, client: Client, payment_id: uuid.UUID) -> PaymentTransaction:
    payment = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment_id, PaymentTransaction.client_id == client.id).with_for_update())
    if not payment:
        raise AppError("PAYMENT_NOT_FOUND", "Payment tidak ditemukan", 404)
    return payment


async def transition(db: AsyncSession, payment: PaymentTransaction, target: PaymentStatus, source: str, reason: str | None = None) -> PaymentTransaction:
    allowed = {
        PaymentStatus.CREATED: {PaymentStatus.PENDING, PaymentStatus.CANCELLED, PaymentStatus.FAILED},
        PaymentStatus.PENDING: {PaymentStatus.PAID, PaymentStatus.EXPIRED, PaymentStatus.CANCELLED, PaymentStatus.FAILED},
        PaymentStatus.PAID: {PaymentStatus.REFUND_PENDING},
        PaymentStatus.REFUND_PENDING: {PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED},
        PaymentStatus.PARTIALLY_REFUNDED: {PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED},
    }
    current = payment.status if isinstance(payment.status, PaymentStatus) else PaymentStatus(payment.status)
    if target != current and target not in allowed.get(current, set()):
        raise AppError("INVALID_STATUS_TRANSITION", f"Transisi {current.value} ke {target.value} tidak diizinkan", 409)
    if target == current:
        return payment
    payment.status = target
    db.add(PaymentStatusHistory(payment_id=payment.id, from_status=current.value, to_status=target.value, source=source, reason=reason))
    await db.flush()
    return payment


async def request_refund(db: AsyncSession, payment: PaymentTransaction, amount: int | None, reason: str) -> Refund:
    current = payment.status if isinstance(payment.status, PaymentStatus) else PaymentStatus(payment.status)
    if current not in {PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED}:
        raise AppError("REFUND_NOT_ALLOWED", "Refund hanya dapat diminta untuk payment yang sudah PAID", 409)
    refund_amount = amount or payment.amount
    await _validate_refund_amount(db, payment, refund_amount)
    refund = Refund(refund_no=f"RFD-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}", payment_id=payment.id, amount=refund_amount, reason=reason, status="REQUESTED", payment_status_before=current.value)
    db.add(refund)
    await transition(db, payment, PaymentStatus.REFUND_PENDING, "API", "Refund request dibuat")
    await db.commit()
    return refund


async def _validate_refund_amount(db, payment, refund_amount):
    if refund_amount > payment.amount:
        raise AppError("INVALID_REFUND_AMOUNT", "Nominal refund melebihi nominal payment", 422)
    used = await db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.payment_id == payment.id, Refund.status.not_in(["REJECTED", "FAILED"])))
    if refund_amount + int(used or 0) > payment.amount:
        raise AppError("REFUND_LIMIT_EXCEEDED", "Total refund melebihi nominal payment", 422)


async def cancel_owned_payment(db: AsyncSession, client: Client, payment_id: uuid.UUID) -> PaymentTransaction:
    from app.services.callback_service import enqueue_payment_callback

    payment = await get_owned(db, client, payment_id)
    if payment.status == PaymentStatus.CANCELLED:
        return payment
    if payment.status not in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
        raise AppError("INVALID_STATUS_TRANSITION", "Payment tidak dapat dibatalkan", 409)
    active = await db.scalar(select(PaymentAttempt.id).where(
        PaymentAttempt.payment_id == payment.id,
        PaymentAttempt.status.in_(["INITIATED", "UNKNOWN", "PENDING", "PAID"]),
    ).limit(1))
    if active:
        raise AppError("PROVIDER_CANCEL_REQUIRED", "Attempt aktif harus diperiksa/dibatalkan di provider terlebih dahulu", 409)
    await transition(db, payment, PaymentStatus.CANCELLED, "API", "Dibatalkan oleh client")
    await enqueue_payment_callback(db, client, payment, "payment.cancelled")
    await db.commit()
    return payment
