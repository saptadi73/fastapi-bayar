"""Add tenant-scoped organizer master and service ownership."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0028"
down_revision = "20260918_0027"
branch_labels = depends_on = None


def upgrade():
    op.create_table("organizers",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "code", name="uq_organizer_client_code"))
    op.create_index("ix_organizers_client_id", "organizers", ["client_id"])
    op.add_column("services", sa.Column("organizer_id", sa.UUID(), nullable=True))
    op.create_index("ix_services_organizer_id", "services", ["organizer_id"])
    op.create_foreign_key("fk_services_organizer", "services", "organizers", ["organizer_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_services_organizer", "services", type_="foreignkey")
    op.drop_index("ix_services_organizer_id", table_name="services")
    op.drop_column("services", "organizer_id")
    op.drop_index("ix_organizers_client_id", table_name="organizers")
    op.drop_table("organizers")
