from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.errors import AppError
from app.models.admin import AdminAudit
from app.models.payment import PaymentStatus, PaymentStatusHistory, PaymentTransaction, Refund
from app.services.payment_service import _validate_refund_amount, transition


def refund_view(refund, payment=None):
    result = {"id": str(refund.id), "refund_no": refund.refund_no, "payment_id": str(refund.payment_id),
              "amount": refund.amount, "reason": refund.reason, "status": refund.status,
              "requested_by_admin": str(refund.requested_by_admin) if refund.requested_by_admin else None,
              "approved_by": str(refund.approved_by) if refund.approved_by else None,
              "rejected_by": str(refund.rejected_by) if refund.rejected_by else None,
              "rejection_reason": refund.rejection_reason, "version": refund.version,
              "provider_ref": refund.provider_ref, "provider_status": refund.provider_status,
              "provider_error_code": refund.provider_error_code,
              "created_at": refund.created_at.isoformat()}
    if payment:
        result["payment"] = {"payment_no": payment.payment_no, "client_id": str(payment.client_id),
                              "client_name": payment.client_name, "event_id": payment.event_id,
                              "event_name": payment.event_name, "status": payment.status.value}
    return result


async def list_refunds(db, status, payment_id, limit, offset):
    query = select(Refund, PaymentTransaction).join(PaymentTransaction, PaymentTransaction.id == Refund.payment_id)
    if status:
        query = query.where(Refund.status == status)
    if payment_id:
        query = query.where(Refund.payment_id == payment_id)
    rows = list((await db.execute(query.order_by(Refund.created_at.desc(), Refund.id.desc()).limit(limit + 1).offset(offset))).all())
    return {"data": [refund_view(refund, payment) for refund, payment in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}


async def request_admin_refund(db, actor_id: UUID, payment_id: UUID, amount, reason):
    payment = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment_id).with_for_update())
    if not payment:
        raise AppError("PAYMENT_NOT_FOUND", "Payment tidak ditemukan", 404)
    current = payment.status if isinstance(payment.status, PaymentStatus) else PaymentStatus(payment.status)
    if current not in {PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED}:
        raise AppError("REFUND_NOT_ALLOWED", "Refund hanya dapat diminta untuk payment yang sudah PAID", 409)
    refund_amount = amount or payment.amount
    await _validate_refund_amount(db, payment, refund_amount)
    refund = Refund(refund_no=f"RFD-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}",
                    payment_id=payment.id, amount=refund_amount, reason=reason, status="REQUESTED",
                    requested_by_admin=actor_id, payment_status_before=current.value)
    db.add(refund)
    await transition(db, payment, PaymentStatus.REFUND_PENDING, "ADMIN", "Refund request admin dibuat")
    db.add(AdminAudit(actor_id=actor_id, action="REFUND_REQUESTED", resource_id=str(refund.id), reason=reason, occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return refund, payment


async def _locked_refund(db, refund_id):
    row = (await db.execute(select(Refund, PaymentTransaction).join(PaymentTransaction, PaymentTransaction.id == Refund.payment_id)
                            .where(Refund.id == refund_id).with_for_update())).first()
    if not row:
        raise AppError("REFUND_NOT_FOUND", "Refund tidak ditemukan", 404)
    return row


async def approve_refund(db, actor_id, refund_id, expected_version):
    refund, payment = await _locked_refund(db, refund_id)
    if refund.version != expected_version:
        raise AppError("VERSION_CONFLICT", "Refund sudah berubah, muat ulang data", 409)
    if refund.status != "REQUESTED":
        raise AppError("REFUND_NOT_PENDING", "Refund tidak berada pada status REQUESTED", 409)
    if refund.requested_by_admin == actor_id:
        raise AppError("REFUND_SELF_APPROVAL", "Pengaju refund tidak boleh menyetujui refund sendiri", 403)
    now = datetime.now(timezone.utc)
    refund.status, refund.approved_by, refund.approved_at, refund.version = "APPROVED", actor_id, now, refund.version + 1
    db.add(AdminAudit(actor_id=actor_id, action="REFUND_APPROVED", resource_id=str(refund.id), reason="Approval internal; menunggu worker provider", occurred_at=now))
    await db.commit()
    return refund, payment


async def reject_refund(db, actor_id, refund_id, expected_version, reason):
    refund, payment = await _locked_refund(db, refund_id)
    if refund.version != expected_version:
        raise AppError("VERSION_CONFLICT", "Refund sudah berubah, muat ulang data", 409)
    if refund.status != "REQUESTED":
        raise AppError("REFUND_NOT_PENDING", "Refund tidak berada pada status REQUESTED", 409)
    now = datetime.now(timezone.utc)
    refund.status, refund.rejected_by, refund.rejected_at, refund.rejection_reason, refund.version = "REJECTED", actor_id, now, reason, refund.version + 1
    if payment.status == PaymentStatus.REFUND_PENDING and refund.payment_status_before:
        previous = PaymentStatus(refund.payment_status_before)
        payment.status = previous
        db.add(PaymentStatusHistory(payment_id=payment.id, from_status=PaymentStatus.REFUND_PENDING.value, to_status=previous.value, source="ADMIN", reason="Refund ditolak"))
    db.add(AdminAudit(actor_id=actor_id, action="REFUND_REJECTED", resource_id=str(refund.id), reason=reason, occurred_at=now))
    await db.commit()
    return refund, payment
