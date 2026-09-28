from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, principal, profile, require
from app.core.database import get_db
from app.schemas.admin_user import CreateAdminUser, InviteAdmin, PasswordChange, PasswordResetConfirm, RevokeUserSessions, UpdateAdminUser
from app.schemas.admin_role import ClientAssignment
from app.services.admin_user_service import create_user, update_user, revoke_sessions
from app.services.admin_recovery_service import accept_invitation, change_password, confirm_reset, create_reset, invite
from app.services.admin_role_service import assign_client

router = APIRouter(prefix="/admin/users", tags=["Admin Users"], dependencies=[Depends(enabled)])


@router.post("", status_code=201)
async def create(payload: CreateAdminUser, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    user = await create_user(db, identity[0].id, identity[1].token_hash, payload)
    return {"data": profile(user)}


@router.post("/invite", status_code=201)
async def invitation(payload: InviteAdmin, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await invite(db, identity[0].id, payload)}


@router.post("/password-change")
async def password_change(payload: PasswordChange, identity=Depends(principal), db: AsyncSession = Depends(get_db)):
    return {"data": await change_password(db, identity[0], identity[1], payload)}


@router.patch("/{user_id}")
async def update(user_id: UUID, payload: UpdateAdminUser, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    user = await update_user(db, identity[0].id, identity[1].token_hash, user_id, payload)
    return {"data": profile(user)}


@router.post("/{user_id}/revoke-sessions")
async def revoke(user_id: UUID, payload: RevokeUserSessions, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    user = await revoke_sessions(db, identity[0].id, identity[1].token_hash, user_id, payload)
    return {"data": {"id": str(user.id), "version": user.version, "status": "sessions_revoked"}}


@router.post("/{user_id}/clients")
async def assign(user_id: UUID, payload: ClientAssignment, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await assign_client(db, identity[0].id, user_id, payload)}


@router.post("/{user_id}/password-reset")
async def password_reset(user_id: UUID, payload: RevokeUserSessions, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await create_reset(db, identity[0].id, user_id, payload.reason)}


