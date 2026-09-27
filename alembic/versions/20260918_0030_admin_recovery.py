"""Add admin invitation and password-reset tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0030"
down_revision = "20260918_0029"
branch_labels = depends_on = None


def upgrade():
    op.create_table("admin_invitations",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(320), nullable=False), sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(40), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)), sa.Column("created_by", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"))
    op.create_index("ix_admin_invitations_token_hash", "admin_invitations", ["token_hash"])
    op.create_index("ix_admin_invitations_email", "admin_invitations", ["email"])
    op.create_table("admin_password_resets",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"))
    op.create_index("ix_admin_password_resets_token_hash", "admin_password_resets", ["token_hash"])
    op.create_index("ix_admin_password_resets_user_id", "admin_password_resets", ["user_id"])


def downgrade():
    op.drop_table("admin_password_resets")
    op.drop_table("admin_invitations")
