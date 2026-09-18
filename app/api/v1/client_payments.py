import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import client_dependency
from app.core.database import get_db
from app.models.payment import Client
from app.schemas.payment import InitiatePaymentRequest, RefundRequest
from app.services.payment_service import cancel_owned_payment, get_owned, initiate, request_refund, response_for
from app.services.checkout_service import new_checkout

router = APIRouter(prefix="/client/payments", tags=["Client Payments"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment(payload: InitiatePaymentRequest, db: AsyncSession = Depends(get_db), client: Client = Depends(client_dependency), idempotency_key: str = Header(..., min_length=1, max_length=150)):
    result, replayed = await initiate(db, client, payload, idempotency_key)
    payment = await get_owned(db, client, uuid.UUID(result["payment_id"]))
    result = dict(result)
    result.pop("payment_url", None)
    if payment.status.value in {"CREATED", "PENDING"} and (not payment.expires_at or payment.expires_at > datetime.now(timezone.utc)):
        result.update(await new_checkout(db, payment))
    return {"data": result, "meta": {"idempotent_replay": replayed}}


@router.post("/{payment_id}/checkout")
async def renew_checkout(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db), client: Client = Depends(client_dependency)):
    return {"data": await new_checkout(db, await get_owned(db, client, payment_id))}


@router.get("/{payment_id}")
async def get_payment(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db), client: Client = Depends(client_dependency)):
    return {"data": response_for(await get_owned(db, client, payment_id))}


@router.post("/{payment_id}/cancel")
async def cancel_payment(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db), client: Client = Depends(client_dependency)):
    payment = await cancel_owned_payment(db, client, payment_id)
    return {"data": response_for(payment)}


@router.post("/{payment_id}/refunds", status_code=status.HTTP_201_CREATED)
async def refund_payment(payment_id: uuid.UUID, payload: RefundRequest, db: AsyncSession = Depends(get_db), client: Client = Depends(client_dependency)):
    payment = await get_owned(db, client, payment_id)
    refund = await request_refund(db, payment, payload.amount, payload.reason)
    return {"data": {"refund_id": str(refund.id), "refund_no": refund.refund_no, "payment_id": str(payment.id), "amount": refund.amount, "status": refund.status, "message": "Refund request tercatat dan menunggu pemrosesan gateway."}}
