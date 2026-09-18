from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.models.payment import Service
from app.schemas.admin_service import CreateService, UpdateService
from app.services.admin_client_service import find_client
from app.services.admin_service_management import service_view, find_service, create_service, update_service

router = APIRouter(prefix="/admin/clients/{client_id}/services", tags=["Admin Services"],
                   dependencies=[Depends(enabled)])


@router.get("")
async def listing(client_id: UUID, identity=Depends(require("admin.services.read")), db: AsyncSession = Depends(get_db),
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    await find_client(db, client_id)
    rows = (await db.scalars(select(Service).where(Service.client_id == client_id)
                            .order_by(Service.code).limit(limit).offset(offset))).all()
    return {"data": [service_view(row) for row in rows], "meta": {"limit": limit, "offset": offset}}


@router.get("/{service_id}")
async def detail(client_id: UUID, service_id: UUID, identity=Depends(require("admin.services.read")),
                 db: AsyncSession = Depends(get_db)):
    await find_client(db, client_id)
    return {"data": service_view(await find_service(db, client_id, service_id))}


@router.post("", status_code=201)
async def create(client_id: UUID, payload: CreateService, identity=Depends(require("admin.services.manage")),
                 db: AsyncSession = Depends(get_db)):
    return {"data": await create_service(db, identity[0].id, client_id, payload)}


@router.patch("/{service_id}")
async def update(client_id: UUID, service_id: UUID, payload: UpdateService,
                 identity=Depends(require("admin.services.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_service(db, identity[0].id, client_id, service_id, payload)}
