import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.admin_security import digest, hash_password, verify_password
from app.core.errors import AppError
from app.models.admin import AdminAudit, AdminInvitation, AdminPasswordReset, AdminSession, AdminUser


async def invite(db: AsyncSession, actor_id, payload):
    email = str(payload.email).lower()
    if await db.scalar(select(AdminUser).where(AdminUser.email == email)):
        raise AppError("ADMIN_EMAIL_EXISTS", "Email admin sudah terdaftar", 409)
    token = secrets.token_urlsafe(32)
    row = AdminInvitation(token_hash=digest("invite:" + token), email=email, display_name=payload.display_name,
                          role=payload.role, expires_at=datetime.now(timezone.utc) + timedelta(hours=payload.expires_hours),
                          created_by=actor_id)
    db.add(row)
    db.add(AdminAudit(actor_id=actor_id, action="ADMIN_INVITATION_CREATED", resource_id=str(row.id),
                      reason=payload.reason, occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"invitation_id": str(row.id), "token": token, "expires_at": row.expires_at.isoformat()}


async def accept_invitation(db: AsyncSession, payload):
    now = datetime.now(timezone.utc)
    row = await db.scalar(select(AdminInvitation).where(AdminInvitation.token_hash == digest("invite:" + payload.token)).with_for_update())
    if not row or row.accepted_at or row.expires_at <= now:
        raise AppError("ADMIN_INVITATION_INVALID", "Invitation tidak valid atau sudah kedaluwarsa", 400)
    if await db.scalar(select(AdminUser).where(AdminUser.email == row.email)):
        raise AppError("ADMIN_EMAIL_EXISTS", "Email admin sudah terdaftar", 409)
    user = AdminUser(email=row.email, display_name=row.display_name, role=row.role,
                     password_hash=await run_in_threadpool(hash_password, payload.new_password.get_secret_value()),
                     force_password_change=False)
    db.add(user); row.accepted_at = now
    await db.flush()
    db.add(AdminAudit(actor_id=user.id, action="ADMIN_INVITATION_ACCEPTED", resource_id=str(user.id), occurred_at=now))
    await db.commit()
    return user


async def create_reset(db: AsyncSession, actor_id, user_id, reason):
    user = await db.get(AdminUser, user_id)
    if not user: raise AppError("ADMIN_USER_NOT_FOUND", "User tidak ditemukan", 404)
    token = secrets.token_urlsafe(32); now = datetime.now(timezone.utc)
    db.add(AdminPasswordReset(token_hash=digest("reset:" + token), user_id=user.id, expires_at=now + timedelta(hours=1)))
    db.add(AdminAudit(actor_id=actor_id, action="ADMIN_PASSWORD_RESET_CREATED", resource_id=str(user.id), reason=reason, occurred_at=now))
    await db.commit()
    return {"token": token, "expires_at": (now + timedelta(hours=1)).isoformat()}


async def confirm_reset(db: AsyncSession, payload):
    now = datetime.now(timezone.utc)
    row = await db.scalar(select(AdminPasswordReset).where(AdminPasswordReset.token_hash == digest("reset:" + payload.token), AdminPasswordReset.used_at.is_(None)).with_for_update())
    if not row or row.expires_at <= now: raise AppError("ADMIN_PASSWORD_RESET_INVALID", "Token reset tidak valid atau kedaluwarsa", 400)
    user = await db.scalar(select(AdminUser).where(AdminUser.id == row.user_id).with_for_update())
    if not user or not user.active: raise AppError("ADMIN_USER_NOT_FOUND", "User tidak ditemukan", 404)
    user.password_hash = await run_in_threadpool(hash_password, payload.new_password.get_secret_value())
    user.force_password_change = False; user.version += 1; row.used_at = now
    await db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))
    db.add(AdminAudit(actor_id=user.id, action="ADMIN_PASSWORD_RESET_COMPLETED", resource_id=str(user.id), occurred_at=now))
    await db.commit()
    return {"status": "password_reset"}


async def change_password(db: AsyncSession, user, session, payload):
    if not await run_in_threadpool(verify_password, payload.current_password.get_secret_value(), user.password_hash):
        raise AppError("ADMIN_PASSWORD_INVALID", "Password saat ini tidak valid", 401)
    user.password_hash = await run_in_threadpool(hash_password, payload.new_password.get_secret_value())
    user.force_password_change = False; user.version += 1
    session.reauthenticated_at = datetime.now(timezone.utc)
    db.add(AdminAudit(actor_id=user.id, action="ADMIN_PASSWORD_CHANGED", resource_id=str(user.id), reason=payload.reason, occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"status": "password_changed"}
