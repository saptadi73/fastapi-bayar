"""Add MFA, recovery, forced-password and reauthentication state."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0029"
down_revision = "20260918_0028"
branch_labels = depends_on = None


def upgrade():
    op.add_column("admin_users", sa.Column("mfa_secret_ciphertext", sa.String(1024), nullable=True))
    op.add_column("admin_users", sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("admin_users", sa.Column("recovery_codes_hash", sa.JSON(), server_default="[]", nullable=False))
    op.add_column("admin_users", sa.Column("force_password_change", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("admin_sessions", sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("admin_sessions", "reauthenticated_at")
    op.drop_column("admin_users", "force_password_change")
    op.drop_column("admin_users", "recovery_codes_hash")
    op.drop_column("admin_users", "mfa_enabled")
    op.drop_column("admin_users", "mfa_secret_ciphertext")
