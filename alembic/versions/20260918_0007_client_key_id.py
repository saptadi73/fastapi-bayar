"""Bind HMAC key identifier to the client credential.

Revision ID: 20260918_0007
Revises: 20260918_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0007"
down_revision = "20260918_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("key_id", sa.String(100), nullable=False, server_default="key-2026-01"))


def downgrade():
    op.drop_column("clients", "key_id")
