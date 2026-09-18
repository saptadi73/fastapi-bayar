"""Admin reconciliation request queue."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0016"
down_revision = "20260918_0015"
branch_labels = depends_on = None


def upgrade():
    op.create_table("reconciliation_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("attempt_id", sa.Uuid(), sa.ForeignKey("payment_attempts.id"), nullable=False, unique=True),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_status", sa.String(30), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True))
    op.create_index("ix_reconciliation_cases_attempt_id", "reconciliation_cases", ["attempt_id"])
    op.create_index("ix_reconciliation_cases_status", "reconciliation_cases", ["status"])


def downgrade():
    op.drop_index("ix_reconciliation_cases_status", table_name="reconciliation_cases")
    op.drop_index("ix_reconciliation_cases_attempt_id", table_name="reconciliation_cases")
    op.drop_table("reconciliation_cases")
