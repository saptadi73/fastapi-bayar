"""Allow customers without email; preserve existing values.

Revision ID: 20260918_0005
Revises: 20260918_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0005"
down_revision = "20260918_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("payment_transactions", "customer_email", existing_type=sa.String(320), nullable=True)


def downgrade() -> None:
    # Fail before changing schema if real customers lack email; never invent addresses.
    missing = op.get_bind().execute(sa.text("SELECT 1 FROM payment_transactions WHERE customer_email IS NULL LIMIT 1")).first()
    if missing:
        raise RuntimeError("Cannot downgrade: customers with NULL email exist; resolve their data first")
    op.alter_column("payment_transactions", "customer_email", existing_type=sa.String(320), nullable=False)
