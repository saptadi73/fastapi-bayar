import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.admin_security import hash_password
from app.core.errors import AppError
from app.models.admin import AdminAudit, AdminSession, AdminUser


async def authorize_write(db: AsyncSession, actor_id, session_hash):
    # All user mutations (including bootstrap) share one lock: protects last-super-admin invariant.
    await db.execute(text("SELECT pg_advisory_xact_lock(7011011)"))
    actor = await db.scalar(select(AdminUser).where(AdminUser.id == actor_id)
                            .with_for_update().execution_options(populate_existing=True))
    session = await db.get(AdminSession, session_hash, populate_existing=True)
    if not actor or not actor.active or actor.role != "SUPER_ADMIN":
        raise AppError("ADMIN_FORBIDDEN", "Permission admin tidak mencukupi", 403)
    if not session or session.user_id != actor_id or session.expires_at <= datetime.now(timezone.utc):
        raise AppError("ADMIN_SESSION_INVALID", "Sesi admin tidak valid", 401)


async def find_user(db, user_id, expected):
    user = await db.scalar(select(AdminUser).where(AdminUser.id == user_id)
                           .with_for_update().execution_options(populate_existing=True))
    if user is None:
        raise AppError("ADMIN_USER_NOT_FOUND", "User tidak ditemukan", 404)
    if user.version != expected:
        raise AppError("ADMIN_USER_VERSION_CONFLICT", "User telah berubah; muat ulang", 409)
    return user


def record(db, actor_id, user, action, reason):
    db.add(AdminAudit(actor_id=actor_id, action=action, resource_id=str(user.id),
                      reason=reason, occurred_at=datetime.now(timezone.utc)))


async def create_user(db, actor_id, session_hash, payload):
    encoded = await run_in_threadpool(hash_password, payload.password.get_secret_value())
    await authorize_write(db, actor_id, session_hash)
    user_id = await db.scalar(insert(AdminUser).values(
        id=uuid.uuid4(), email=str(payload.email).strip().lower(), display_name=payload.display_name,
        role=payload.role, active=payload.active, password_hash=encoded, version=1,
        force_password_change=True,
    ).on_conflict_do_nothing(index_elements=[AdminUser.email]).returning(AdminUser.id))
    if user_id is None:
        raise AppError("ADMIN_EMAIL_EXISTS", "Email admin sudah terdaftar", 409)
    user = await db.get(AdminUser, user_id)
    record(db, actor_id, user, "ADMIN_USER_CREATED", payload.reason)
    await db.commit()
    return user


async def update_user(db, actor_id, session_hash, user_id, payload):
    await authorize_write(db, actor_id, session_hash)
    user = await find_user(db, user_id, payload.expected_version)
    if user.active and user.role == "SUPER_ADMIN" and (not payload.active or payload.role != "SUPER_ADMIN"):
        others = await db.scalar(select(func.count()).select_from(AdminUser).where(
            AdminUser.active.is_(True), AdminUser.role == "SUPER_ADMIN", AdminUser.id != user.id))
        if not others:
            raise AppError("LAST_SUPER_ADMIN", "Super Admin aktif terakhir tidak boleh dinonaktifkan/diturunkan", 409)
    user.display_name, user.role, user.active = payload.display_name, payload.role, payload.active
    user.version += 1
    await db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))
    record(db, actor_id, user, "ADMIN_USER_UPDATED", payload.reason)
    await db.commit()
    return user


async def revoke_sessions(db, actor_id, session_hash, user_id, payload):
    await authorize_write(db, actor_id, session_hash)
    user = await find_user(db, user_id, payload.expected_version)
    user.version += 1
    await db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))
    record(db, actor_id, user, "ADMIN_SESSIONS_REVOKED", payload.reason)
    await db.commit()
    return user
