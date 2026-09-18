import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.payment import Client, Service


async def main(client_code: str, service_code: str, secret: str) -> None:
    async with SessionLocal() as db:
        client = await db.scalar(select(Client).where(Client.code == client_code))
        if not client:
            client = Client(code=client_code, name="Development Event Client", api_secret=secret, callback_secret=secret, callback_url="http://localhost:9000/callback/payment")
            db.add(client)
            await db.flush()
        elif not client.callback_secret:
            client.callback_secret = secret
        service = await db.scalar(select(Service).where(Service.client_id == client.id, Service.code == service_code))
        if not service:
            db.add(Service(client_id=client.id, code=service_code, name="Development Event 2026"))
        await db.commit()
        print(f"seeded client={client.code} service={service_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-code", default="EVENT-CLIENT")
    parser.add_argument("--service-code", default="EVENT-2026")
    parser.add_argument("--secret", default="dev-event-secret")
    args = parser.parse_args()
    asyncio.run(main(args.client_code, args.service_code, args.secret))
