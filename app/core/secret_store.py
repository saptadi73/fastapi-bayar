"""Application-level encryption for credentials that must be recovered at runtime."""
from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AppError


def encrypt_secret(value: str, key: str) -> str:
    if not key:
        raise AppError("CREDENTIAL_ENCRYPTION_KEY_REQUIRED", "Kunci enkripsi credential belum dikonfigurasi", 503)
    try:
        return Fernet(key.encode()).encrypt(value.encode()).decode()
    except ValueError as exc:
        raise AppError("CREDENTIAL_ENCRYPTION_KEY_INVALID", "Format kunci enkripsi credential tidak valid", 503) from exc


def decrypt_secret(value: str, key: str, previous_key: str = "") -> str:
    if not key and not previous_key:
        raise AppError("CREDENTIAL_ENCRYPTION_KEY_REQUIRED", "Kunci enkripsi credential belum dikonfigurasi", 503)
    last_error = None
    for candidate in (key, previous_key):
        if not candidate:
            continue
        try:
            return Fernet(candidate.encode()).decrypt(value.encode()).decode()
        except (ValueError, InvalidToken) as exc:
            last_error = exc
    raise AppError("CREDENTIAL_DECRYPTION_FAILED", "Credential terenkripsi tidak dapat dibuka", 503) from last_error
