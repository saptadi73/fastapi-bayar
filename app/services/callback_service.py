import uuid
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.access import allow_url
from app.core.errors import AppError
from app.core.secret_store import decrypt_secret
from app.models.payment import CallbackDelivery, Client, PaymentTransaction

RETRY_DELAYS_SECONDS = (60, 300, 900, 3600, 21600, 86400)


async def enqueue_payment_callback(db: AsyncSession, client: Client, payment: PaymentTransaction, event_type: str) -> CallbackDelivery | None:
    if not client.callback_url:
        return None
    allow_url(client.callback_url, client.allowed_callback_urls, "callback_url")
    event_id = uuid.uuid4()
    delivery = CallbackDelivery(
        payment_id=payment.id,
        event_id=event_id,
        event_type=event_type,
        callback_url=client.callback_url,
        payload={
            "event_id": str(event_id),
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "payment_id": str(payment.id),
                "payment_no": payment.payment_no,
                "reference_id": payment.external_reference,
                "event_id": payment.event_id,
                "event_name": payment.event_name,
                "amount": payment.amount,
                "currency": payment.currency,
                "status": payment.status.value,
            },
        },
        status="PENDING",
    )
    db.add(delivery)
    await db.flush()
    return delivery


def callback_signature(payload: dict, secret: str, timestamp: str) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    canonical = f"{timestamp}.{raw}"
    digest = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


async def deliver_pending_callbacks(db: AsyncSession, limit: int = 20) -> dict[str, int]:
    """Send due callbacks once; a scheduler should call this repeatedly."""
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(CallbackDelivery, Client)
        .join(PaymentTransaction, PaymentTransaction.id == CallbackDelivery.payment_id)
        .join(Client, Client.id == PaymentTransaction.client_id)
        .where(CallbackDelivery.status.in_(["PENDING", "RETRY"]), (CallbackDelivery.next_retry_at.is_(None)) | (CallbackDelivery.next_retry_at <= now))
        .order_by(CallbackDelivery.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True, of=CallbackDelivery)
    )).all()
    result = {"succeeded": 0, "retry": 0, "dead_letter": 0}
    timeout = get_settings().callback_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        for delivery, owner in rows:
            try:
                allow_url(delivery.callback_url, owner.allowed_callback_urls, "callback_url")
                if not owner.active:
                    raise AppError("CLIENT_INACTIVE", "Client tidak aktif", 403)
            except AppError:
                delivery.status = "DEAD_LETTER"
                result["dead_letter"] += 1
                continue
            delivery.status = "SENDING"
            delivery.attempt_no += 1
            if owner.callback_secret_ciphertext:
                settings = get_settings()
                secret = decrypt_secret(owner.callback_secret_ciphertext, settings.credential_encryption_key,
                                        settings.credential_encryption_key_previous)
            else:
                # Legacy rows remain readable until the controlled backfill is run.
                if owner.callback_secret:
                    secret = owner.callback_secret
                elif owner.api_secret_ciphertext:
                    settings = get_settings()
                    secret = decrypt_secret(owner.api_secret_ciphertext, settings.credential_encryption_key,
                                            settings.credential_encryption_key_previous)
                else:
                    secret = owner.api_secret
            timestamp = datetime.now(timezone.utc).isoformat()
            headers = {"Content-Type": "application/json", "X-Event-ID": str(delivery.event_id), "X-Timestamp": timestamp, "X-Signature": callback_signature(delivery.payload, secret, timestamp)}
            try:
                raw = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
                response = await client.post(delivery.callback_url, content=raw, headers=headers)
                if 200 <= response.status_code < 300:
                    delivery.status = "SUCCEEDED"
                    delivery.sent_at = datetime.now(timezone.utc)
                    result["succeeded"] += 1
                elif delivery.attempt_no >= get_settings().callback_max_attempts:
                    delivery.status = "DEAD_LETTER"
                    result["dead_letter"] += 1
                else:
                    delivery.status = "RETRY"
                    delay = RETRY_DELAYS_SECONDS[min(delivery.attempt_no - 1, len(RETRY_DELAYS_SECONDS) - 1)]
                    delivery.next_retry_at = now + timedelta(seconds=delay)
                    result["retry"] += 1
            except httpx.HTTPError:
                if delivery.attempt_no >= get_settings().callback_max_attempts:
                    delivery.status = "DEAD_LETTER"
                    result["dead_letter"] += 1
                else:
                    delivery.status = "RETRY"
                    delay = RETRY_DELAYS_SECONDS[min(delivery.attempt_no - 1, len(RETRY_DELAYS_SECONDS) - 1)]
                    delivery.next_retry_at = now + timedelta(seconds=delay)
                    result["retry"] += 1
    await db.commit()
    return result
