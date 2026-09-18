import hashlib
import json

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError
from app.models.payment import WebhookEvent
from app.services.webhook_service import process_midtrans_notification

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/midtrans/{merchant_code}", status_code=status.HTTP_200_OK)
async def receive_midtrans_webhook(merchant_code: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    try:
        payload = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AppError("INVALID_WEBHOOK_BODY", "Body webhook harus JSON valid", 422)
    return {"data": await process_midtrans_notification(db, merchant_code, payload, body)}

@router.post("/{gateway}/{merchant_code}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(gateway: str, merchant_code: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    payload_hash = hashlib.sha256(body).hexdigest()
    duplicate = await db.scalar(select(WebhookEvent).where(WebhookEvent.gateway == gateway.upper(), WebhookEvent.payload_hash == payload_hash))
    if duplicate:
        return {"data": {"accepted": True, "duplicate": True, "webhook_id": str(duplicate.id), "status": duplicate.processing_status}}
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        payload = {"_raw_payload": body.decode("utf-8", errors="replace")}
    event = WebhookEvent(gateway=gateway.upper(), merchant_code=merchant_code, payload_hash=payload_hash, payload=payload, signature_valid=False, processing_status="QUARANTINED")
    db.add(event)
    await db.commit()
    return {"data": {"accepted": True, "duplicate": False, "webhook_id": str(event.id), "status": event.processing_status}}
