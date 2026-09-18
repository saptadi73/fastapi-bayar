import hmac
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_security import COOKIE_NAME, ROLES, csrf_for, digest
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.models.admin import AdminAudit, AdminSession, AdminUser
from app.schemas.admin import AdminLogin
from app.services.admin_service import authenticate, login


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
    return user, session


def require(permission):
    async def dependency(identity=Depends(principal)):
        if permission not in ROLES.get(identity[0].role, set()):
            raise AppError("ADMIN_FORBIDDEN", "Permission admin tidak mencukupi", 403)
        return identity
    return dependency


def profile(user):
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name,
            "active": user.active, "role": user.role, "version": user.version}


@router.post("/auth/login")
async def sign_in(payload: AdminLogin, request: Request, response: Response,
                  db: AsyncSession = Depends(get_db)):
    check_origin(request)
    token, user, session = await login(db, str(payload.identifier), payload.password.get_secret_value(),
                                      request.client.host if request.client else "unknown",
                                      request.cookies.get(COOKIE_NAME))
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=settings.public_base_url.startswith("https://"),
                        samesite="lax", path=settings.api_prefix + "/admin",
                        max_age=settings.admin_session_ttl_seconds)
    return {"data": {"status": "authenticated", "user": profile(user),
                     "csrf_token": csrf_for(token), "session_expires_at": session.expires_at.isoformat()}}


@router.get("/auth/me")
async def me(request: Request, identity=Depends(principal)):
    user, session = identity
    return {"data": {"user": profile(user), "roles": [user.role],
                     "permissions": sorted(ROLES.get(user.role, set())),
                     "access_scope": {"all_clients": True, "client_ids": []},
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


@router.get("/users")
async def users(identity=Depends(require("admin.users.read")), db: AsyncSession = Depends(get_db),
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = (await db.scalars(select(AdminUser).order_by(AdminUser.email).limit(limit).offset(offset))).all()
    return {"data": [profile(row) for row in rows], "meta": {"limit": limit, "offset": offset}}


@router.get("/roles")
async def roles(identity=Depends(require("admin.roles.read"))):
    return {"data": [{"code": role, "permissions": sorted(permissions)} for role, permissions in ROLES.items()]}


@router.get("/audit")
async def audit(identity=Depends(require("admin.audit.read")), db: AsyncSession = Depends(get_db),
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = (await db.scalars(select(AdminAudit).order_by(AdminAudit.occurred_at.desc(), AdminAudit.id)
                            .limit(limit).offset(offset))).all()
    return {"data": [{"id": str(row.id), "actor_id": str(row.actor_id) if row.actor_id else None,
                      "action": row.action, "resource_id": row.resource_id, "reason": row.reason,
                      "occurred_at": row.occurred_at.isoformat()} for row in rows],
            "meta": {"limit": limit, "offset": offset}}
