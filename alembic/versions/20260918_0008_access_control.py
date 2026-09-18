"""OAuth credentials and payment-scoped checkout sessions."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0008"
down_revision = "20260918_0007"
branch_labels = depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("oauth_secret_hash", sa.String(255), nullable=True))
    op.add_column("clients", sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("clients", sa.Column("allowed_scopes", sa.String(255), nullable=False, server_default="payments:read payments:write"))
    op.add_column("clients", sa.Column("allowed_return_urls", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("clients", sa.Column("allowed_callback_urls", sa.JSON(), nullable=False, server_default="[]"))
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("checkout_sessions"):
        # Development auto-DDL may have created this table before the migration.
        columns = {c["name"]: c for c in inspector.get_columns("checkout_sessions")}
        expected = {"id": sa.Uuid, "payment_id": sa.Uuid, "token_hash": sa.String, "expires_at": sa.DateTime}
        if set(columns) != set(expected) or any(not isinstance(columns[k]["type"], kind) or columns[k]["nullable"] for k, kind in expected.items()):
            raise RuntimeError("Existing checkout_sessions schema needs manual review")
        if not any(c["column_names"] == ["token_hash"] for c in inspector.get_unique_constraints("checkout_sessions")):
            raise RuntimeError("Existing checkout token uniqueness constraint missing")
        return
    op.create_table("checkout_sessions", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payment_transactions.id"), nullable=False),
                    sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_checkout_sessions_payment_id", "checkout_sessions", ["payment_id"])


def downgrade():
    op.drop_table("checkout_sessions")
    for column in ("allowed_callback_urls", "allowed_return_urls", "allowed_scopes", "token_version", "oauth_secret_hash"):
        op.drop_column("clients", column)
