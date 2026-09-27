from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.core.admin_security import ROLES
from app.core.errors import AppError
from app.models.admin import AdminAudit, AdminClientAssignment, AdminRole, AdminUser
from app.models.payment import Client


def available_permissions():
    return sorted(set().union(*ROLES.values()))


async def update_role(db, actor_id, code, payload):
    invalid = sorted(set(payload.permissions) - set(available_permissions()))
    if invalid:
        raise AppError("UNKNOWN_PERMISSION", "Permission tidak dikenal", 422, {"permissions": invalid})
    role = await db.scalar(select(AdminRole).where(AdminRole.code == code).with_for_update())
    if role is None:
        role = AdminRole(code=code, display_name=payload.display_name, permissions_json=sorted(set(payload.permissions)))
        db.add(role); await db.flush(); action = "ROLE_CREATED"; before = None
    else:
        if role.version != payload.expected_version:
            raise AppError("ROLE_VERSION_CONFLICT", "Role telah berubah", 409)
        before = {"display_name": role.display_name, "permissions": role.permissions_json, "active": role.active}
        role.display_name, role.permissions_json, role.version = payload.display_name, sorted(set(payload.permissions)), role.version + 1
        action = "ROLE_UPDATED"
    db.add(AdminAudit(actor_id=actor_id, action=action, resource_id=code, reason=payload.reason,
                      details_json={"before": before, "after": {"display_name": role.display_name, "permissions": role.permissions_json}},
                      occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"code": role.code, "display_name": role.display_name, "permissions": role.permissions_json, "version": role.version}


async def assign_client(db, actor_id, user_id, payload):
    user = await db.get(AdminUser, user_id)
    if not user: raise AppError("ADMIN_USER_NOT_FOUND", "User tidak ditemukan", 404)
    if not await db.get(Client, payload.client_id): raise AppError("CLIENT_NOT_FOUND", "Client tidak ditemukan", 404)
    result = await db.scalar(insert(AdminClientAssignment).values(user_id=user_id, client_id=payload.client_id, active=True, version=1)
                             .on_conflict_do_update(index_elements=[AdminClientAssignment.user_id, AdminClientAssignment.client_id], set_={"active": True}).returning(AdminClientAssignment.id))
    db.add(AdminAudit(actor_id=actor_id, action="ADMIN_CLIENT_ASSIGNED", resource_id=str(user_id), reason=payload.reason,
                      details_json={"client_id": str(payload.client_id), "active": True}, occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"id": str(result), "user_id": str(user_id), "client_id": str(payload.client_id), "active": True}
