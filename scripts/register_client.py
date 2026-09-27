"""Register/rotate a confidential client locally. Secrets are printed once, not logged."""
import argparse
import asyncio
import secrets
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.core.access import SCOPES, hash_secret, validate_registered_url
from app.core.config import get_settings
from app.core.secret_store import encrypt_secret
from app.core.database import SessionLocal, engine
from app.models.payment import Client, Service


async def main(args):
    for url in args.return_url + ([args.callback_url] if args.callback_url else []):
        validate_registered_url(url)
    if not set(args.scope) <= SCOPES:
        raise ValueError("Unsupported scope")
    async with SessionLocal() as db:
        client = await db.scalar(select(Client).where(Client.code == args.code).with_for_update())
        if client and not args.rotate:
            raise ValueError("Client exists. Use --rotate to explicitly replace credentials/allowlists and revoke JWTs.")
        secret = secrets.token_urlsafe(48)
        encryption_key = get_settings().credential_encryption_key
        api_secret = secrets.token_urlsafe(48)
        callback_secret = secrets.token_urlsafe(48)
        if not client:
            client = Client(code=args.code, name=args.name,
                            api_secret=api_secret if not encryption_key else "",
                            api_secret_ciphertext=encrypt_secret(api_secret, encryption_key) if encryption_key else None,
                            callback_secret=callback_secret if not encryption_key else None,
                            callback_secret_ciphertext=encrypt_secret(callback_secret, encryption_key) if encryption_key else None,
                            token_version=1)
            db.add(client)
        else:
            client.token_version += 1
        client.oauth_secret_hash = hash_secret(secret)
        client.allowed_scopes = " ".join(sorted(set(args.scope)))
        client.allowed_return_urls = args.return_url
        client.allowed_callback_urls = [args.callback_url] if args.callback_url else []
        client.callback_url = args.callback_url
        await db.flush()
        service = await db.scalar(select(Service).where(Service.client_id == client.id, Service.code == args.service))
        if not service:
            db.add(Service(client_id=client.id, code=args.service, name=args.service))
        await db.commit()
        print("client_id:", client.code)
        print("client_secret (save securely):", secret)
        print("callback_secret (save in Event backend):", callback_secret)
        print("service_code:", args.service)
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--return-url", action="append", default=[])
    parser.add_argument("--callback-url")
    parser.add_argument("--scope", action="append", default=["payments:read", "payments:write"])
    parser.add_argument("--rotate", action="store_true")
    asyncio.run(main(parser.parse_args()))

