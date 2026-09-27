import hmac
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import build_canonical, sign, timestamp_is_valid
from app.core.secret_store import decrypt_secret
from app.models.payment import Client, NonceRecord
from app.core.access import bearer_value, decode_access_token
import uuid


async def legacy_hmac_dependency(request: Request, db: AsyncSession = Depends(get_db), x_client_id: str | None = Header(default=None), x_key_id: str | None = Header(default=None), x_timestamp: str | None = Header(default=None), x_nonce: str | None = Header(default=None), x_signature: str | None = Header(default=None)) -> Client:
    client = await db.scalar(select(Client).where(Client.code == x_client_id, Client.active.is_(True)))
    if not client:
        raise AppError("CLIENT_NOT_FOUND", "Client tidak ditemukan atau tidak aktif", 401)
    if get_settings().auth_enabled:
        if not all([x_key_id, x_timestamp, x_nonce, x_signature]) or not timestamp_is_valid(x_timestamp or ""):
            raise AppError("INVALID_SIGNATURE", "Header autentikasi tidak valid", 401)
        if x_key_id != client.key_id or len(x_nonce) > 150 or not x_nonce.strip() or len(x_signature) != 44:
            raise AppError("INVALID_SIGNATURE", "Header autentikasi tidak valid", 401)
        if any("\n" in value or "\r" in value or not value.isascii() for value in (x_client_id, x_key_id, x_timestamp, x_nonce, x_signature)):
            raise AppError("INVALID_SIGNATURE", "Header autentikasi tidak valid", 401)
        path = request.scope.get("raw_path", request.url.path.encode()).decode("ascii")
        query = request.scope.get("query_string", b"").decode("ascii")
        if query:
            path += "?" + query
        canonical = build_canonical(request.method, path, x_client_id or "", x_key_id or "", x_timestamp or "", x_nonce or "", await request.body())
        settings = get_settings()
        api_secret = decrypt_secret(client.api_secret_ciphertext, settings.credential_encryption_key,
                                    settings.credential_encryption_key_previous) if client.api_secret_ciphertext else client.api_secret
        if not hmac.compare_digest(sign(canonical, api_secret), x_signature or ""):
            raise AppError("INVALID_SIGNATURE", "Signature tidak valid", 401)
        nonce_id = await db.scalar(insert(NonceRecord).values(
            client_id=client.id, nonce=x_nonce,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=get_settings().nonce_ttl_seconds),
        ).on_conflict_do_nothing(index_elements=["client_id", "nonce"]).returning(NonceRecord.id))
        if nonce_id is None:
            raise AppError("REPLAY_DETECTED", "Nonce sudah pernah digunakan", 401)
        await db.commit()
    return client


async def client_dependency(request: Request, db: AsyncSession = Depends(get_db), authorization: str | None = Header(None)) -> Client:
    claims = decode_access_token(bearer_value(authorization))
    client = await db.scalar(select(Client).where(Client.id == uuid.UUID(claims["sub"]), Client.active.is_(True)))
    if not client or not client.oauth_secret_hash or client.token_version != claims["ver"]:
        raise AppError("INVALID_ACCESS_TOKEN", "Client/token tidak aktif", 401)
    required = "payments:read" if request.method == "GET" else "payments:write"
    if request.url.path.endswith("/refunds"):
        required = "payments:refund"
    if required not in claims["scope"].split() or required not in client.allowed_scopes.split():
        raise AppError("INSUFFICIENT_SCOPE", "Scope tidak mengizinkan operasi ini", 403)
    return client
