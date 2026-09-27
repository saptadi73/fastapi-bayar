"""Add database-configurable admin roles and client assignments."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0031"
down_revision = "20260918_0030"
branch_labels = depends_on = None


def upgrade():
    op.create_table("admin_roles",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("code", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False), sa.Column("permissions_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False), sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("code"))
    op.create_table("admin_client_assignments",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False), sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]), sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "client_id", name="uq_admin_user_client_assignment"))
    op.create_index("ix_admin_client_assignments_user_id", "admin_client_assignments", ["user_id"])
    op.create_index("ix_admin_client_assignments_client_id", "admin_client_assignments", ["client_id"])


def downgrade():
    op.drop_table("admin_client_assignments")
    op.drop_table("admin_roles")
