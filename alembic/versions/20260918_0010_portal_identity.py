"""Tenant event/payer identities; preserve nullable legacy payment snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0010"
down_revision = "20260918_0009"
branch_labels = depends_on = None


def upgrade():
    for table, identity, length, name_length, unique, owner in (
        ("portal_events", "event_id", 150, 250, "uq_portal_event_identity", "uq_portal_event_owner"),
        ("portal_users", "email", 320, 200, "uq_portal_user_identity", "uq_portal_user_owner"),
    ):
        op.create_table(table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column(identity, sa.String(length), nullable=False),
            sa.Column("name", sa.String(name_length), nullable=False),
            sa.UniqueConstraint("client_id", identity, name=unique),
            sa.UniqueConstraint("client_id", "id", name=owner))
    for column, kind in (("event_record_id", sa.Uuid()), ("portal_user_id", sa.Uuid()),
                         ("event_id", sa.String(150)), ("event_name", sa.String(250)),
                         ("client_name", sa.String(200))):
        op.add_column("payment_transactions", sa.Column(column, kind, nullable=True))
    op.create_foreign_key("fk_payment_event_owner", "payment_transactions", "portal_events",
                          ["client_id", "event_record_id"], ["client_id", "id"])
    op.create_foreign_key("fk_payment_user_owner", "payment_transactions", "portal_users",
                          ["client_id", "portal_user_id"], ["client_id", "id"])


def downgrade():
    op.drop_constraint("fk_payment_event_owner", "payment_transactions", type_="foreignkey")
    op.drop_constraint("fk_payment_user_owner", "payment_transactions", type_="foreignkey")
    for column in ("event_record_id", "portal_user_id", "event_id", "event_name", "client_name"):
        op.drop_column("payment_transactions", column)
    op.drop_table("portal_users")
    op.drop_table("portal_events")
