"""initial payment portal schema

Revision ID: 20260918_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    payment_status = sa.Enum("CREATED", "PENDING", "PAID", "EXPIRED", "CANCELLED", "FAILED", "REFUND_PENDING", "PARTIALLY_REFUNDED", "REFUNDED", name="paymentstatus")
    payment_status.create(op.get_bind(), checkfirst=True)
    op.create_table("clients", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("code", sa.String(50), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("api_secret", sa.String(255), nullable=False), sa.Column("callback_url", sa.String(500)), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.UniqueConstraint("code"))
    op.create_index("ix_clients_code", "clients", ["code"], unique=False)
    op.create_table("services", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False), sa.Column("code", sa.String(100), nullable=False), sa.Column("name", sa.String(250), nullable=False), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.UniqueConstraint("client_id", "code"))
    op.create_index("ix_services_client_id", "services", ["client_id"])
    op.create_index("ix_services_code", "services", ["code"])
    op.create_table("payment_transactions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("payment_no", sa.String(40), nullable=False), sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False), sa.Column("service_id", sa.Uuid(), sa.ForeignKey("services.id"), nullable=False), sa.Column("external_reference", sa.String(150), nullable=False), sa.Column("description", sa.String(500)), sa.Column("amount", sa.BigInteger(), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="IDR"), sa.Column("status", payment_status, nullable=False), sa.Column("customer_name", sa.String(200), nullable=False), sa.Column("customer_email", sa.String(320), nullable=False), sa.Column("customer_phone", sa.String(40)), sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("return_url", sa.String(500)), sa.Column("metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("payment_no"))
    op.create_index("ix_payment_transactions_payment_no", "payment_transactions", ["payment_no"])
    op.create_index("ix_payment_transactions_client_id", "payment_transactions", ["client_id"])
    op.create_index("ix_payment_transactions_external_reference", "payment_transactions", ["external_reference"])
    op.create_table("payment_attempts", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id"), nullable=False), sa.Column("attempt_no", sa.Integer(), nullable=False), sa.Column("gateway", sa.String(30), nullable=False), sa.Column("channel_code", sa.String(80), nullable=False), sa.Column("gateway_order_id", sa.String(100), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("instructions", sa.JSON(), nullable=False), sa.UniqueConstraint("gateway_order_id"))
    op.create_index("ix_payment_attempts_payment_id", "payment_attempts", ["payment_id"])
    op.create_table("idempotency_records", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False), sa.Column("idempotency_key", sa.String(150), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("resource_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id"), nullable=False), sa.Column("response_body", sa.JSON(), nullable=False), sa.UniqueConstraint("client_id", "idempotency_key"))
    op.create_index("ix_idempotency_records_client_id", "idempotency_records", ["client_id"])
    op.create_table("nonce_records", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False), sa.Column("nonce", sa.String(150), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("client_id", "nonce"))
    op.create_index("ix_nonce_records_client_id", "nonce_records", ["client_id"])
    op.create_table("payment_status_history", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id"), nullable=False), sa.Column("from_status", sa.String(30)), sa.Column("to_status", sa.String(30), nullable=False), sa.Column("source", sa.String(50), nullable=False), sa.Column("reason", sa.String(500)), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_payment_status_history_payment_id", "payment_status_history", ["payment_id"])
    op.create_table("webhook_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("gateway", sa.String(30), nullable=False), sa.Column("merchant_code", sa.String(100), nullable=False), sa.Column("provider_event_id", sa.String(255)), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("signature_valid", sa.Boolean(), nullable=False), sa.Column("processing_status", sa.String(30), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_webhook_events_gateway", "webhook_events", ["gateway"])
    op.create_index("ix_webhook_events_merchant_code", "webhook_events", ["merchant_code"])
    op.create_index("ix_webhook_events_payload_hash", "webhook_events", ["payload_hash"])
    op.create_table("refunds", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("refund_no", sa.String(50), nullable=False), sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id"), nullable=False), sa.Column("amount", sa.BigInteger(), nullable=False), sa.Column("reason", sa.String(500), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("refund_no"))
    op.create_index("ix_refunds_refund_no", "refunds", ["refund_no"])
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])


def downgrade() -> None:
    for table in ["refunds", "webhook_events", "payment_status_history", "nonce_records", "idempotency_records", "payment_attempts", "payment_transactions", "services", "clients"]:
        op.drop_table(table)
    sa.Enum(name="paymentstatus").drop(op.get_bind(), checkfirst=True)

