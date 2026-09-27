"""Persist the winning payment attempt."""
from alembic import op
import sqlalchemy as sa


revision = "20260918_0021"
down_revision = "20260918_0020"
branch_labels = depends_on = None


def upgrade():
    op.add_column("payment_transactions", sa.Column("winning_attempt_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_payment_winning_attempt",
        "payment_transactions",
        "payment_attempts",
        ["winning_attempt_id"],
        ["id"],
    )
    op.create_unique_constraint("uq_payment_winning_attempt", "payment_transactions", ["winning_attempt_id"])


def downgrade():
    op.drop_constraint("uq_payment_winning_attempt", "payment_transactions", type_="unique")
    op.drop_constraint("fk_payment_winning_attempt", "payment_transactions", type_="foreignkey")
    op.drop_column("payment_transactions", "winning_attempt_id")
