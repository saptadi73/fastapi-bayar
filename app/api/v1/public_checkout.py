from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError
from app.models.payment import PaymentTransaction
from app.schemas.payment import CreateAttemptRequest
from app.services.payment_service import response_for
from app.services.attempt_service import create_attempt
from app.models.payment import PaymentAttempt
from app.core.access import bearer_value
from app.core.config import get_settings
from app.services.checkout_service import payment_for_checkout

router = APIRouter(prefix="/public", tags=["Public Checkout"])

async def checkout_owner(authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    return await payment_for_checkout(db, bearer_value(authorization))


async def by_no(payment_no: str, payment: PaymentTransaction) -> PaymentTransaction:
    if payment.payment_no != payment_no:
        raise AppError("PAYMENT_NOT_FOUND", "Payment tidak ditemukan", 404)
    return payment

@router.get("/payments/{payment_no}")
async def checkout_summary(payment_no: str, payment: PaymentTransaction = Depends(checkout_owner)):
    p = await by_no(payment_no, payment)
    return {"data": {"payment_no": p.payment_no, "amount": p.amount, "currency": p.currency, "status": p.status.value}}

@router.get("/payments/{payment_no}/channels")
async def available_channels(payment_no: str, payment: PaymentTransaction = Depends(checkout_owner)):
    await by_no(payment_no, payment)
    settings = get_settings()
    channels = []
    if payment.status.value in {"CREATED", "PENDING"} and settings.midtrans_enabled and settings.midtrans_server_key:
        channels = [{"code": "MIDTRANS_SNAP", "name": "Midtrans Snap"}]
    return {"data": {"channels": channels}}


@router.post("/payments/{payment_no}/attempts", status_code=status.HTTP_201_CREATED)
async def select_channel(payment_no: str, payload: CreateAttemptRequest, db: AsyncSession = Depends(get_db), payment: PaymentTransaction = Depends(checkout_owner)):
    payment = await by_no(payment_no, payment)
    attempt = await create_attempt(db, payment, payload.channel_code)
    return {"data": {"attempt_id": str(attempt.id), "gateway": attempt.gateway, "channel_code": attempt.channel_code, "gateway_order_id": attempt.gateway_order_id, "status": attempt.status, "instructions": attempt.instructions}}


@router.get("/payments/{payment_no}/status")
async def checkout_status(payment_no: str, payment: PaymentTransaction = Depends(checkout_owner)):
    return await checkout_summary(payment_no, payment)


@router.get("/attempts/{attempt_id}/instructions")
async def attempt_instructions(attempt_id: UUID, db: AsyncSession = Depends(get_db), payment: PaymentTransaction = Depends(checkout_owner)):
    attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.id == attempt_id, PaymentAttempt.payment_id == payment.id))
    if not attempt:
        raise AppError("ATTEMPT_NOT_FOUND", "Payment attempt tidak ditemukan", 404)
    return {"data": {"attempt_id": str(attempt.id), "gateway": attempt.gateway, "channel_code": attempt.channel_code, "status": attempt.status, "instructions": attempt.instructions}}
