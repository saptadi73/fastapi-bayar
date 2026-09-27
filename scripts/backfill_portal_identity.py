"""Backfill only from an operator-approved explicit mapping CSV.

Dry-run is the default. Apply requires --apply, --approved-by and --reason.
Required columns: payment_id,event_id,event_name,email,user_name.
"""
import argparse
import asyncio
import csv
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.admin import AdminAudit
from app.models.payment import PaymentTransaction
from app.models.portal_identity import PortalEvent, PortalUser


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    required = {"payment_id", "event_id", "event_name", "email", "user_name"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"CSV wajib memiliki kolom: {','.join(sorted(required))}")
    return rows


async def run(path: Path, apply: bool, approved_by: str | None, reason: str | None):
    rows = read_rows(path)
    async with SessionLocal() as db:
        changes = []
        for index, row in enumerate(rows, 2):
            try:
                payment_id = uuid.UUID(row["payment_id"].strip())
            except ValueError as exc:
                raise ValueError(f"baris {index}: payment_id invalid") from exc
            payment = await db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment_id).with_for_update())
            if payment is None:
                raise ValueError(f"baris {index}: payment tidak ditemukan")
            event_id, event_name = row["event_id"].strip(), row["event_name"].strip()
            email, user_name = row["email"].strip().lower(), row["user_name"].strip()
            if not all((event_id, event_name, email, user_name)):
                raise ValueError(f"baris {index}: event dan email tidak boleh kosong")
            if ((payment.event_id and payment.event_id != event_id) or
                    (payment.customer_email and payment.customer_email != email)):
                raise ValueError(f"baris {index}: mapping akan menimpa snapshot non-null; ditolak")
            changes.append((payment, event_id, event_name, email, user_name))
        print(f"validated_rows={len(changes)} apply={apply}")
        if not apply:
            return
        if not approved_by or not reason:
            raise ValueError("--apply wajib disertai --approved-by dan --reason")
        for payment, event_id, event_name, email, user_name in changes:
            event = await db.scalar(select(PortalEvent).where(PortalEvent.client_id == payment.client_id, PortalEvent.event_id == event_id).with_for_update())
            if event is None:
                event = PortalEvent(client_id=payment.client_id, event_id=event_id, name=event_name)
                db.add(event); await db.flush()
            payer = await db.scalar(select(PortalUser).where(PortalUser.client_id == payment.client_id, PortalUser.email == email).with_for_update())
            if payer is None:
                payer = PortalUser(client_id=payment.client_id, email=email, name=user_name)
                db.add(payer); await db.flush()
            payment.event_id, payment.event_name = event_id, event_name
            payment.customer_email, payment.customer_name = email, user_name
            payment.event_record_id, payment.portal_user_id = event.id, payer.id
            db.add(AdminAudit(actor_id=None, action="HISTORICAL_IDENTITY_BACKFILL", resource_id=str(payment.id),
                              reason=f"{approved_by}: {reason}", details_json={"event_id": event_id, "email_sha256": hashlib.sha256(email.encode()).hexdigest()[:16]},
                              occurred_at=datetime.now(timezone.utc)))
        await db.commit()
        print(f"applied_rows={len(changes)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-by")
    parser.add_argument("--reason")
    args = parser.parse_args()
    asyncio.run(run(args.mapping, args.apply, args.approved_by, args.reason))


if __name__ == "__main__":
    main()
