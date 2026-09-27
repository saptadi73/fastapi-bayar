from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.models.payment import Client
from app.schemas.admin_client import CreateClient, UpdateClient, RotateClientSecret, RevokeCheckouts
from app.services.admin_client_service import (client_view, create_client, find_client, update_client,
                                                rotate_secret, revoke_checkout_sessions)

router = APIRouter(prefix="/admin/clients", tags=["Admin Clients"], dependencies=[Depends(enabled)])


@router.get("")
async def listing(identity=Depends(require("admin.clients.read")), db: AsyncSession = Depends(get_db),
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = list((await db.scalars(select(Client).order_by(Client.code).limit(limit + 1).offset(offset))).all())
    return {"data": [client_view(row) for row in rows[:limit]],
            "meta": {"limit": limit, "offset": offset, "has_more": len(rows) > limit}}


@router.get("/{client_id}")
async def detail(client_id: UUID, identity=Depends(require("admin.clients.read")), db: AsyncSession = Depends(get_db)):
    return {"data": client_view(await find_client(db, client_id))}


@router.post("", status_code=201)
async def create(payload: CreateClient, identity=Depends(require("admin.clients.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await create_client(db, identity[0].id, payload)}


@router.patch("/{client_id}")
async def update(client_id: UUID, payload: UpdateClient, identity=Depends(require("admin.clients.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_client(db, identity[0].id, client_id, payload)}


@router.post("/{client_id}/rotate-secret")
async def rotate(client_id: UUID, payload: RotateClientSecret, identity=Depends(require("admin.clients.rotate_secret")), db: AsyncSession = Depends(get_db)):
    return {"data": await rotate_secret(db, identity[0].id, client_id, payload)}


@router.post("/{client_id}/revoke-checkouts")
async def revoke_checkouts(client_id: UUID, payload: RevokeCheckouts,
                           identity=Depends(require("admin.clients.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await revoke_checkout_sessions(db, identity[0].id, client_id, payload.reason)}
