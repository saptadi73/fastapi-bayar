"""add callback signing secret

Revision ID: 20260918_0004
Revises: 20260918_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0004"
down_revision = "20260918_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("callback_secret", sa.String(255)))


def downgrade() -> None:
    op.drop_column("clients", "callback_secret")

