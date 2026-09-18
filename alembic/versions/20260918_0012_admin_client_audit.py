"""Resource identity and reason for admin client mutations."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0012"
down_revision = "20260918_0011"
branch_labels = depends_on = None


def upgrade():
    op.add_column("admin_audit", sa.Column("resource_id", sa.String(100), nullable=True))
    op.add_column("admin_audit", sa.Column("reason", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("admin_audit", "reason")
    op.drop_column("admin_audit", "resource_id")
