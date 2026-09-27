"""Tenant-scoped merchant, routing, channel and feature configuration."""
import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Organizer(Base):
    __tablename__ = "organizers"
    __table_args__ = (UniqueConstraint("client_id", "code", name="uq_organizer_client_code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class MerchantAccount(Base):
    __tablename__ = "merchant_accounts"
    __table_args__ = (UniqueConstraint("client_id", "code", name="uq_merchant_client_code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    gateway: Mapped[str] = mapped_column(String(30))
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PaymentChannel(Base):
    __tablename__ = "payment_channels"
    __table_args__ = (UniqueConstraint("merchant_account_id", "channel_code", name="uq_channel_merchant_code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchant_accounts.id"), index=True)
    gateway: Mapped[str] = mapped_column(String(30))
    channel_code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    min_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currencies: Mapped[list] = mapped_column(JSON, default=lambda: ["IDR"], server_default='["IDR"]')
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class RoutingRule(Base):
    __tablename__ = "merchant_routing_rules"
    __table_args__ = (UniqueConstraint("client_id", "service_id", "event_id", "channel_code", name="uq_routing_rule_scope"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    channel_code: Mapped[str] = mapped_column(String(80))
    merchant_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchant_accounts.id"))
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class FeatureFlag(Base):
    __tablename__ = "client_feature_flags"
    __table_args__ = (UniqueConstraint("client_id", "key", name="uq_feature_flag_client_key"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    config_json: Mapped[dict] = mapped_column("config", JSON, default=dict, server_default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
