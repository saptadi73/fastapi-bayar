"""add callback outbox

Revision ID: 20260918_0003
Revises: 20260918_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0003"
down_revision = "20260918_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("callback_deliveries", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id"), nullable=False), sa.Column("event_id", sa.Uuid(), nullable=False), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("callback_url", sa.String(500), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"), sa.Column("next_retry_at", sa.DateTime(timezone=True)), sa.Column("sent_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("event_id"))
    op.create_index("ix_callback_deliveries_payment_id", "callback_deliveries", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_callback_deliveries_payment_id", table_name="callback_deliveries")
    op.drop_table("callback_deliveries")
