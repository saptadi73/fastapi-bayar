"""add refund statuses to existing payment enum

Revision ID: 20260918_0002
Revises: 20260918_0001
"""
from alembic import op

revision = "20260918_0002"
down_revision = "20260918_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("REFUND_PENDING", "PARTIALLY_REFUNDED", "REFUNDED"):
        op.execute(f"ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely in-place.
    pass

