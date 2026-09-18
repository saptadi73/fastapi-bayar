from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.models.payment import PaymentStatus
from app.services import admin_payment_service as service

router = APIRouter(prefix="/admin/payments", tags=["Admin Payments"],
                   dependencies=[Depends(enabled), Depends(require("admin.payments.read"))])


@router.get("")
async def listing(client_id: UUID | None = None, service_id: UUID | None = None,
                  event_id: str | None = Query(None, min_length=1, max_length=150),
                  status: PaymentStatus | None = None,
                  reference_id: str | None = Query(None, min_length=1, max_length=150),
                  created_from: AwareDatetime | None = None, created_to: AwareDatetime | None = None,
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  db: AsyncSession = Depends(get_db)):
    return await service.list_payments(db, client_id=client_id, service_id=service_id, event_id=event_id,
                                       status=status, reference_id=reference_id, created_from=created_from,
                                       created_to=created_to, limit=limit, offset=offset)


@router.get("/{payment_id}")
async def detail(payment_id: UUID, db: AsyncSession = Depends(get_db)):
    return {"data": service.payment_view(await service.get_payment(db, payment_id))}


@router.get("/{payment_id}/history")
async def history(payment_id: UUID, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   db: AsyncSession = Depends(get_db)):
    return await service.history(db, payment_id, limit, offset)


@router.get("/{payment_id}/attempts")
async def attempts(payment_id: UUID, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                    db: AsyncSession = Depends(get_db)):
    return await service.attempts(db, payment_id, limit, offset)
