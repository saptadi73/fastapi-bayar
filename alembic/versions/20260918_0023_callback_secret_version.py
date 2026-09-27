"""Track callback secret rotations independently from OAuth secret rotations."""
from alembic import op
import sqlalchemy as sa


revision = "20260918_0023"
down_revision = "20260918_0022"
branch_labels = depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("callback_secret_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("clients", "callback_secret_version")
