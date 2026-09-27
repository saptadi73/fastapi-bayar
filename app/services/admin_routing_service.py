from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.admin import AdminAudit
from app.models.payment import Client, Service
from app.models.routing import FeatureFlag, MerchantAccount, Organizer, PaymentChannel, RoutingRule


def _view(row):
    if isinstance(row, MerchantAccount):
        return {"id": str(row.id), "client_id": str(row.client_id), "code": row.code, "name": row.name,
                "gateway": row.gateway, "credential_ref": row.credential_ref, "active": row.active, "version": row.version}
    if isinstance(row, Organizer):
        return {"id": str(row.id), "client_id": str(row.client_id), "code": row.code, "name": row.name,
                "active": row.active, "version": row.version}
    if isinstance(row, PaymentChannel):
        return {"id": str(row.id), "merchant_account_id": str(row.merchant_account_id), "gateway": row.gateway,
                "channel_code": row.channel_code, "name": row.name, "active": row.active,
                "min_amount": row.min_amount, "max_amount": row.max_amount, "currencies": row.currencies, "version": row.version}
    if isinstance(row, RoutingRule):
        return {"id": str(row.id), "client_id": str(row.client_id), "service_id": str(row.service_id) if row.service_id else None,
                "event_id": row.event_id, "channel_code": row.channel_code, "merchant_account_id": str(row.merchant_account_id),
                "priority": row.priority, "active": row.active, "version": row.version}
    return {"id": str(row.id), "client_id": str(row.client_id), "key": row.key, "enabled": row.enabled,
            "config": row.config_json, "version": row.version}


async def _client(db, client_id):
    client = await db.get(Client, client_id)
    if not client:
        raise AppError("CLIENT_NOT_FOUND", "Client tidak ditemukan", 404)
    return client


def _audit(db, actor_id, row, action, reason, before=None):
    db.add(AdminAudit(actor_id=actor_id, action=action, resource_id=str(row.id), reason=reason,
                      details_json={"before": before, "after": _view(row)}, occurred_at=datetime.now(timezone.utc)))


async def list_rows(db, client_id, model):
    await _client(db, client_id)
    if model is MerchantAccount:
        query = select(model).where(model.client_id == client_id).order_by(model.code)
    elif model is RoutingRule:
        query = select(model).where(model.client_id == client_id).order_by(model.priority, model.id)
    elif model is FeatureFlag:
        query = select(model).where(model.client_id == client_id).order_by(model.key)
    elif model is Organizer:
        query = select(model).where(model.client_id == client_id).order_by(model.code)
    else:
        query = select(model).join(MerchantAccount).where(MerchantAccount.client_id == client_id).order_by(model.channel_code)
    return list((await db.scalars(query)).all())


async def create_merchant(db, actor_id, client_id, payload):
    await _client(db, client_id)
    exists = await db.scalar(select(MerchantAccount).where(MerchantAccount.client_id == client_id, MerchantAccount.code == payload.code))
    if exists: raise AppError("MERCHANT_ACCOUNT_EXISTS", "Kode merchant sudah digunakan client", 409)
    row = MerchantAccount(client_id=client_id, code=payload.code, name=payload.name, gateway=payload.gateway.upper(), credential_ref=payload.credential_ref, active=payload.active)
    db.add(row); await db.flush(); _audit(db, actor_id, row, "MERCHANT_ACCOUNT_CREATED", payload.reason); await db.commit(); return _view(row)


async def create_organizer(db, actor_id, client_id, payload):
    await _client(db, client_id)
    if await db.scalar(select(Organizer).where(Organizer.client_id == client_id, Organizer.code == payload.code)):
        raise AppError("ORGANIZER_EXISTS", "Kode organizer sudah digunakan client", 409)
    row = Organizer(client_id=client_id, code=payload.code, name=payload.name, active=payload.active)
    db.add(row); await db.flush(); _audit(db, actor_id, row, "ORGANIZER_CREATED", payload.reason); await db.commit(); return _view(row)


async def update_organizer(db, actor_id, client_id, row_id, payload):
    row = await db.scalar(select(Organizer).where(Organizer.id == row_id, Organizer.client_id == client_id).with_for_update())
    if not row: raise AppError("ORGANIZER_NOT_FOUND", "Organizer tidak ditemukan", 404)
    if row.version != payload.expected_version: raise AppError("ORGANIZER_VERSION_CONFLICT", "Organizer telah berubah", 409)
    before = _view(row); row.name, row.active = payload.name, payload.active; row.version += 1
    _audit(db, actor_id, row, "ORGANIZER_UPDATED", payload.reason, before); await db.commit(); return _view(row)


async def update_merchant(db, actor_id, client_id, row_id, payload):
    row = await db.scalar(select(MerchantAccount).where(MerchantAccount.id == row_id, MerchantAccount.client_id == client_id).with_for_update())
    if not row: raise AppError("MERCHANT_ACCOUNT_NOT_FOUND", "Merchant account tidak ditemukan", 404)
    if row.version != payload.expected_version: raise AppError("MERCHANT_ACCOUNT_VERSION_CONFLICT", "Merchant account telah berubah", 409)
    before = _view(row); row.name, row.credential_ref, row.active = payload.name, payload.credential_ref, payload.active; row.version += 1
    _audit(db, actor_id, row, "MERCHANT_ACCOUNT_UPDATED", payload.reason, before); await db.commit(); return _view(row)


async def create_channel(db, actor_id, client_id, payload):
    account = await db.scalar(select(MerchantAccount).where(MerchantAccount.id == payload.merchant_account_id, MerchantAccount.client_id == client_id))
    if not account: raise AppError("MERCHANT_ACCOUNT_NOT_FOUND", "Merchant account tidak ditemukan", 404)
    if payload.max_amount is not None and payload.min_amount is not None and payload.max_amount < payload.min_amount: raise AppError("INVALID_CHANNEL_LIMIT", "max_amount harus >= min_amount", 422)
    exists = await db.scalar(select(PaymentChannel).where(PaymentChannel.merchant_account_id == account.id, PaymentChannel.channel_code == payload.channel_code))
    if exists: raise AppError("PAYMENT_CHANNEL_EXISTS", "Channel sudah terdaftar pada merchant", 409)
    row = PaymentChannel(merchant_account_id=account.id, gateway=payload.gateway.upper(), channel_code=payload.channel_code, name=payload.name, active=payload.active, min_amount=payload.min_amount, max_amount=payload.max_amount, currencies=[c.upper() for c in payload.currencies])
    db.add(row); await db.flush(); _audit(db, actor_id, row, "PAYMENT_CHANNEL_CREATED", payload.reason); await db.commit(); return _view(row)


async def update_channel(db, actor_id, client_id, row_id, payload):
    row = await db.scalar(select(PaymentChannel).join(MerchantAccount).where(PaymentChannel.id == row_id, MerchantAccount.client_id == client_id).with_for_update())
    if not row: raise AppError("PAYMENT_CHANNEL_NOT_FOUND", "Payment channel tidak ditemukan", 404)
    if row.version != payload.expected_version: raise AppError("PAYMENT_CHANNEL_VERSION_CONFLICT", "Payment channel telah berubah", 409)
    if payload.max_amount is not None and payload.min_amount is not None and payload.max_amount < payload.min_amount: raise AppError("INVALID_CHANNEL_LIMIT", "max_amount harus >= min_amount", 422)
    before = _view(row); row.name, row.active, row.min_amount, row.max_amount, row.currencies = payload.name, payload.active, payload.min_amount, payload.max_amount, [c.upper() for c in payload.currencies]; row.version += 1
    _audit(db, actor_id, row, "PAYMENT_CHANNEL_UPDATED", payload.reason, before); await db.commit(); return _view(row)


async def create_routing(db, actor_id, client_id, payload):
    await _client(db, client_id)
    account = await db.scalar(select(MerchantAccount).where(MerchantAccount.id == payload.merchant_account_id, MerchantAccount.client_id == client_id))
    if not account: raise AppError("MERCHANT_ACCOUNT_NOT_FOUND", "Merchant account tidak ditemukan", 404)
    if payload.service_id and not await db.scalar(select(Service).where(Service.id == payload.service_id, Service.client_id == client_id)): raise AppError("SERVICE_NOT_FOUND", "Service tidak ditemukan pada client", 404)
    row = RoutingRule(client_id=client_id, service_id=payload.service_id, event_id=payload.event_id, channel_code=payload.channel_code, merchant_account_id=account.id, priority=payload.priority, active=payload.active)
    db.add(row); await db.flush(); _audit(db, actor_id, row, "ROUTING_RULE_CREATED", payload.reason); await db.commit(); return _view(row)


async def update_routing(db, actor_id, client_id, row_id, payload):
    row = await db.scalar(select(RoutingRule).where(RoutingRule.id == row_id, RoutingRule.client_id == client_id).with_for_update())
    if not row: raise AppError("ROUTING_RULE_NOT_FOUND", "Routing rule tidak ditemukan", 404)
    if row.version != payload.expected_version: raise AppError("ROUTING_RULE_VERSION_CONFLICT", "Routing rule telah berubah", 409)
    if not await db.scalar(select(MerchantAccount).where(MerchantAccount.id == payload.merchant_account_id, MerchantAccount.client_id == client_id)): raise AppError("MERCHANT_ACCOUNT_NOT_FOUND", "Merchant account tidak ditemukan", 404)
    before = _view(row); row.merchant_account_id, row.priority, row.active = payload.merchant_account_id, payload.priority, payload.active; row.version += 1
    _audit(db, actor_id, row, "ROUTING_RULE_UPDATED", payload.reason, before); await db.commit(); return _view(row)


async def upsert_flag(db, actor_id, client_id, payload):
    await _client(db, client_id)
    row = await db.scalar(select(FeatureFlag).where(FeatureFlag.client_id == client_id, FeatureFlag.key == payload.key).with_for_update())
    before = _view(row) if row else None
    if row:
        if payload.expected_version is None or row.version != payload.expected_version: raise AppError("FEATURE_FLAG_VERSION_CONFLICT", "Feature flag telah berubah", 409)
        row.enabled, row.config_json, row.version = payload.enabled, payload.config, row.version + 1
        action = "FEATURE_FLAG_UPDATED"
    else:
        if payload.expected_version is not None: raise AppError("FEATURE_FLAG_NOT_FOUND", "Feature flag belum terdaftar", 404)
        row = FeatureFlag(client_id=client_id, key=payload.key, enabled=payload.enabled, config_json=payload.config); db.add(row); await db.flush(); action = "FEATURE_FLAG_CREATED"
    _audit(db, actor_id, row, action, payload.reason, before); await db.commit(); return _view(row)
