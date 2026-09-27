"""Encrypt legacy plaintext client credentials after CREDENTIAL_ENCRYPTION_KEY is provisioned."""
import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.secret_store import decrypt_secret, encrypt_secret
from app.models.payment import Client


async def backfill(dry_run: bool) -> int:
    settings = get_settings()
    if not settings.credential_encryption_key:
        raise SystemExit("CREDENTIAL_ENCRYPTION_KEY wajib diisi")
    async with SessionLocal() as db:
        rows = list((await db.scalars(select(Client).where(
            Client.callback_secret.is_not(None) |
            Client.callback_secret_ciphertext.is_not(None) |
            Client.api_secret.is_not(None) |
            Client.api_secret_ciphertext.is_not(None)
        ))).all())
        changed = 0
        if dry_run:
            for client in rows:
                changed += _rotate_client_credentials(client, settings, dry_run=True)
            print(f"clients_scanned={len(rows)} credentials_to_rewrite={changed} dry_run=true")
            return changed
        for client in rows:
            changed += _rotate_client_credentials(client, settings)
        await db.commit()
        print(f"clients_scanned={len(rows)} credentials_rewritten={changed}")
        return changed


def _rewrite(value: str | None, ciphertext: str | None, settings, dry_run: bool) -> tuple[str | None, str | None, bool]:
    if value:
        return (value, None, True) if dry_run else ("", encrypt_secret(value, settings.credential_encryption_key), True)
    if not ciphertext:
        return value, ciphertext, False
    try:
        decrypt_secret(ciphertext, settings.credential_encryption_key)
        return value, ciphertext, False
    except AppError:
        # Current key failed; previous key must be configured during rotation.
        plain = decrypt_secret(ciphertext, settings.credential_encryption_key,
                               settings.credential_encryption_key_previous)
        return value, ciphertext if dry_run else encrypt_secret(plain, settings.credential_encryption_key), True


def _rotate_client_credentials(client, settings, dry_run=False) -> int:
    callback_plain, callback_cipher, callback_changed = _rewrite(
        client.callback_secret, client.callback_secret_ciphertext, settings, dry_run)
    api_plain, api_cipher, api_changed = _rewrite(
        client.api_secret, client.api_secret_ciphertext, settings, dry_run)
    if not dry_run:
        client.callback_secret, client.callback_secret_ciphertext = callback_plain, callback_cipher
        client.api_secret, client.api_secret_ciphertext = api_plain, api_cipher
    return int(callback_changed) + int(api_changed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count legacy rows without changing the database")
    args = parser.parse_args()
    asyncio.run(backfill(args.dry_run))


if __name__ == "__main__":
    main()
