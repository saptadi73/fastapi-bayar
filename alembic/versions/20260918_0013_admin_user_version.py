"""Optimistic concurrency for admin user management."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0013"
down_revision = "20260918_0012"
branch_labels = depends_on = None


def upgrade():
    op.add_column("admin_users", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("admin_users", "version")
