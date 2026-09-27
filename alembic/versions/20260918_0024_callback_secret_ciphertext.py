"""Add encrypted storage for callback secrets; legacy plaintext is migrated separately."""
from alembic import op
import sqlalchemy as sa


revision = "20260918_0024"
down_revision = "20260918_0023"
branch_labels = depends_on = None


def upgrade():
    op.add_column("clients", sa.Column("callback_secret_ciphertext", sa.String(length=1024), nullable=True))


def downgrade():
    op.drop_column("clients", "callback_secret_ciphertext")
