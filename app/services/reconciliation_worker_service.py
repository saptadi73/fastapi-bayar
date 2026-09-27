"""Claim and process admin reconciliation cases outside the web request."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.gateways.midtrans.client import MidtransSnapClient
from app.gateways.doku.client import DokuDirectClient
from app.models.payment import ReconciliationCase
from app.services.reconciliation_service import reconcile_attempt


async def claim_case(db):
    now = datetime.now(timezone.utc)
    case = await db.scalar(select(ReconciliationCase)
                           .where(ReconciliationCase.status.in_(["REQUESTED", "RETRY_WAIT"]),
                                  (ReconciliationCase.next_retry_at.is_(None) | (ReconciliationCase.next_retry_at <= now)))
                           .order_by(ReconciliationCase.requested_at, ReconciliationCase.id)
                           .with_for_update(skip_locked=True))
    if not case:
        return None
    case.status = "RUNNING"
    case.started_at = datetime.now(timezone.utc)
    case.retry_count += 1
    await db.commit()
    return case.id, case.attempt_id


async def finish_case(case_id, result_status=None, error_code=None):
    async with SessionLocal() as db:
        case = await db.get(ReconciliationCase, case_id, with_for_update=True)
        if not case or case.status != "RUNNING":
            return
        settings = get_settings()
        retryable = error_code is not None and case.retry_count < settings.worker_reconciliation_max_attempts
        case.status = "COMPLETED" if error_code is None else ("RETRY_WAIT" if retryable else "FAILED")
        case.result_status = result_status
        case.error_code = error_code
        case.next_retry_at = (datetime.now(timezone.utc) + timedelta(
            seconds=min(settings.worker_reconciliation_backoff_seconds * (2 ** (case.retry_count - 1)), 3600)
        )) if retryable else None
        case.completed_at = None if retryable else datetime.now(timezone.utc)
        await db.commit()


async def reconciliation_tick() -> dict[str, int]:
    totals = {"claimed": 0, "completed": 0, "retry_wait": 0, "failed": 0}
    for _ in range(get_settings().worker_reconciliation_batch_size):
        async with SessionLocal() as db:
            claim = await claim_case(db)
        if not claim:
            break
        case_id, attempt_id = claim
        totals["claimed"] += 1
        try:
            async with SessionLocal() as db:
                from app.models.payment import PaymentAttempt
                case = await db.get(ReconciliationCase, case_id)
                attempt = await db.get(PaymentAttempt, case.attempt_id)
                adapter = DokuDirectClient(get_settings()) if attempt.gateway == "DOKU" else MidtransSnapClient(get_settings())
                result = await reconcile_attempt(db, attempt_id, adapter)
            await finish_case(case_id, result_status=result.get("status", "UNKNOWN"))
            totals["completed"] += 1
        except AppError as exc:
            await finish_case(case_id, error_code=exc.code)
            totals["retry_wait" if get_settings().worker_reconciliation_max_attempts > 1 else "failed"] += 1
        except Exception:
            # Do not expose provider/database error text in logs or API responses.
            await finish_case(case_id, error_code="RECONCILIATION_WORKER_ERROR")
            totals["retry_wait" if get_settings().worker_reconciliation_max_attempts > 1 else "failed"] += 1
    return totals
