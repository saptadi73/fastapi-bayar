from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.models.payment import ReconciliationCase
from app.schemas.admin_reconciliation import ReconciliationRequest
from app.services.admin_reconciliation_service import list_cases, request_case, case_view

router = APIRouter(prefix="/admin/reconciliation", tags=["Admin Reconciliation"],
                   dependencies=[Depends(enabled)])


@router.get("")
async def listing(identity=Depends(require("admin.reconciliation.read")), db: AsyncSession = Depends(get_db),
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return await list_cases(db, limit, offset)


@router.post("/{attempt_id}/request", status_code=202)
async def request(attempt_id: UUID, payload: ReconciliationRequest,
                  identity=Depends(require("admin.reconciliation.request")), db: AsyncSession = Depends(get_db)):
    case, already_complete = await request_case(db, identity[0].id, attempt_id, payload.reason)
    return {"data": case_view(case), "meta": {"already_complete": already_complete}}
