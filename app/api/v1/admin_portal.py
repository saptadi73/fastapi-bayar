from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.core.errors import AppError
from app.models.payment import Client
from app.models.admin import AdminAudit
from app.models.portal_identity import PortalEvent, PortalUser
from app.schemas.admin_portal import CreatePortalUser, DeletePortalUser, UpdatePortalUser
from app.services.admin_portal_service import create_user, delete_user, update_user
from datetime import datetime, timezone

router = APIRouter(prefix="/admin/clients/{client_id}/events", tags=["Admin Portal"],
                   dependencies=[Depends(enabled)])
users_router = APIRouter(prefix="/admin/clients/{client_id}/portal-users", tags=["Admin Portal"],
                         dependencies=[Depends(enabled)])


async def client_exists(db: AsyncSession, client_id: UUID) -> None:
    if await db.get(Client, client_id) is None:
        raise AppError("CLIENT_NOT_FOUND", "Client tidak ditemukan", 404)


def event_view(event: PortalEvent) -> dict:
    return {"id": str(event.id), "client_id": str(event.client_id),
            "event_id": event.event_id, "name": event.name}


@router.get("")
async def listing(client_id: UUID, identity=Depends(require("admin.payments.read")),
                  db: AsyncSession = Depends(get_db),
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    await client_exists(db, client_id)
    rows = (await db.scalars(select(PortalEvent).where(PortalEvent.client_id == client_id)
                            .order_by(PortalEvent.event_id, PortalEvent.id)
                            .limit(limit + 1).offset(offset))).all()
    return {"data": [event_view(row) for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}


@router.get("/{event_id}")
async def detail(client_id: UUID, event_id: str, identity=Depends(require("admin.payments.read")),
                 db: AsyncSession = Depends(get_db)):
    await client_exists(db, client_id)
    event = await db.scalar(select(PortalEvent).where(PortalEvent.client_id == client_id,
                                                       PortalEvent.event_id == event_id))
    if event is None:
        raise AppError("PORTAL_EVENT_NOT_FOUND", "Event portal tidak ditemukan", 404)
    return {"data": event_view(event)}


def user_view(user: PortalUser) -> dict:
    return {"id": str(user.id), "client_id": str(user.client_id),
            "email": user.email, "name": user.name, "version": user.version}


@users_router.get("")
async def user_listing(client_id: UUID, identity=Depends(require("admin.portal_users.read")),
                       db: AsyncSession = Depends(get_db),
                       limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    await client_exists(db, client_id)
    rows = (await db.scalars(select(PortalUser).where(PortalUser.client_id == client_id)
                            .order_by(PortalUser.email, PortalUser.id)
                            .limit(limit + 1).offset(offset))).all()
    db.add(AdminAudit(actor_id=identity[0].id, action="PORTAL_USERS_VIEWED",
                      resource_id=str(client_id), reason="pii_read=true",
                      occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"data": [user_view(row) for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit,
                     "pii": True}}


@users_router.post("", status_code=201)
async def create_portal_user(client_id: UUID, payload: CreatePortalUser,
                             identity=Depends(require("admin.portal_users.manage")),
                             db: AsyncSession = Depends(get_db)):
    return {"data": await create_user(db, identity[0].id, client_id, payload)}


@users_router.patch("/{user_id}")
async def update_portal_user(client_id: UUID, user_id: UUID, payload: UpdatePortalUser,
                             identity=Depends(require("admin.portal_users.manage")),
                             db: AsyncSession = Depends(get_db)):
    return {"data": await update_user(db, identity[0].id, client_id, user_id, payload)}


@users_router.delete("/{user_id}")
async def delete_portal_user(client_id: UUID, user_id: UUID, payload: DeletePortalUser,
                             identity=Depends(require("admin.portal_users.manage")),
                             db: AsyncSession = Depends(get_db)):
    return {"data": await delete_user(db, identity[0].id, client_id, user_id, payload)}
