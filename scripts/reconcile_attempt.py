"""Explicit one-attempt inquiry; never creates/cancels/refunds a provider transaction."""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.errors import AppError
from app.gateways.midtrans.client import MidtransSnapClient
from app.services.reconciliation_service import reconcile_attempt
import httpx


async def main(attempt_id):
    try:
        async with SessionLocal() as db:
            print(await reconcile_attempt(db, attempt_id, MidtransSnapClient(get_settings())))
    except AppError as error:
        print({"error": error.code, "message": error.message})
        return 1
    except httpx.HTTPError:
        print({"error": "GATEWAY_UNAVAILABLE"})
        return 1
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id", type=UUID)
    sys.exit(asyncio.run(main(parser.parse_args().attempt_id)))
