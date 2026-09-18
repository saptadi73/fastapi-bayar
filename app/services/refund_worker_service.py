"""At-least-once provider refund worker for approved Midtrans refunds."""
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.gateways.midtrans.client import MidtransSnapClient
from app.models.payment import PaymentAttempt, PaymentStatus, PaymentStatusHistory, PaymentTransaction, Refund


async def claim_refund(db):
    row = (await db.execute(select(Refund, PaymentTransaction)
        .join(PaymentTransaction, PaymentTransaction.id == Refund.payment_id)
        .where(Refund.status == "APPROVED")
        .order_by(Refund.created_at, Refund.id)
        .with_for_update(skip_locked=True))).first()
    if not row:
        return None
    refund, payment = row
    attempt = await db.scalar(select(PaymentAttempt).where(
        PaymentAttempt.payment_id == payment.id, PaymentAttempt.gateway == "MIDTRANS"
    ).order_by(PaymentAttempt.attempt_no.desc()).limit(1))
    if not attempt:
        refund.status, refund.provider_error_code, refund.completed_at = "FAILED", "MIDTRANS_ATTEMPT_NOT_FOUND", datetime.now(timezone.utc)
        await db.commit()
        return "failed", refund.id
    refund.status = "PROCESSING"
    refund.attempted_at = datetime.now(timezone.utc)
    refund.version += 1
    await db.commit()
    return refund.id, attempt.gateway_order_id, refund.refund_no, refund.amount, refund.reason


async def finish_refund(refund_id, *, status, provider_status=None, provider_ref=None, error_code=None):
    async with SessionLocal() as db:
        refund = await db.get(Refund, refund_id, with_for_update=True)
        if not refund or refund.status not in {"PROCESSING", "RECONCILING"}:
            return
        refund.status = status
        refund.provider_status = provider_status
        refund.provider_ref = provider_ref
        refund.provider_error_code = error_code
        refund.completed_at = datetime.now(timezone.utc) if status in {"PROVIDER_ACCEPTED", "FAILED"} else None
        refund.version += 1
        await db.commit()


async def claim_provider_refund(db):
    row = (await db.execute(select(Refund, PaymentTransaction)
        .join(PaymentTransaction, PaymentTransaction.id == Refund.payment_id)
        .where(Refund.status == "PROVIDER_ACCEPTED")
        .order_by(Refund.completed_at, Refund.id)
        .with_for_update(skip_locked=True))).first()
    if not row:
        return None
    refund, payment = row
    attempt = await db.scalar(select(PaymentAttempt).where(
        PaymentAttempt.payment_id == payment.id, PaymentAttempt.gateway == "MIDTRANS"
    ).order_by(PaymentAttempt.attempt_no.desc()).limit(1))
    if not attempt:
        refund.status, refund.provider_error_code = "FAILED", "MIDTRANS_ATTEMPT_NOT_FOUND"
        refund.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return "failed", refund.id
    refund.status, refund.version = "RECONCILING", refund.version + 1
    await db.commit()
    return refund.id, attempt.gateway_order_id


async def finish_provider_reconciliation(refund_id, payload):
    async with SessionLocal() as db:
        row = (await db.execute(select(Refund, PaymentTransaction).join(PaymentTransaction, PaymentTransaction.id == Refund.payment_id)
                                .where(Refund.id == refund_id).with_for_update())).first()
        if not row or row[0].status != "RECONCILING":
            return "ignored"
        refund, payment = row
        history = payload.get("refunds") if isinstance(payload.get("refunds"), list) else []
        matched = None
        for item in history:
            if not isinstance(item, dict):
                continue
            key = str(item.get("refund_key") or "")
            try:
                item_amount = int(float(str(item.get("refund_amount", "0"))))
            except (TypeError, ValueError):
                item_amount = 0
            if key == refund.refund_no and item_amount == refund.amount:
                matched = item
                break
        if matched is None:
            refund.status = "PROVIDER_ACCEPTED"
            refund.provider_status = str(payload.get("transaction_status") or "UNKNOWN")
            refund.version += 1
            await db.commit()
            return "pending"
        refund.status = "SUCCEEDED"
        refund.provider_status = str(payload.get("transaction_status") or "UNKNOWN")
        refund.provider_ref = str(matched.get("refund_chargeback_id") or refund.provider_ref or "")
        refund.completed_at = datetime.now(timezone.utc)
        refund.version += 1
        total = await db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.payment_id == payment.id, Refund.status == "SUCCEEDED"))
        target = PaymentStatus.REFUNDED if int(total or 0) >= payment.amount else PaymentStatus.PARTIALLY_REFUNDED
        current = payment.status if isinstance(payment.status, PaymentStatus) else PaymentStatus(payment.status)
        if current == PaymentStatus.REFUND_PENDING:
            payment.status = target
            db.add(PaymentStatusHistory(payment_id=payment.id, from_status=current.value, to_status=target.value,
                                        source="REFUND_RECONCILIATION", reason="Nominal refund dikonfirmasi provider"))
        await db.commit()
        return "succeeded"


async def reconcile_provider_refunds() -> dict[str, int]:
    totals = {"claimed": 0, "succeeded": 0, "pending": 0, "failed": 0}
    for _ in range(get_settings().worker_refund_batch_size):
        async with SessionLocal() as db:
            claim = await claim_provider_refund(db)
        if not claim:
            break
        if claim[0] == "failed":
            totals["failed"] += 1
            continue
        refund_id, order_id = claim
        totals["claimed"] += 1
        try:
            payload = await MidtransSnapClient(get_settings()).get_status(order_id)
            if payload is None:
                await finish_refund(refund_id, status="FAILED", error_code="PROVIDER_NOT_FOUND")
                totals["failed"] += 1
                continue
            outcome = await finish_provider_reconciliation(refund_id, payload)
            if outcome in totals:
                totals[outcome] += 1
        except AppError as exc:
            await finish_refund(refund_id, status="PROVIDER_ACCEPTED", error_code=exc.code)
            totals["pending"] += 1
        except Exception:
            await finish_refund(refund_id, status="PROVIDER_ACCEPTED", error_code="REFUND_INQUIRY_ERROR")
            totals["pending"] += 1
    return totals


async def refund_tick() -> dict[str, int]:
    totals = {"claimed": 0, "accepted": 0, "succeeded": 0, "pending": 0, "failed": 0}
    if not get_settings().midtrans_enabled:
        return totals
    reconciled = await reconcile_provider_refunds()
    for key in ("claimed", "succeeded", "pending", "failed"):
        totals[key] += reconciled[key]
    for _ in range(get_settings().worker_refund_batch_size):
        async with SessionLocal() as db:
            claim = await claim_refund(db)
        if not claim:
            break
        if claim[0] == "failed":
            totals["failed"] += 1
            continue
        refund_id, order_id, refund_key, amount, reason = claim
        totals["claimed"] += 1
        try:
            result = await MidtransSnapClient(get_settings()).refund(order_id=order_id, refund_key=refund_key, amount=amount, reason=reason)
            await finish_refund(refund_id, status="PROVIDER_ACCEPTED", provider_status=result.get("transaction_status"), provider_ref=str(result.get("refund_chargeback_id") or result.get("refund_key") or ""))
            totals["accepted"] += 1
        except AppError as exc:
            await finish_refund(refund_id, status="FAILED", error_code=exc.code)
            totals["failed"] += 1
        except Exception:
            await finish_refund(refund_id, status="FAILED", error_code="REFUND_WORKER_ERROR")
            totals["failed"] += 1
    return totals
