"""Normalize reconciliation attempt uniqueness to the ORM unique index."""
from alembic import op

revision = "20260918_0017"
down_revision = "20260918_0016"
branch_labels = depends_on = None


def upgrade():
    op.drop_index("ix_reconciliation_cases_attempt_id", table_name="reconciliation_cases")
    op.drop_constraint("reconciliation_cases_attempt_id_key", "reconciliation_cases", type_="unique")
    op.create_index("ix_reconciliation_cases_attempt_id", "reconciliation_cases", ["attempt_id"], unique=True)


def downgrade():
    op.drop_index("ix_reconciliation_cases_attempt_id", table_name="reconciliation_cases")
    op.create_unique_constraint("reconciliation_cases_attempt_id_key", "reconciliation_cases", ["attempt_id"])
    op.create_index("ix_reconciliation_cases_attempt_id", "reconciliation_cases", ["attempt_id"])
