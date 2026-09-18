from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.schemas.admin_refund import AdminRefundRequest, RefundDecision
from app.services import admin_refund_service as service

router = APIRouter(prefix="/admin/refunds", tags=["Admin Refunds"], dependencies=[Depends(enabled)])

@router.get("")
async def listing(status: str | None = Query(None, min_length=1, max_length=30), payment_id: UUID | None = None,
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  identity=Depends(require("admin.refunds.read")), db: AsyncSession = Depends(get_db)):
    return await service.list_refunds(db, status, payment_id, limit, offset)

@router.post("/request", status_code=202)
async def request(payload: AdminRefundRequest, identity=Depends(require("admin.refunds.request")), db: AsyncSession = Depends(get_db)):
    refund, payment = await service.request_admin_refund(db, identity[0].id, payload.payment_id, payload.amount, payload.reason)
    return {"data": service.refund_view(refund, payment), "meta": {"provider_action": "NOT_STARTED"}}

@router.post("/{refund_id}/approve", status_code=202)
async def approve(refund_id: UUID, payload: RefundDecision, identity=Depends(require("admin.refunds.approve")), db: AsyncSession = Depends(get_db)):
    refund, payment = await service.approve_refund(db, identity[0].id, refund_id, payload.expected_version)
    return {"data": service.refund_view(refund, payment), "meta": {"provider_action": "PENDING_ADAPTER"}}

@router.post("/{refund_id}/reject")
async def reject(refund_id: UUID, payload: RefundDecision, identity=Depends(require("admin.refunds.approve")), db: AsyncSession = Depends(get_db)):
    if not payload.reason:
        from app.core.errors import AppError
        raise AppError("REFUND_REJECTION_REASON_REQUIRED", "Alasan penolakan wajib diisi", 422)
    refund, payment = await service.reject_refund(db, identity[0].id, refund_id, payload.expected_version, payload.reason)
    return {"data": service.refund_view(refund, payment)}
