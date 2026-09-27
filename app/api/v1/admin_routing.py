from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import enabled, require
from app.core.database import get_db
from app.schemas.admin_routing import (FeatureFlagUpsert, MerchantAccountCreate, MerchantAccountUpdate,
    OrganizerCreate, OrganizerUpdate, PaymentChannelCreate, PaymentChannelUpdate, RoutingRuleCreate, RoutingRuleUpdate)
from app.services.admin_routing_service import (create_channel, create_merchant, create_routing, list_rows,
    create_organizer, update_channel, update_merchant, update_organizer, update_routing, upsert_flag, _view)
from app.models.routing import FeatureFlag, MerchantAccount, Organizer, PaymentChannel, RoutingRule

router = APIRouter(prefix="/admin/clients/{client_id}", tags=["Admin Routing"], dependencies=[Depends(enabled)])


async def _list(client_id, model, db):
    return {"data": [_view(r) for r in await list_rows(db, client_id, model)]}


@router.get("/merchant-accounts")
async def merchant_list(client_id: UUID, identity=Depends(require("admin.routing.read")), db: AsyncSession = Depends(get_db)):
    return await _list(client_id, MerchantAccount, db)


@router.get("/organizers")
async def organizer_list(client_id: UUID, identity=Depends(require("admin.routing.read")), db: AsyncSession = Depends(get_db)):
    return await _list(client_id, Organizer, db)


@router.post("/organizers", status_code=201)
async def organizer_create(client_id: UUID, payload: OrganizerCreate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await create_organizer(db, identity[0].id, client_id, payload)}


@router.patch("/organizers/{organizer_id}")
async def organizer_update(client_id: UUID, organizer_id: UUID, payload: OrganizerUpdate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_organizer(db, identity[0].id, client_id, organizer_id, payload)}


@router.post("/merchant-accounts", status_code=201)
async def merchant_create(client_id: UUID, payload: MerchantAccountCreate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await create_merchant(db, identity[0].id, client_id, payload)}


@router.patch("/merchant-accounts/{account_id}")
async def merchant_update(client_id: UUID, account_id: UUID, payload: MerchantAccountUpdate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_merchant(db, identity[0].id, client_id, account_id, payload)}


@router.get("/payment-channels")
async def channel_list(client_id: UUID, identity=Depends(require("admin.routing.read")), db: AsyncSession = Depends(get_db)):
    return await _list(client_id, PaymentChannel, db)


@router.post("/payment-channels", status_code=201)
async def channel_create(client_id: UUID, payload: PaymentChannelCreate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await create_channel(db, identity[0].id, client_id, payload)}


@router.patch("/payment-channels/{channel_id}")
async def channel_update(client_id: UUID, channel_id: UUID, payload: PaymentChannelUpdate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_channel(db, identity[0].id, client_id, channel_id, payload)}


@router.get("/routing-rules")
async def routing_list(client_id: UUID, identity=Depends(require("admin.routing.read")), db: AsyncSession = Depends(get_db)):
    return await _list(client_id, RoutingRule, db)


@router.post("/routing-rules", status_code=201)
async def routing_create(client_id: UUID, payload: RoutingRuleCreate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await create_routing(db, identity[0].id, client_id, payload)}


@router.patch("/routing-rules/{rule_id}")
async def routing_update(client_id: UUID, rule_id: UUID, payload: RoutingRuleUpdate, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await update_routing(db, identity[0].id, client_id, rule_id, payload)}


@router.get("/feature-flags")
async def flag_list(client_id: UUID, identity=Depends(require("admin.routing.read")), db: AsyncSession = Depends(get_db)):
    return await _list(client_id, FeatureFlag, db)


@router.put("/feature-flags")
async def flag_upsert(client_id: UUID, payload: FeatureFlagUpsert, identity=Depends(require("admin.routing.manage")), db: AsyncSession = Depends(get_db)):
    return {"data": await upsert_flag(db, identity[0].id, client_id, payload)}
