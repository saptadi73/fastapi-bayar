import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models import admin  # register admin metadata
from app.models.portal_identity import PortalEvent, PortalUser  # register metadata


class PaymentStatus(str, enum.Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    api_secret: Mapped[str] = mapped_column(String(255))
    key_id: Mapped[str] = mapped_column(String(100), default="key-2026-01", server_default="key-2026-01")
    oauth_secret_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    allowed_scopes: Mapped[str] = mapped_column(String(255), default="payments:read payments:write", server_default="payments:read payments:write")
    allowed_return_urls: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    allowed_callback_urls: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    callback_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    callback_secret_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    callback_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(250))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("client_id", "code"),)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("client_id", "external_reference", name="uq_payment_client_reference"),
        CheckConstraint("amount > 0", name="ck_payment_positive_amount"),
        Index("ix_payment_created_id", "created_at", "id"),
        Index("ix_payment_client_event_created", "client_id", "event_id", "created_at"),
        ForeignKeyConstraint(["client_id", "event_record_id"], ["portal_events.client_id", "portal_events.id"], name="fk_payment_event_owner"),
        ForeignKeyConstraint(["client_id", "portal_user_id"], ["portal_users.client_id", "portal_users.id"], name="fk_payment_user_owner"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"))
    event_record_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    portal_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    event_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_reference: Mapped[str] = mapped_column(String(150), index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.CREATED)
    winning_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_attempts.id", use_alter=True, name="fk_payment_winning_attempt"),
        nullable=True,
        unique=True,
    )
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("payment_id", "attempt_no", name="uq_attempt_payment_number"),
        Index(
            "uq_attempt_one_active_per_payment",
            "payment_id",
            unique=True,
            postgresql_where=text("status IN ('INITIATED', 'PENDING', 'UNKNOWN')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    gateway: Mapped[str] = mapped_column(String(30))
    channel_code: Mapped[str] = mapped_column(String(80))
    gateway_order_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="INITIATED")
    instructions: Mapped[dict] = mapped_column(JSON, default=dict)


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"
    __table_args__ = (Index("ix_reconciliation_cases_attempt_id", "attempt_id", unique=True),
                      Index("ix_reconciliation_cases_status", "status"),
                      Index("ix_reconciliation_cases_retry_due", "status", "next_retry_at"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_attempts.id"))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="REQUESTED")
    reason: Mapped[str] = mapped_column(String(500))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(150))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"))
    response_body: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("client_id", "idempotency_key"),)


class NonceRecord(Base):
    __tablename__ = "nonce_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    nonce: Mapped[str] = mapped_column(String(150))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("client_id", "nonce"),)


class PaymentStatusHistory(Base):
    __tablename__ = "payment_status_history"
    __table_args__ = (Index("ix_history_payment_time", "payment_id", "occurred_at", "id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    gateway: Mapped[str] = mapped_column(String(30), index=True)
    merchant_code: Mapped[str] = mapped_column(String(100), index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_status: Mapped[str] = mapped_column(String(30), default="RECEIVED")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    refund_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="REQUESTED")
    requested_by_admin: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    payment_status_before: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CallbackDelivery(Base):
    __tablename__ = "callback_deliveries"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"), index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(unique=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(80))
    callback_url: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict] = mapped_column(JSON)
    attempt_no: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_transactions.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
