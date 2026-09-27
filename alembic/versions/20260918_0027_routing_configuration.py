"""Add tenant-scoped merchant, channel, routing and feature configuration."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0027"
down_revision = "20260918_0026"
branch_labels = depends_on = None


def upgrade():
    op.create_table("merchant_accounts",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(200), nullable=False),
        sa.Column("gateway", sa.String(30), nullable=False), sa.Column("credential_ref", sa.String(255)),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "code", name="uq_merchant_client_code"))
    op.create_index("ix_merchant_accounts_client_id", "merchant_accounts", ["client_id"])
    op.create_table("payment_channels",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("merchant_account_id", sa.UUID(), nullable=False),
        sa.Column("gateway", sa.String(30), nullable=False), sa.Column("channel_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("min_amount", sa.BigInteger()), sa.Column("max_amount", sa.BigInteger()),
        sa.Column("currencies", sa.JSON(), server_default='["IDR"]', nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["merchant_account_id"], ["merchant_accounts.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_account_id", "channel_code", name="uq_channel_merchant_code"))
    op.create_index("ix_payment_channels_merchant_account_id", "payment_channels", ["merchant_account_id"])
    op.create_table("merchant_routing_rules",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID()), sa.Column("event_id", sa.String(150)), sa.Column("channel_code", sa.String(80), nullable=False),
        sa.Column("merchant_account_id", sa.UUID(), nullable=False), sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False), sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]), sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["merchant_account_id"], ["merchant_accounts.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "service_id", "event_id", "channel_code", name="uq_routing_rule_scope"))
    op.create_index("ix_merchant_routing_rules_client_id", "merchant_routing_rules", ["client_id"])
    op.create_table("client_feature_flags",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False), sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("config", sa.JSON(), server_default="{}", nullable=False), sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "key", name="uq_feature_flag_client_key"))
    op.create_index("ix_client_feature_flags_client_id", "client_feature_flags", ["client_id"])


def downgrade():
    op.drop_table("client_feature_flags")
    op.drop_table("merchant_routing_rules")
    op.drop_table("payment_channels")
    op.drop_table("merchant_accounts")
