"""Durable reservations serialize checkout requests before provider I/O."""
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.gateways.registry import client_for_channel
from app.models.payment import PaymentAttempt, PaymentStatus, PaymentTransaction
from app.services.payment_service import transition
from app.services.routing_service import ensure_channel_eligible

ACTIVE_ATTEMPT_STATUSES = ("INITIATED", "PENDING", "UNKNOWN")


async def create_attempt(db: AsyncSession, payment: PaymentTransaction, channel_code: str) -> PaymentAttempt:
    channel_code = channel_code.upper()
    await ensure_channel_eligible(db, payment, channel_code)
    adapter = client_for_channel(channel_code, get_settings())
    payment = await db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.id == payment.id
    ).with_for_update().execution_options(populate_existing=True))
    if payment.status not in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
        raise AppError("INVALID_STATUS_TRANSITION", "Payment tidak dapat menerima attempt baru", 409)
    if payment.expires_at and payment.expires_at <= datetime.now(timezone.utc):
        raise AppError("PAYMENT_EXPIRED", "Waktu checkout sudah berakhir", 409)
    if payment.currency != "IDR":
        raise AppError("UNSUPPORTED_CURRENCY", "Checkout saat ini hanya mendukung IDR", 422)
    active = await db.scalar(select(PaymentAttempt).where(
        PaymentAttempt.payment_id == payment.id,
        PaymentAttempt.status.in_(ACTIVE_ATTEMPT_STATUSES),
    ).order_by(PaymentAttempt.attempt_no.desc()))
    if active:
        if active.status == "PENDING" and active.channel_code == channel_code:
            await db.commit()
            return active
        raise AppError("ATTEMPT_IN_PROGRESS", "Attempt sebelumnya masih aktif atau memerlukan status inquiry", 409,
                       {"attempt_id": str(active.id), "status": active.status})
    last_no = await db.scalar(select(func.max(PaymentAttempt.attempt_no)).where(PaymentAttempt.payment_id == payment.id))
    attempt_no = int(last_no or 0) + 1
    attempt = PaymentAttempt(payment_id=payment.id, attempt_no=attempt_no,
                             gateway=adapter.name, channel_code=channel_code,
                             gateway_order_id=f"{payment.payment_no}-{adapter.name[:2]}-{attempt_no:02d}",
                             status="INITIATED", instructions={})
    db.add(attempt)
    await transition(db, payment, PaymentStatus.PENDING, "API", "Provider attempt reserved")
    await db.commit()
    # At this point a webhook can locate the order, and a competing create sees INITIATED.
    try:
        result = await adapter.create_payment(
            order_id=attempt.gateway_order_id, amount=payment.amount, currency=payment.currency,
            customer={"name": payment.customer_name, "email": payment.customer_email, "phone": payment.customer_phone},
            channel_code=channel_code,
        )
        failure = None
    except (httpx.HTTPError, AppError, ValueError):
        # A network failure or malformed response cannot prove that no charge was created.
        result = None
        failure = AppError("GATEWAY_OUTCOME_UNKNOWN", "Hasil gateway belum pasti; lakukan status inquiry sebelum mencoba lagi", 503,
                           {"attempt_id": str(attempt.id)})
    # Same lock order as notification processing; refresh to preserve an early PAID webhook.
    await db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment.id).with_for_update())
    attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.id == attempt.id)
                              .with_for_update().execution_options(populate_existing=True))
    if attempt.status == "INITIATED":
        attempt.status = "UNKNOWN" if failure else result.status
    if result:
        attempt.instructions = result.instructions or {}
    await db.commit()
    if failure and attempt.status == "UNKNOWN":
        raise failure
    return attempt
