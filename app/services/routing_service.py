from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.routing import MerchantAccount, PaymentChannel, RoutingRule


async def eligible_channels(db: AsyncSession, payment):
    rows = list((await db.scalars(
        select(PaymentChannel).join(MerchantAccount).where(
            MerchantAccount.client_id == payment.client_id,
            MerchantAccount.id == PaymentChannel.merchant_account_id,
            MerchantAccount.active.is_(True), PaymentChannel.active.is_(True),
        ).order_by(PaymentChannel.channel_code)
    )).all())
    if not rows:
        return []
    rules = list((await db.scalars(select(RoutingRule).where(
        RoutingRule.client_id == payment.client_id, RoutingRule.active.is_(True),
        or_(RoutingRule.service_id.is_(None), RoutingRule.service_id == payment.service_id),
        or_(RoutingRule.event_id.is_(None), RoutingRule.event_id == payment.event_id),
    ))).all())
    if rules:
        codes = {rule.channel_code for rule in rules}
        rows = [row for row in rows if row.channel_code in codes]
    return [row for row in rows if payment.currency in (row.currencies or [])
            and (row.min_amount is None or payment.amount >= row.min_amount)
            and (row.max_amount is None or payment.amount <= row.max_amount)]


async def has_active_configuration(db: AsyncSession, client_id):
    return await db.scalar(select(PaymentChannel.id).join(MerchantAccount).where(
        MerchantAccount.client_id == client_id, MerchantAccount.active.is_(True),
        PaymentChannel.active.is_(True),
    ).limit(1)) is not None


async def ensure_channel_eligible(db: AsyncSession, payment, channel_code: str):
    has_config = await has_active_configuration(db, payment.client_id)
    eligible = await eligible_channels(db, payment)
    if not has_config:
        return None
    channel = next((row for row in eligible if row.channel_code == channel_code), None)
    if channel is None:
        raise AppError("UNSUPPORTED_CHANNEL", "Channel tidak tersedia untuk payment ini", 422)
    return channel
