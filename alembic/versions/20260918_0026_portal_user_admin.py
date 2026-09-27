"""Add PortalUser optimistic version and sanitized audit details."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0026"
down_revision = "20260918_0025"
branch_labels = depends_on = None


def upgrade():
    op.add_column("portal_users", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("admin_audit", sa.Column("details_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("admin_audit", "details_json")
    op.drop_column("portal_users", "version")
