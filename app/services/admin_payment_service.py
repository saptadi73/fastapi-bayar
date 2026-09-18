"""Read-only ledger views; explicit fields avoid exposing gateway/browser credentials."""
from sqlalchemy import select
from app.core.errors import AppError
from app.models.payment import PaymentTransaction, PaymentAttempt, PaymentStatusHistory


def payment_view(p):
    return {"id": str(p.id), "payment_no": p.payment_no, "client_id": str(p.client_id),
            "client_name": p.client_name, "service_id": str(p.service_id),
            "event_id": p.event_id, "event_name": p.event_name,
            "reference_id": p.external_reference, "amount": p.amount, "currency": p.currency,
            "status": p.status.value, "created_at": p.created_at.isoformat(),
            "expires_at": p.expires_at.isoformat() if p.expires_at else None}


def page(rows, serializer, limit, offset):
    return {"data": [serializer(row) for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}


async def get_payment(db, payment_id):
    payment = await db.get(PaymentTransaction, payment_id)
    if payment is None:
        raise AppError("PAYMENT_NOT_FOUND", "Payment tidak ditemukan", 404)
    return payment


async def list_payments(db, *, client_id, service_id, event_id, status, reference_id,
                        created_from, created_to, limit, offset):
    if event_id is not None and client_id is None:
        raise AppError("CLIENT_FILTER_REQUIRED", "Filter event_id wajib disertai client_id", 422)
    if created_from and created_to and created_from >= created_to:
        raise AppError("INVALID_DATE_RANGE", "created_from harus sebelum created_to", 422)
    query = select(PaymentTransaction)
    for column, value in ((PaymentTransaction.client_id, client_id), (PaymentTransaction.service_id, service_id),
                          (PaymentTransaction.event_id, event_id), (PaymentTransaction.status, status),
                          (PaymentTransaction.external_reference, reference_id)):
        if value is not None:
            query = query.where(column == value)
    if created_from:
        query = query.where(PaymentTransaction.created_at >= created_from)
    if created_to:
        query = query.where(PaymentTransaction.created_at < created_to)
    rows = list((await db.scalars(query.order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
                                 .limit(limit + 1).offset(offset))).all())
    return page(rows, payment_view, limit, offset)


async def history(db, payment_id, limit, offset):
    await get_payment(db, payment_id)
    rows = list((await db.scalars(select(PaymentStatusHistory).where(PaymentStatusHistory.payment_id == payment_id)
                                 .order_by(PaymentStatusHistory.occurred_at, PaymentStatusHistory.id)
                                 .limit(limit + 1).offset(offset))).all())
    return page(rows, lambda h: {"id": str(h.id), "from_status": h.from_status, "to_status": h.to_status,
                                "source": h.source, "occurred_at": h.occurred_at.isoformat()}, limit, offset)


async def attempts(db, payment_id, limit, offset):
    await get_payment(db, payment_id)
    rows = list((await db.scalars(select(PaymentAttempt).where(PaymentAttempt.payment_id == payment_id)
                                 .order_by(PaymentAttempt.attempt_no).limit(limit + 1).offset(offset))).all())
    return page(rows, lambda a: {"id": str(a.id), "attempt_no": a.attempt_no, "gateway": a.gateway,
                                "gateway_order_id": a.gateway_order_id, "channel_code": a.channel_code,
                                "status": a.status}, limit, offset)
