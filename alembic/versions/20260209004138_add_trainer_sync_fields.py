"""Add trainer sync fields.

Revision ID: 20260209004138
Revises:
Create Date: 2026-02-09 00:41:38.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260209004138"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trainers", sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("trainers", sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("trainers", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("trainers", "sync_enabled", server_default=None)
    op.alter_column("trainers", "sync_interval_minutes", server_default=None)


def downgrade() -> None:
    op.drop_column("trainers", "last_synced_at")
    op.drop_column("trainers", "sync_interval_minutes")
    op.drop_column("trainers", "sync_enabled")
