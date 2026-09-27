import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.admin import AdminAudit
from app.models.payment import Client, PaymentTransaction
from app.models.portal_identity import PortalUser
from app.schemas.admin_portal import CreatePortalUser, DeletePortalUser, UpdatePortalUser


def user_view(user: PortalUser) -> dict:
    return {"id": str(user.id), "client_id": str(user.client_id), "email": user.email,
            "name": user.name, "version": user.version}


def audit_snapshot(user: PortalUser | None) -> dict | None:
    if user is None:
        return None
    return {"email_sha256": hashlib.sha256(user.email.encode()).hexdigest()[:16],
            "name_present": bool(user.name), "version": user.version}


def add_audit(db, actor_id, user, action, reason, before=None, after=None):
    db.add(AdminAudit(actor_id=actor_id, action=action, resource_id=str(user.id), reason=reason,
                      details_json={"before": before, "after": after},
                      occurred_at=datetime.now(timezone.utc)))


async def find_client(db: AsyncSession, client_id: uuid.UUID):
    client = await db.get(Client, client_id)
    if client is None:
        raise AppError("CLIENT_NOT_FOUND", "Client tidak ditemukan", 404)
    return client


async def find_user(db: AsyncSession, client_id, user_id, lock=False):
    query = select(PortalUser).where(PortalUser.client_id == client_id, PortalUser.id == user_id)
    if lock:
        query = query.with_for_update()
    user = await db.scalar(query)
    if user is None:
        raise AppError("PORTAL_USER_NOT_FOUND", "Portal user tidak ditemukan pada client", 404)
    return user


async def create_user(db: AsyncSession, actor_id, client_id, payload: CreatePortalUser):
    await find_client(db, client_id)
    email = str(payload.email).lower()
    user_id = await db.scalar(insert(PortalUser).values(
        id=uuid.uuid4(), client_id=client_id, email=email, name=payload.name, version=1,
    ).on_conflict_do_nothing(index_elements=[PortalUser.client_id, PortalUser.email]).returning(PortalUser.id))
    if user_id is None:
        raise AppError("PORTAL_USER_EXISTS", "Email portal user sudah terdaftar pada client", 409)
    user = await find_user(db, client_id, user_id)
    add_audit(db, actor_id, user, "PORTAL_USER_CREATED", payload.reason,
              after=audit_snapshot(user))
    await db.commit()
    return user_view(user)


async def update_user(db: AsyncSession, actor_id, client_id, user_id, payload: UpdatePortalUser):
    await find_client(db, client_id)
    user = await find_user(db, client_id, user_id, lock=True)
    if user.version != payload.expected_version:
        raise AppError("PORTAL_USER_VERSION_CONFLICT", "Portal user telah berubah; muat ulang", 409)
    before = audit_snapshot(user)
    user.name = payload.name
    user.version += 1
    add_audit(db, actor_id, user, "PORTAL_USER_UPDATED", payload.reason,
              before=before, after=audit_snapshot(user))
    await db.commit()
    return user_view(user)


async def delete_user(db: AsyncSession, actor_id, client_id, user_id, payload: DeletePortalUser):
    await find_client(db, client_id)
    user = await find_user(db, client_id, user_id, lock=True)
    payment_count = await db.scalar(select(func.count()).select_from(PaymentTransaction).where(
        PaymentTransaction.client_id == client_id, PaymentTransaction.portal_user_id == user_id))
    if payment_count:
        raise AppError("PORTAL_USER_DELETE_CONFLICT", "Portal user masih direferensikan transaksi", 409,
                        {"payment_count": payment_count})
    before = audit_snapshot(user)
    add_audit(db, actor_id, user, "PORTAL_USER_DELETED", payload.reason, before=before)
    await db.delete(user)
    await db.commit()
    return {"id": str(user_id), "status": "deleted"}
