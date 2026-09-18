"""Resolve tenant identities inside the caller's locked initiation transaction."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Client
from app.models.portal_identity import PortalEvent, PortalUser
from app.schemas.payment import InitiatePaymentRequest


async def resolve_portal_identity(db: AsyncSession, client: Client, payload: InitiatePaymentRequest):
    # initiate() holds the client row lock; unique constraints protect all write paths.
    event = await db.scalar(select(PortalEvent).where(
        PortalEvent.client_id == client.id, PortalEvent.event_id == payload.event_id))
    if event is None:
        event = PortalEvent(client_id=client.id, event_id=payload.event_id, name=payload.event_name)
        db.add(event)
    else:
        event.name = payload.event_name
    payer = await db.scalar(select(PortalUser).where(
        PortalUser.client_id == client.id, PortalUser.email == str(payload.customer.email)))
    if payer is None:
        payer = PortalUser(client_id=client.id, email=str(payload.customer.email), name=payload.customer.name)
        db.add(payer)
    else:
        payer.name = payload.customer.name
    await db.flush()
    return event, payer
