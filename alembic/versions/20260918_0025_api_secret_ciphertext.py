"""Add encrypted storage for legacy client HMAC secrets."""
from alembic import op
import sqlalchemy as sa


revision = "20260918_0025"
down_revision = "20260918_0024"
branch_labels = depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("api_secret_ciphertext", sa.String(length=1024), nullable=True))


def downgrade():
    op.drop_column("clients", "api_secret_ciphertext")
