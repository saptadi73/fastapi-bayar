"""Create the first Super Admin interactively; never accept passwords as CLI args."""
import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select, text
from app.core.admin_security import hash_password
from app.core.database import SessionLocal, engine
from app.models.admin import AdminAudit, AdminUser


async def bootstrap(email: str, name: str, password: str):
    email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    name = name.strip()
    if not 1 <= len(name) <= 200:
        raise ValueError("Nama harus 1-200 karakter")
    encoded = hash_password(password)
    async with SessionLocal() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(7011011)"))
        if await db.scalar(select(AdminUser.id).limit(1)):
            raise ValueError("Admin sudah ada; bootstrap tidak mengganti akun/password existing")
        user = AdminUser(email=email, display_name=name, password_hash=encoded, role="SUPER_ADMIN")
        db.add(user)
        await db.flush()
        db.add(AdminAudit(actor_id=user.id, action="BOOTSTRAP", occurred_at=datetime.now(timezone.utc)))
        await db.commit()
        return user.id


async def main(args):
    password = getpass.getpass("Password baru (15-128 karakter): ")
    if password != getpass.getpass("Ulangi password: "):
        raise ValueError("Password tidak sama")
    try:
        user_id = await bootstrap(args.email, args.name, password)
        print("Super Admin dibuat:", user_id)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    try:
        asyncio.run(main(parser.parse_args()))
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
