"""Track provider refund execution and reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0019"
down_revision = "20260918_0018"
branch_labels = depends_on = None

def upgrade():
    for name, column in (("provider_ref", sa.String(100)), ("provider_status", sa.String(50)), ("provider_error_code", sa.String(80))):
        op.add_column("refunds", sa.Column(name, column, nullable=True))
    op.add_column("refunds", sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refunds", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    for name in ("completed_at", "attempted_at", "provider_error_code", "provider_status", "provider_ref"):
        op.drop_column("refunds", name)
