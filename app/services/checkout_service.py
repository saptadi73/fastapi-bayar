import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.payment import CheckoutSession, Client, PaymentTransaction


async def new_checkout(db: AsyncSession, payment: PaymentTransaction) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=get_settings().checkout_ttl_seconds)
    if payment.expires_at:
        expires = min(expires, payment.expires_at)
    if expires <= now or payment.status.value not in {"CREATED", "PENDING"}:
        raise AppError("CHECKOUT_UNAVAILABLE", "Payment tidak menerima checkout baru", 409)
    token = secrets.token_urlsafe(32)
    db.add(CheckoutSession(payment_id=payment.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=expires))
    await db.commit()
    return {"checkout_token": token, "checkout_expires_at": expires.isoformat(),
            "payment_url": f"{get_settings().public_base_url.rstrip('/')}/p/{payment.payment_no}#token={token}"}


async def payment_for_checkout(db: AsyncSession, token: str) -> PaymentTransaction:
    if len(token) != 43:
        raise AppError("INVALID_CHECKOUT_TOKEN", "Checkout token tidak valid", 401)
    payment = await db.scalar(select(PaymentTransaction).join(CheckoutSession, CheckoutSession.payment_id == PaymentTransaction.id)
        .join(Client, Client.id == PaymentTransaction.client_id)
        .where(CheckoutSession.token_hash == hashlib.sha256(token.encode()).hexdigest(),
               CheckoutSession.expires_at > datetime.now(timezone.utc), Client.active.is_(True)))
    if not payment:
        raise AppError("INVALID_CHECKOUT_TOKEN", "Checkout token tidak valid atau kedaluwarsa", 401)
    return payment

