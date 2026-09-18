import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.admin_security import digest, hash_password, verify_password
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.admin import AdminAudit, AdminLoginBucket, AdminSession, AdminUser

DUMMY_PASSWORD = hash_password("not-a-real-admin-password")


async def login(db: AsyncSession, identifier: str, password: str, peer: str, old_token: str | None):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    seconds = settings.admin_login_window_seconds
    window = int(now.timestamp()) // seconds
    # Atomic shared PostgreSQL counter, independent from authentication transaction.
    statement = insert(AdminLoginBucket).values(key=digest(peer), window=window, count=1)
    statement = statement.on_conflict_do_update(
        index_elements=[AdminLoginBucket.key, AdminLoginBucket.window],
        set_={"count": AdminLoginBucket.count + 1}).returning(AdminLoginBucket.count)
    count = await db.scalar(statement)
    await db.commit()
    if count > settings.admin_login_limit:
        raise AppError("ADMIN_LOGIN_RATE_LIMIT", "Terlalu banyak percobaan login", 429,
                       {"retry_after": seconds - int(now.timestamp()) % seconds})
    user = await db.scalar(select(AdminUser).where(AdminUser.email == identifier.strip().lower()).with_for_update())
    valid = await run_in_threadpool(verify_password, password, user.password_hash if user else DUMMY_PASSWORD)
    if not user or not valid or not user.active:
        db.add(AdminAudit(actor_id=None, action="LOGIN_FAILED", occurred_at=now))
        await db.commit()
        raise AppError("ADMIN_LOGIN_FAILED", "Identitas atau password tidak valid", 401)
    if old_token:
        await db.execute(delete(AdminSession).where(AdminSession.token_hash == digest(old_token)))
    token = secrets.token_urlsafe(32)
    session = AdminSession(token_hash=digest(token), user_id=user.id,
                           expires_at=now + timedelta(seconds=settings.admin_session_ttl_seconds),
                           last_seen_at=now)
    db.add(session)
    db.add(AdminAudit(actor_id=user.id, action="LOGIN_SUCCEEDED", occurred_at=now))
    await db.commit()
    return token, user, session


async def authenticate(db: AsyncSession, token: str | None):
    if not token or len(token) != 43:
        raise AppError("ADMIN_SESSION_REQUIRED", "Login admin diperlukan", 401)
    row = (await db.execute(select(AdminSession, AdminUser).join(AdminUser)
                           .where(AdminSession.token_hash == digest(token))
                           .with_for_update(of=AdminSession))).first()
    now = datetime.now(timezone.utc)
    if not row:
        raise AppError("ADMIN_SESSION_INVALID", "Sesi admin tidak valid", 401)
    session, user = row
    if (not user.active or session.expires_at <= now or
        session.last_seen_at + timedelta(seconds=get_settings().admin_idle_ttl_seconds) <= now):
        await db.delete(session)
        await db.commit()
        raise AppError("ADMIN_SESSION_INVALID", "Sesi admin tidak valid", 401)
    session.last_seen_at = now
    await db.commit()
    return user, session
