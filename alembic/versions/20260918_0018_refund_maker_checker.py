"""Add refund maker-checker fields."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0018"
down_revision = "20260918_0017"
branch_labels = depends_on = None

def upgrade():
    op.add_column("refunds", sa.Column("requested_by_admin", sa.Uuid(), nullable=True))
    op.add_column("refunds", sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.add_column("refunds", sa.Column("rejected_by", sa.Uuid(), nullable=True))
    op.add_column("refunds", sa.Column("payment_status_before", sa.String(30), nullable=True))
    op.add_column("refunds", sa.Column("rejection_reason", sa.String(500), nullable=True))
    op.add_column("refunds", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refunds", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refunds", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    for name, column in (("fk_refunds_requested_by_admin", "requested_by_admin"), ("fk_refunds_approved_by", "approved_by"), ("fk_refunds_rejected_by", "rejected_by")):
        op.create_foreign_key(name, "refunds", "admin_users", [column], ["id"])

def downgrade():
    for name in ("fk_refunds_rejected_by", "fk_refunds_approved_by", "fk_refunds_requested_by_admin"):
        op.drop_constraint(name, "refunds", type_="foreignkey")
    for column in ("version", "rejected_at", "approved_at", "rejection_reason", "payment_status_before", "rejected_by", "approved_by", "requested_by_admin"):
        op.drop_column("refunds", column)
