from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import AppError
from app.models.admin import AdminAudit
from app.models.payment import Service
from app.services.admin_client_service import find_client


def service_view(service):
    return {"id": str(service.id), "client_id": str(service.client_id), "code": service.code,
            "name": service.name, "active": service.active, "version": service.version}


async def find_service(db, client_id, service_id, lock=False):
    query = select(Service).where(Service.id == service_id, Service.client_id == client_id)
    if lock:
        query = query.with_for_update()
    service = await db.scalar(query)
    if service is None:
        raise AppError("SERVICE_NOT_FOUND", "Service tidak ditemukan pada client", 404)
    return service


def audit(db, actor_id, service, action, reason):
    db.add(AdminAudit(actor_id=actor_id, action=action, resource_id=str(service.id),
                      reason=reason, occurred_at=datetime.now(timezone.utc)))


async def create_service(db, actor_id, client_id, payload):
    # Same lock/order as payment initiation and client configuration changes.
    await find_client(db, client_id, lock=True)
    service_id = await db.scalar(insert(Service).values(
        id=uuid.uuid4(), client_id=client_id, code=payload.code, name=payload.name,
        active=payload.active, version=1,
    ).on_conflict_do_nothing(index_elements=[Service.client_id, Service.code]).returning(Service.id))
    if service_id is None:
        raise AppError("SERVICE_CODE_EXISTS", "Kode service sudah digunakan pada client ini", 409)
    service = await find_service(db, client_id, service_id)
    audit(db, actor_id, service, "SERVICE_CREATED", payload.reason)
    await db.commit()
    return service_view(service)


async def update_service(db, actor_id, client_id, service_id, payload):
    await find_client(db, client_id, lock=True)
    service = await find_service(db, client_id, service_id, lock=True)
    if service.version != payload.expected_version:
        raise AppError("SERVICE_VERSION_CONFLICT", "Service telah berubah; muat ulang", 409)
    service.name, service.active = payload.name, payload.active
    service.version += 1
    audit(db, actor_id, service, "SERVICE_UPDATED", payload.reason)
    await db.commit()
    return service_view(service)
