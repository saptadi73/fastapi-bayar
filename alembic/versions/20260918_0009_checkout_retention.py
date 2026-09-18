"""Index checkout expiration for bounded retention cleanup."""
from alembic import op

revision = "20260918_0009"
down_revision = "20260918_0008"
branch_labels = depends_on = None


def upgrade():
    op.create_index("ix_checkout_sessions_expires_at", "checkout_sessions", ["expires_at"])


def downgrade():
    op.drop_index("ix_checkout_sessions_expires_at", table_name="checkout_sessions")
