"""Bounded retention maintenance; never deletes ledger or idempotency records."""
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import CheckoutSession


async def cleanup_expired_checkouts(db: AsyncSession, limit: int = 500) -> dict[str, int]:
    if not 1 <= limit <= 10000:
        raise ValueError("Cleanup limit must be between 1 and 10000")
    ids = list((await db.scalars(
        select(CheckoutSession.id)
        .where(CheckoutSession.expires_at <= datetime.now(timezone.utc))
        .order_by(CheckoutSession.expires_at, CheckoutSession.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )).all())
    if ids:
        await db.execute(delete(CheckoutSession).where(CheckoutSession.id.in_(ids)))
    await db.commit()
    return {"expired_checkouts_deleted": len(ids)}
