import hashlib
import hmac
import secrets
import time
import uuid
from urllib.parse import urlsplit

from jose import JWTError, jwt
from app.core.config import get_settings
from app.core.errors import AppError

SCOPES = {"payments:read", "payments:write", "payments:refund"}


def hash_secret(secret: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(secret.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_secret(secret: str, encoded: str) -> bool:
    try:
        scheme, salt, expected = encoded.split("$")
        if scheme != "scrypt" or len(secret) > 256:
            return False
        actual = hashlib.scrypt(secret.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def signing_key():
    key = get_settings().jwt_secret
    if len(key) < 48 or key.startswith("REPLACE"):
        raise AppError("AUTH_NOT_CONFIGURED", "JWT signing key belum dikonfigurasi", 503)
    return key


def issue_access_token(client, scopes: set[str]) -> str:
    settings = get_settings()
    now = int(time.time())
    return jwt.encode({
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
        "sub": str(client.id), "iat": now, "nbf": now,
        "exp": now + settings.access_token_ttl_seconds, "jti": str(uuid.uuid4()),
        "scope": " ".join(sorted(scopes)), "ver": client.token_version, "kind": "client_access",
    }, signing_key(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        claims = jwt.decode(token, signing_key(), algorithms=["HS256"],
                            issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                            options={"require_exp": True, "require_iat": True, "require_nbf": True,
                                     "require_sub": True, "require_jti": True, "require_aud": True, "require_iss": True})
        if claims.get("kind") != "client_access" or not isinstance(claims.get("scope"), str):
            raise ValueError()
        if type(claims.get("ver")) is not int or claims["iat"] > time.time():
            raise ValueError()
        uuid.UUID(claims["sub"])
        return claims
    except (JWTError, ValueError, TypeError, KeyError):
        raise AppError("INVALID_ACCESS_TOKEN", "Access token tidak valid atau kedaluwarsa", 401)


def bearer_value(authorization: str | None) -> str:
    if not authorization:
        raise AppError("AUTH_REQUIRED", "Authorization Bearer wajib diisi", 401)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 4096:
        raise AppError("INVALID_ACCESS_TOKEN", "Authorization tidak valid", 401)
    return token


def validate_registered_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        local = get_settings().environment != "production" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or not parsed.hostname:
            raise ValueError()
        if parsed.username or parsed.password or parsed.fragment or any(c.isspace() for c in url) or "\\" in url:
            raise ValueError()
        parsed.port
    except ValueError:
        raise AppError("INVALID_REGISTERED_URL", "URL wajib HTTPS valid (localhost HTTP hanya development)", 422)


def allow_url(url: str | None, allowed: list, label: str):
    if url is None:
        return
    validate_registered_url(url)
    if url not in allowed:
        raise AppError("URL_NOT_ALLOWED", f"{label} belum terdaftar untuk client", 422)

