"""Bounded retention maintenance; never deletes ledger or idempotency records."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import CheckoutSession, NonceRecord
from app.models.admin import AdminLoginBucket, AdminSession


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


async def cleanup_expired_nonces(db: AsyncSession, limit: int = 500) -> dict[str, int]:
    if not 1 <= limit <= 10000:
        raise ValueError("Cleanup limit must be between 1 and 10000")
    ids = list((await db.scalars(
        select(NonceRecord.id)
        .where(NonceRecord.expires_at <= datetime.now(timezone.utc))
        .order_by(NonceRecord.expires_at, NonceRecord.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )).all())
    if ids:
        await db.execute(delete(NonceRecord).where(NonceRecord.id.in_(ids)))
    await db.commit()
    return {"expired_nonces_deleted": len(ids)}


async def cleanup_admin_retention(db: AsyncSession, limit: int = 500, idle_ttl_seconds: int = 1800,
                                  login_window_seconds: int = 300) -> dict[str, int]:
    if not 1 <= limit <= 10000:
        raise ValueError("Cleanup limit must be between 1 and 10000")
    now = datetime.now(timezone.utc)
    session_ids = list((await db.scalars(select(AdminSession.token_hash)
        .where((AdminSession.expires_at <= now) | (AdminSession.last_seen_at <= now - timedelta(seconds=idle_ttl_seconds)))
        .order_by(AdminSession.expires_at, AdminSession.token_hash).limit(limit).with_for_update(skip_locked=True))).all())
    if session_ids:
        await db.execute(delete(AdminSession).where(AdminSession.token_hash.in_(session_ids)))
    cutoff = int(now.timestamp()) // login_window_seconds - 2
    bucket_keys = list((await db.execute(select(AdminLoginBucket.key, AdminLoginBucket.window)
        .where(AdminLoginBucket.window < cutoff).order_by(AdminLoginBucket.window)
        .limit(limit).with_for_update(skip_locked=True))).all())
    if bucket_keys:
        await db.execute(delete(AdminLoginBucket).where(
            tuple_(AdminLoginBucket.key, AdminLoginBucket.window).in_(bucket_keys)))
    await db.commit()
    return {"admin_sessions_deleted": len(session_ids), "admin_login_buckets_deleted": len(bucket_keys)}
