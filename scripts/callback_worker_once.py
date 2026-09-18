import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.services.callback_service import deliver_pending_callbacks


async def main() -> None:
    async with SessionLocal() as db:
        print(await deliver_pending_callbacks(db))


if __name__ == "__main__":
    asyncio.run(main())

