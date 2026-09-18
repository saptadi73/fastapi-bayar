"""Indexes for read-only admin ledger browsing."""
from alembic import op

revision = "20260918_0015"
down_revision = "20260918_0014"
branch_labels = depends_on = None


def upgrade():
    op.create_index("ix_payment_created_id", "payment_transactions", ["created_at", "id"])
    op.create_index("ix_payment_client_event_created", "payment_transactions", ["client_id", "event_id", "created_at"])
    op.create_index("ix_history_payment_time", "payment_status_history", ["payment_id", "occurred_at", "id"])


def downgrade():
    op.drop_index("ix_history_payment_time", table_name="payment_status_history")
    op.drop_index("ix_payment_client_event_created", table_name="payment_transactions")
    op.drop_index("ix_payment_created_id", table_name="payment_transactions")
