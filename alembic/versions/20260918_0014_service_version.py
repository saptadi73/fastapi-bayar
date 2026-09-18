"""Version service configuration for concurrent admin edits."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0014"
down_revision = "20260918_0013"
branch_labels = depends_on = None


def upgrade():
    op.add_column("services", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("services", "version")
