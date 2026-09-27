import hmac
import re
from uuid import UUID
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_security import COOKIE_NAME, ROLES, csrf_for, digest
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.models.admin import AdminAudit, AdminClientAssignment, AdminRole, AdminSession, AdminUser
from app.schemas.admin import AdminLogin, MfaCode, Reauthenticate
from app.schemas.admin_user import InvitationAccept, PasswordResetConfirm
from app.schemas.admin_role import RoleUpdate
from app.services.admin_role_service import available_permissions, update_role
from app.services.admin_recovery_service import accept_invitation, confirm_reset
from app.services.admin_service import authenticate, begin_mfa, confirm_mfa, login, reauthenticate


def enabled():
    if not get_settings().admin_enabled:
        raise AppError("ADMIN_DISABLED", "Admin API belum diaktifkan", 503)


router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(enabled)])


def check_origin(request: Request):
    parsed = urlsplit(get_settings().public_base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if request.headers.get("origin") != origin:
        raise AppError("ADMIN_ORIGIN_DENIED", "Origin admin tidak diizinkan", 403)


async def principal(request: Request, db: AsyncSession = Depends(get_db)):
    user, session = await authenticate(db, request.cookies.get(COOKIE_NAME))
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(supplied.encode(), csrf_for(request.cookies[COOKIE_NAME]).encode()):
            raise AppError("ADMIN_CSRF_INVALID", "CSRF token tidak valid", 403)
    if user.force_password_change and request.url.path not in {
        get_settings().api_prefix + "/admin/users/password-change",
        get_settings().api_prefix + "/admin/auth/logout",
        get_settings().api_prefix + "/admin/auth/me",
    }:
        raise AppError("ADMIN_PASSWORD_CHANGE_REQUIRED", "Password wajib diganti sebelum melanjutkan", 403)
    permissions = await db.scalar(select(AdminRole.permissions_json).where(AdminRole.code == user.role, AdminRole.active.is_(True)))
    effective_permissions = set(permissions or ROLES.get(user.role, set()))
    client_match = re.search(r"/clients/([0-9a-fA-F-]{36})(?:/|$)", request.url.path)
    if client_match and user.role != "SUPER_ADMIN":
        assigned = await db.scalar(select(AdminClientAssignment.id).where(
            AdminClientAssignment.user_id == user.id,
            AdminClientAssignment.client_id == UUID(client_match.group(1)),
            AdminClientAssignment.active.is_(True),
        ))
        if assigned is None:
            raise AppError("ADMIN_CLIENT_FORBIDDEN", "Admin tidak ditugaskan ke client ini", 403)
    return user, session, effective_permissions


def require(permission):
    async def dependency(identity=Depends(principal)):
        if permission not in identity[2]:
            raise AppError("ADMIN_FORBIDDEN", "Permission admin tidak mencukupi", 403)
        return identity
    return dependency


def profile(user):
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name,
            "active": user.active, "role": user.role, "version": user.version,
            "force_password_change": user.force_password_change, "mfa_enabled": user.mfa_enabled}


@router.post("/auth/login")
async def sign_in(payload: AdminLogin, request: Request, response: Response,
                  db: AsyncSession = Depends(get_db)):
    check_origin(request)
    token, user, session = await login(db, str(payload.identifier), payload.password.get_secret_value(),
                                      request.client.host if request.client else "unknown",
                                      request.cookies.get(COOKIE_NAME), payload.otp)
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=settings.public_base_url.startswith("https://"),
                        samesite="lax", path=settings.api_prefix + "/admin",
                        max_age=settings.admin_session_ttl_seconds)
    return {"data": {"status": "authenticated", "user": profile(user),
                     "csrf_token": csrf_for(token), "session_expires_at": session.expires_at.isoformat()}}


@router.get("/auth/me")
async def me(request: Request, identity=Depends(principal), db: AsyncSession = Depends(get_db)):
    user, session, permissions = identity
    assignments = []
    if user.role != "SUPER_ADMIN":
        assignments = [str(item) for item in (await db.scalars(select(AdminClientAssignment.client_id).where(AdminClientAssignment.user_id == user.id, AdminClientAssignment.active.is_(True)))).all()]
    return {"data": {"user": profile(user), "roles": [user.role],
                     "permissions": sorted(permissions),
                     "access_scope": {"all_clients": user.role == "SUPER_ADMIN", "client_ids": assignments},
                     "session_expires_at": session.expires_at.isoformat(),
                     "csrf_token": csrf_for(request.cookies[COOKIE_NAME])}}


@router.post("/auth/logout")
async def sign_out(request: Request, response: Response, identity=Depends(principal),
                   db: AsyncSession = Depends(get_db)):
    await db.execute(delete(AdminSession).where(AdminSession.token_hash == digest(request.cookies[COOKIE_NAME])))
    db.add(AdminAudit(actor_id=identity[0].id, action="LOGOUT", occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    response.delete_cookie(COOKIE_NAME, path=get_settings().api_prefix + "/admin")
    return {"data": {"status": "logged_out"}}


@router.post("/auth/mfa/enroll")
async def mfa_enroll(identity=Depends(principal), db: AsyncSession = Depends(get_db)):
    return {"data": await begin_mfa(db, identity[0])}


@router.post("/auth/mfa/confirm")
async def mfa_confirm(payload: MfaCode, identity=Depends(principal), db: AsyncSession = Depends(get_db)):
    return {"data": {"recovery_codes": await confirm_mfa(db, identity[0].id, identity[0], payload.code)}}


@router.post("/auth/reauthenticate")
async def auth_reauthenticate(payload: Reauthenticate, identity=Depends(principal), db: AsyncSession = Depends(get_db)):
    return {"data": await reauthenticate(db, identity[0], identity[1], payload.password.get_secret_value())}


@router.post("/auth/invitations/accept")
async def invitation_accept(payload: InvitationAccept, db: AsyncSession = Depends(get_db)):
    return {"data": profile(await accept_invitation(db, payload))}


@router.post("/auth/password-reset/confirm")
async def password_reset_confirm(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    return {"data": await confirm_reset(db, payload)}


@router.get("/users")
async def users(identity=Depends(require("admin.users.read")), db: AsyncSession = Depends(get_db),
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = list((await db.scalars(select(AdminUser).order_by(AdminUser.email).limit(limit + 1).offset(offset))).all())
    return {"data": [profile(row) for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}


@router.get("/roles")
async def roles(identity=Depends(require("admin.roles.read")), db: AsyncSession = Depends(get_db)):
    rows = list((await db.scalars(select(AdminRole).where(AdminRole.active.is_(True)).order_by(AdminRole.code))).all())
    if rows:
        return {"data": [{"code": row.code, "display_name": row.display_name, "permissions": row.permissions_json, "version": row.version} for row in rows]}
    return {"data": [{"code": role, "display_name": role, "permissions": sorted(permissions), "version": 1} for role, permissions in ROLES.items()]}


@router.patch("/roles/{code}")
async def role_update(code: str, payload: RoleUpdate, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_role(db, identity[0].id, code, payload)}


@router.get("/audit")
async def audit(identity=Depends(require("admin.audit.read")), db: AsyncSession = Depends(get_db),
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = list((await db.scalars(select(AdminAudit).order_by(AdminAudit.occurred_at.desc(), AdminAudit.id)
                            .limit(limit + 1).offset(offset))).all())
    return {"data": [{"id": str(row.id), "actor_id": str(row.actor_id) if row.actor_id else None,
                      "action": row.action, "resource_id": row.resource_id, "reason": row.reason,
                      "occurred_at": row.occurred_at.isoformat()} for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}
