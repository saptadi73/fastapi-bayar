"""Protect payment reference, positive money, and attempt sequence.

Revision ID: 20260918_0006
Revises: 20260918_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0006"
down_revision = "20260918_0005"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    checks = (
        "SELECT 1 FROM payment_transactions GROUP BY client_id, external_reference HAVING count(*) > 1 LIMIT 1",
        "SELECT 1 FROM payment_transactions WHERE amount <= 0 LIMIT 1",
        "SELECT 1 FROM payment_attempts GROUP BY payment_id, attempt_no HAVING count(*) > 1 LIMIT 1",
    )
    for query in checks:
        if connection.execute(sa.text(query)).first():
            raise RuntimeError("Existing ledger violates payment invariants; review data before migration. No records removed.")
    op.create_unique_constraint("uq_payment_client_reference", "payment_transactions", ["client_id", "external_reference"])
    op.create_check_constraint("ck_payment_positive_amount", "payment_transactions", "amount > 0")
    op.create_unique_constraint("uq_attempt_payment_number", "payment_attempts", ["payment_id", "attempt_no"])


def downgrade():
    op.drop_constraint("uq_attempt_payment_number", "payment_attempts", type_="unique")
    op.drop_constraint("ck_payment_positive_amount", "payment_transactions", type_="check")
    op.drop_constraint("uq_payment_client_reference", "payment_transactions", type_="unique")
