from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import AppError
from app.models.admin import AdminAudit
from app.models.payment import PaymentAttempt, ReconciliationCase


def case_view(case, attempt=None):
    data = {"id": str(case.id), "attempt_id": str(case.attempt_id), "requested_by": str(case.requested_by) if case.requested_by else None,
            "status": case.status, "reason": case.reason, "requested_at": case.requested_at.isoformat(),
            "started_at": case.started_at.isoformat() if case.started_at else None,
            "completed_at": case.completed_at.isoformat() if case.completed_at else None,
            "result_status": case.result_status, "error_code": case.error_code}
    if attempt:
        data["attempt"] = {"gateway": attempt.gateway, "channel_code": attempt.channel_code,
                            "gateway_order_id": attempt.gateway_order_id, "status": attempt.status}
    return data


async def list_cases(db, limit, offset):
    rows = list((await db.execute(select(ReconciliationCase, PaymentAttempt)
        .join(PaymentAttempt, PaymentAttempt.id == ReconciliationCase.attempt_id)
        .order_by(ReconciliationCase.requested_at.desc(), ReconciliationCase.id.desc())
        .limit(limit + 1).offset(offset))).all())
    return {"data": [case_view(case, attempt) for case, attempt in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}


async def request_case(db, actor_id: UUID, attempt_id: UUID, reason: str):
    attempt = await db.scalar(select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update())
    if not attempt:
        raise AppError("ATTEMPT_NOT_FOUND", "Payment attempt tidak ditemukan", 404)
    if attempt.gateway not in {"MIDTRANS", "DOKU"}:
        raise AppError("RECONCILIATION_UNSUPPORTED", "Gateway attempt belum mendukung inquiry", 422)
    if attempt.status not in {"INITIATED", "UNKNOWN", "PENDING"}:
        raise AppError("RECONCILIATION_NOT_REQUIRED", "Attempt tidak membutuhkan inquiry saat ini", 409)
    case = await db.scalar(select(ReconciliationCase).where(ReconciliationCase.attempt_id == attempt_id).with_for_update())
    if case:
        if case.status in {"REQUESTED", "RUNNING"}:
            return case, False
        if case.status == "COMPLETED":
            return case, True
        case.status, case.error_code, case.reason = "REQUESTED", None, reason
        case.requested_by, case.requested_at = actor_id, datetime.now(timezone.utc)
    else:
        case = ReconciliationCase(attempt_id=attempt_id, requested_by=actor_id, reason=reason)
        db.add(case)
    db.add(AdminAudit(actor_id=actor_id, action="RECONCILIATION_REQUESTED", resource_id=str(attempt.payment_id),
                      reason=reason, occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return case, False
