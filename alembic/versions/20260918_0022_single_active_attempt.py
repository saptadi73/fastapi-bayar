"""Enforce one active provider attempt per payment."""
from alembic import op
import sqlalchemy as sa


revision = "20260918_0022"
down_revision = "20260918_0021"
branch_labels = depends_on = None


def upgrade():
    op.create_index(
        "uq_attempt_one_active_per_payment",
        "payment_attempts",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('INITIATED', 'PENDING', 'UNKNOWN')"),
    )


def downgrade():
    op.drop_index("uq_attempt_one_active_per_payment", table_name="payment_attempts")
