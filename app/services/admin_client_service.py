import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.access import allow_url, hash_secret, validate_registered_url
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.secret_store import encrypt_secret
from app.models.admin import AdminAudit
from app.models.payment import CheckoutSession, Client, PaymentTransaction, Service
from app.schemas.admin_client import CreateClient, UpdateClient, RotateClientSecret, RotateCallbackSecret


def client_view(client: Client):
    # Explicit allowlist: never serialize ORM __dict__ or credential columns.
    return {"id": str(client.id), "code": client.code, "name": client.name, "active": client.active,
            "version": client.token_version, "scopes": client.allowed_scopes.split(),
            "callback_secret_version": client.callback_secret_version,
            "allowed_return_urls": client.allowed_return_urls,
            "allowed_callback_urls": client.allowed_callback_urls, "callback_url": client.callback_url}


def validate_configuration(payload):
    for url in payload.allowed_return_urls + payload.allowed_callback_urls:
        if len(url) > 500:
            raise AppError("INVALID_REGISTERED_URL", "URL maksimal 500 karakter", 422)
        validate_registered_url(url)
    allow_url(payload.callback_url, payload.allowed_callback_urls, "callback_url")


def audit(db, actor_id, client, action, reason):
    db.add(AdminAudit(actor_id=actor_id, action=action, resource_id=str(client.id),
                      reason=reason, occurred_at=datetime.now(timezone.utc)))


async def find_client(db: AsyncSession, client_id: uuid.UUID, lock=False):
    query = select(Client).where(Client.id == client_id)
    if lock:
        query = query.with_for_update()
    client = await db.scalar(query)
    if client is None:
        raise AppError("CLIENT_NOT_FOUND", "Client tidak ditemukan", 404)
    return client


def check_version(client, expected):
    if client.token_version != expected:
        raise AppError("CLIENT_VERSION_CONFLICT", "Client telah berubah; muat ulang sebelum mencoba lagi", 409)


async def create_client(db: AsyncSession, actor_id, payload: CreateClient):
    validate_configuration(payload)
    secret, callback_secret = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    encoded = await run_in_threadpool(hash_secret, secret)
    encryption_key = get_settings().credential_encryption_key
    api_secret = secrets.token_urlsafe(48)
    api_secret_ciphertext = encrypt_secret(api_secret, encryption_key) if encryption_key else None
    callback_secret_ciphertext = encrypt_secret(callback_secret, encryption_key) if encryption_key else None
    client_id = await db.scalar(insert(Client).values(
        id=uuid.uuid4(), code=payload.code, name=payload.name, active=payload.active,
        api_secret=api_secret if not api_secret_ciphertext else "", api_secret_ciphertext=api_secret_ciphertext,
        oauth_secret_hash=encoded,
        callback_secret=None if callback_secret_ciphertext else callback_secret,
        callback_secret_ciphertext=callback_secret_ciphertext, token_version=1,
        allowed_scopes=" ".join(sorted(set(payload.scopes))),
        allowed_return_urls=payload.allowed_return_urls, allowed_callback_urls=payload.allowed_callback_urls,
        callback_url=payload.callback_url,
    ).on_conflict_do_nothing(index_elements=[Client.code]).returning(Client.id))
    if client_id is None:
        raise AppError("CLIENT_CODE_EXISTS", "Kode client sudah terdaftar", 409)
    client = await find_client(db, client_id)
    db.add(Service(client_id=client.id, code=payload.service_code, name=payload.service_code))
    audit(db, actor_id, client, "CLIENT_CREATED", payload.reason)
    await db.commit()
    return {**client_view(client), "service_code": payload.service_code,
            "client_secret": secret, "callback_secret": callback_secret}


async def update_client(db: AsyncSession, actor_id, client_id, payload: UpdateClient):
    validate_configuration(payload)
    client = await find_client(db, client_id, lock=True)
    check_version(client, payload.expected_version)
    client.name, client.active = payload.name, payload.active
    client.allowed_scopes = " ".join(sorted(set(payload.scopes)))
    client.allowed_return_urls = payload.allowed_return_urls
    client.allowed_callback_urls = payload.allowed_callback_urls
    client.callback_url = payload.callback_url
    client.token_version += 1
    audit(db, actor_id, client, "CLIENT_UPDATED", payload.reason)
    await db.commit()
    return client_view(client)


async def rotate_secret(db: AsyncSession, actor_id, client_id, payload: RotateClientSecret):
    client = await find_client(db, client_id, lock=True)
    check_version(client, payload.expected_version)
    secret = secrets.token_urlsafe(48)
    client.oauth_secret_hash = await run_in_threadpool(hash_secret, secret)
    client.token_version += 1
    audit(db, actor_id, client, "CLIENT_SECRET_ROTATED", payload.reason)
    await db.commit()
    return {**client_view(client), "client_secret": secret}


async def rotate_callback_secret(db: AsyncSession, actor_id, client_id, payload: RotateCallbackSecret):
    client = await find_client(db, client_id, lock=True)
    if client.callback_secret_version != payload.expected_version:
        raise AppError("CLIENT_CALLBACK_VERSION_CONFLICT", "Callback secret telah berubah; muat ulang sebelum mencoba lagi", 409)
    callback_secret = secrets.token_urlsafe(48)
    encrypted = encrypt_secret(callback_secret, get_settings().credential_encryption_key) if get_settings().credential_encryption_key else None
    client.callback_secret = None if encrypted else callback_secret
    client.callback_secret_ciphertext = encrypted
    client.callback_secret_version += 1
    audit(db, actor_id, client, "CLIENT_CALLBACK_SECRET_ROTATED", payload.reason)
    await db.commit()
    return {**client_view(client), "callback_secret": callback_secret}


async def revoke_checkout_sessions(db: AsyncSession, actor_id, client_id: uuid.UUID, reason: str) -> dict:
    client = await find_client(db, client_id, lock=True)
    payment_ids = select(PaymentTransaction.id).where(PaymentTransaction.client_id == client.id)
    result = await db.execute(delete(CheckoutSession).where(CheckoutSession.payment_id.in_(payment_ids)))
    audit(db, actor_id, client, "CLIENT_CHECKOUTS_REVOKED", reason)
    await db.commit()
    return {"client_id": str(client.id), "checkout_sessions_revoked": result.rowcount or 0}
