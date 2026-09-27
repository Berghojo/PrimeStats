"""Turnier-Scouting

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scouts",
        sa.Column("puuid", sa.String(100), primary_key=True),
        sa.Column("game_name", sa.Text(), nullable=False),
        sa.Column("tag_line", sa.Text(), nullable=False),
        sa.Column("roster", postgresql.JSONB(), nullable=False),
        sa.Column("games", postgresql.JSONB(), nullable=False),
        sa.Column("min_members", sa.SmallInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scouts_updated_at", "scouts", ["updated_at"])


def downgrade() -> None:
    op.drop_table("scouts")
