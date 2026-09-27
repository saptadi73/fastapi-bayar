"""Read-only ledger views; explicit fields avoid exposing gateway/browser credentials."""
import base64
import json
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import func, or_, select
from app.core.errors import AppError
from app.models.admin import AdminAudit
from app.models.payment import PaymentTransaction, PaymentAttempt, PaymentStatusHistory


def payment_view(p):
    return {"id": str(p.id), "payment_no": p.payment_no, "client_id": str(p.client_id),
            "client_name": p.client_name, "service_id": str(p.service_id),
            "event_id": p.event_id, "event_name": p.event_name,
            "reference_id": p.external_reference, "amount": p.amount, "currency": p.currency,
            "status": p.status.value, "created_at": p.created_at.isoformat(),
            "expires_at": p.expires_at.isoformat() if p.expires_at else None}


def page(rows, serializer, limit, offset, total_count=None):
    return {"data": [serializer(row) for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit,
                     **({"total_count": total_count} if total_count is not None else {})}}


async def get_payment(db, payment_id):
    payment = await db.get(PaymentTransaction, payment_id)
    if payment is None:
        raise AppError("PAYMENT_NOT_FOUND", "Payment tidak ditemukan", 404)
    return payment


async def list_payments(db, *, client_id, service_id, event_id, status, reference_id, search,
                        created_from, created_to, limit, offset):
    if event_id is not None and client_id is None:
        raise AppError("CLIENT_FILTER_REQUIRED", "Filter event_id wajib disertai client_id", 422)
    if created_from and created_to and created_from >= created_to:
        raise AppError("INVALID_DATE_RANGE", "created_from harus sebelum created_to", 422)
    query = select(PaymentTransaction)
    filters = []
    for column, value in ((PaymentTransaction.client_id, client_id), (PaymentTransaction.service_id, service_id),
                          (PaymentTransaction.event_id, event_id), (PaymentTransaction.status, status),
                          (PaymentTransaction.external_reference, reference_id)):
        if value is not None:
            filters.append(column == value)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(PaymentTransaction.payment_no.ilike(pattern),
                           PaymentTransaction.external_reference.ilike(pattern),
                           PaymentTransaction.event_id.ilike(pattern),
                           PaymentTransaction.event_name.ilike(pattern),
                           PaymentTransaction.client_name.ilike(pattern)))
    if created_from:
        filters.append(PaymentTransaction.created_at >= created_from)
    if created_to:
        filters.append(PaymentTransaction.created_at < created_to)
    query = query.where(*filters)
    total_count = await db.scalar(select(func.count(PaymentTransaction.id)).where(*filters))
    rows = list((await db.scalars(query.order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
                                 .limit(limit + 1).offset(offset))).all())
    return page(rows, payment_view, limit, offset, int(total_count or 0))


async def summary(db, *, actor_id, client_id, status, created_from, created_to):
    if created_from and created_to and created_from >= created_to:
        raise AppError("INVALID_DATE_RANGE", "created_from harus sebelum created_to", 422)
    filters = []
    for column, value in ((PaymentTransaction.client_id, client_id), (PaymentTransaction.status, status)):
        if value is not None:
            filters.append(column == value)
    if created_from:
        filters.append(PaymentTransaction.created_at >= created_from)
    if created_to:
        filters.append(PaymentTransaction.created_at < created_to)
    by_status = (await db.execute(select(PaymentTransaction.status, func.count(PaymentTransaction.id),
        func.coalesce(func.sum(PaymentTransaction.amount), 0)).where(*filters)
        .group_by(PaymentTransaction.status).order_by(PaymentTransaction.status))).all()
    by_client = (await db.execute(select(PaymentTransaction.client_id, PaymentTransaction.client_name,
        func.count(PaymentTransaction.id), func.coalesce(func.sum(PaymentTransaction.amount), 0)).where(*filters)
        .group_by(PaymentTransaction.client_id, PaymentTransaction.client_name)
        .order_by(func.sum(PaymentTransaction.amount).desc(), PaymentTransaction.client_id))).all()
    db.add(AdminAudit(actor_id=actor_id, action="PAYMENT_SUMMARY_VIEWED", resource_id="PAYMENT_SUMMARY",
                      reason=f"client_filter={bool(client_id)} status_filter={bool(status)}",
                      occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"data": {"by_status": [{"status": status.value if isinstance(status, PaymentStatus) else status,
                                      "payment_count": count, "amount": int(amount or 0)}
                                     for status, count, amount in by_status],
                     "by_client": [{"client_id": str(client_id), "client_name": client_name,
                                     "payment_count": count, "amount": int(amount or 0)}
                                    for client_id, client_name, count, amount in by_client]},
            "meta": {"client_id": str(client_id) if client_id else None, "status": status.value if status else None,
                     "created_from": created_from.isoformat() if created_from else None,
                     "created_to": created_to.isoformat() if created_to else None,
                     "currency": "IDR", "source": "payment_transactions"}}


async def export_payments(db, *, client_id, service_id, event_id, status, reference_id, search,
                          created_from, created_to, limit, actor_id, cursor=None, snapshot_at=None):
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
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(PaymentTransaction.payment_no.ilike(pattern),
                                PaymentTransaction.external_reference.ilike(pattern),
                                PaymentTransaction.event_id.ilike(pattern),
                                PaymentTransaction.event_name.ilike(pattern),
                                PaymentTransaction.client_name.ilike(pattern)))
    if created_from:
        query = query.where(PaymentTransaction.created_at >= created_from)
    if created_to:
        query = query.where(PaymentTransaction.created_at < created_to)
    if snapshot_at:
        query = query.where(PaymentTransaction.created_at <= snapshot_at)
    if cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode() + b"=" * (-len(cursor) % 4)))
            cursor_time = datetime.fromisoformat(decoded["created_at"])
            cursor_id = UUID(decoded["id"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_CURSOR", "Cursor export tidak valid", 422)
        query = query.where((PaymentTransaction.created_at < cursor_time) |
                            ((PaymentTransaction.created_at == cursor_time) & (PaymentTransaction.id < cursor_id)))
    rows = list((await db.scalars(query.order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
                                 .limit(limit + 1))).all())
    visible = rows[:limit]
    next_cursor = None
    if len(rows) > limit and visible:
        last = visible[-1]
        raw = json.dumps({"created_at": last.created_at.isoformat(), "id": str(last.id)}, separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    db.add(AdminAudit(actor_id=actor_id, action="PAYMENT_EXPORT_VIEWED", resource_id="PAYMENT_EXPORT",
                      reason=f"limit={limit} cursor={bool(cursor)} client_filter={bool(client_id)}",
                      occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"data": [payment_view(row) for row in rows[:limit]],
            "meta": {"limit": limit, "has_more": len(rows) > limit, "next_cursor": next_cursor,
                     "snapshot_at": snapshot_at.isoformat() if snapshot_at else datetime.now(timezone.utc).isoformat(),
                     "format": "json", "source": "payment_transactions"}}


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
