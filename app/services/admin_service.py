import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.admin_security import digest, hash_password, verify_password
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.secret_store import decrypt_secret, encrypt_secret
from app.core.totp import new_secret, verify as verify_totp
from app.models.admin import AdminAudit, AdminLoginBucket, AdminSession, AdminUser

DUMMY_PASSWORD = hash_password("not-a-real-admin-password")


async def login(db: AsyncSession, identifier: str, password: str, peer: str, old_token: str | None, otp: str | None = None):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    seconds = settings.admin_login_window_seconds
    window = int(now.timestamp()) // seconds
    # Atomic shared PostgreSQL counter, independent from authentication transaction.
    account_key = identifier.strip().lower()[:320]
    statement = insert(AdminLoginBucket).values(key=digest(f"{peer}:{account_key}"), window=window, count=1)
    statement = statement.on_conflict_do_update(
        index_elements=[AdminLoginBucket.key, AdminLoginBucket.window],
        set_={"count": AdminLoginBucket.count + 1}).returning(AdminLoginBucket.count)
    count = await db.scalar(statement)
    await db.commit()
    if count > settings.admin_login_limit:
        db.add(AdminAudit(actor_id=None, action="LOGIN_RATE_LIMITED", reason="account-aware login bucket", occurred_at=now))
        await db.commit()
        raise AppError("ADMIN_LOGIN_RATE_LIMIT", "Terlalu banyak percobaan login", 429,
                       {"retry_after": seconds - int(now.timestamp()) % seconds})
    user = await db.scalar(select(AdminUser).where(AdminUser.email == identifier.strip().lower()).with_for_update())
    valid = await run_in_threadpool(verify_password, password, user.password_hash if user else DUMMY_PASSWORD)
    if not user or not valid or not user.active:
        db.add(AdminAudit(actor_id=None, action="LOGIN_FAILED", occurred_at=now))
        await db.commit()
        raise AppError("ADMIN_LOGIN_FAILED", "Identitas atau password tidak valid", 401)
    if user.mfa_enabled:
        if not otp:
            db.add(AdminAudit(actor_id=user.id, action="LOGIN_MFA_REQUIRED", occurred_at=now))
            await db.commit()
            raise AppError("ADMIN_MFA_REQUIRED", "Kode MFA wajib diisi", 401)
        secret = decrypt_secret(user.mfa_secret_ciphertext, settings.credential_encryption_key,
                               settings.credential_encryption_key_previous)
        valid_otp = verify_totp(secret, otp)
        recovery_digest = digest("mfa-recovery:" + otp.upper())
        if not valid_otp and recovery_digest in (user.recovery_codes_hash or []):
            user.recovery_codes_hash = [item for item in user.recovery_codes_hash if item != recovery_digest]
            valid_otp = True
        if not valid_otp:
            db.add(AdminAudit(actor_id=user.id, action="LOGIN_MFA_FAILED", occurred_at=now))
            await db.commit()
            raise AppError("ADMIN_MFA_INVALID", "Kode MFA tidak valid", 401)
    if old_token:
        await db.execute(delete(AdminSession).where(AdminSession.token_hash == digest(old_token)))
    token = secrets.token_urlsafe(32)
    session = AdminSession(token_hash=digest(token), user_id=user.id,
                           expires_at=now + timedelta(seconds=settings.admin_session_ttl_seconds),
                           last_seen_at=now)
    db.add(session)
    db.add(AdminAudit(actor_id=user.id, action="LOGIN_SUCCEEDED", occurred_at=now))
    await db.commit()
    return token, user, session


async def authenticate(db: AsyncSession, token: str | None):
    if not token or len(token) != 43:
        raise AppError("ADMIN_SESSION_REQUIRED", "Login admin diperlukan", 401)
    row = (await db.execute(select(AdminSession, AdminUser).join(AdminUser)
                           .where(AdminSession.token_hash == digest(token))
                           .with_for_update(of=AdminSession))).first()
    now = datetime.now(timezone.utc)
    if not row:
        raise AppError("ADMIN_SESSION_INVALID", "Sesi admin tidak valid", 401)
    session, user = row
    if (not user.active or session.expires_at <= now or
        session.last_seen_at + timedelta(seconds=get_settings().admin_idle_ttl_seconds) <= now):
        await db.delete(session)
        await db.commit()
        raise AppError("ADMIN_SESSION_INVALID", "Sesi admin tidak valid", 401)
    session.last_seen_at = now
    await db.commit()
    return user, session


async def begin_mfa(db: AsyncSession, user: AdminUser):
    key = get_settings().credential_encryption_key
    if not key:
        raise AppError("CREDENTIAL_ENCRYPTION_REQUIRED", "Credential encryption key wajib untuk MFA", 503)
    secret = new_secret()
    user.mfa_secret_ciphertext = encrypt_secret(secret, key)
    user.mfa_enabled = False
    await db.commit()
    label = f"Payment Portal:{user.email}"
    return {"secret": secret, "otpauth_uri": f"otpauth://totp/{label}?secret={secret}&issuer=Payment%20Portal"}


async def confirm_mfa(db: AsyncSession, actor_id, user: AdminUser, code_value: str):
    if not user.mfa_secret_ciphertext:
        raise AppError("ADMIN_MFA_NOT_ENROLLED", "MFA belum dimulai", 409)
    secret = decrypt_secret(user.mfa_secret_ciphertext, get_settings().credential_encryption_key,
                            get_settings().credential_encryption_key_previous)
    if not verify_totp(secret, code_value):
        raise AppError("ADMIN_MFA_INVALID", "Kode MFA tidak valid", 422)
    codes = [secrets.token_hex(5).upper() for _ in range(8)]
    user.recovery_codes_hash = [digest("mfa-recovery:" + item) for item in codes]
    user.mfa_enabled = True
    db.add(AdminAudit(actor_id=actor_id, action="MFA_ENABLED", resource_id=str(user.id),
                      reason="MFA enrollment confirmed", occurred_at=datetime.now(timezone.utc)))
    await db.commit()
    return codes


async def reauthenticate(db: AsyncSession, user: AdminUser, session: AdminSession, password: str):
    if not await run_in_threadpool(verify_password, password, user.password_hash):
        raise AppError("ADMIN_REAUTH_FAILED", "Password reauthentication tidak valid", 401)
    session.reauthenticated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "reauthenticated", "valid_for_seconds": 300}
