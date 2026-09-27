"""Add bounded retry scheduling to reconciliation cases."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0020"
down_revision = "20260918_0019"
branch_labels = depends_on = None


def upgrade():
    op.add_column("reconciliation_cases", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("reconciliation_cases", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_reconciliation_cases_retry_due", "reconciliation_cases", ["status", "next_retry_at"])


def downgrade():
    op.drop_index("ix_reconciliation_cases_retry_due", table_name="reconciliation_cases")
    op.drop_column("reconciliation_cases", "next_retry_at")
    op.drop_column("reconciliation_cases", "retry_count")
