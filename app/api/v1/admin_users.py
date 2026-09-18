from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, profile, require
from app.core.database import get_db
from app.schemas.admin_user import CreateAdminUser, UpdateAdminUser, RevokeUserSessions
from app.services.admin_user_service import create_user, update_user, revoke_sessions

router = APIRouter(prefix="/admin/users", tags=["Admin Users"], dependencies=[Depends(enabled)])


@router.post("", status_code=201)
async def create(payload: CreateAdminUser, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    user = await create_user(db, identity[0].id, identity[1].token_hash, payload)
    return {"data": profile(user)}


@router.patch("/{user_id}")
async def update(user_id: UUID, payload: UpdateAdminUser, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    user = await update_user(db, identity[0].id, identity[1].token_hash, user_id, payload)
    return {"data": profile(user)}


@router.post("/{user_id}/revoke-sessions")
async def revoke(user_id: UUID, payload: RevokeUserSessions, identity=Depends(require("admin.users.manage")), db: AsyncSession = Depends(get_db)):
    user = await revoke_sessions(db, identity[0].id, identity[1].token_hash, user_id, payload)
    return {"data": {"id": str(user.id), "version": user.version, "status": "sessions_revoked"}}
