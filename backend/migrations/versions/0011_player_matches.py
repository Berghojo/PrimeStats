"""Spiele je Spieler und Queue (Spieler-Einzelansicht)

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_matches",
        sa.Column("puuid", sa.String(100), primary_key=True),
        sa.Column("match_id", sa.String(40), primary_key=True),
        sa.Column("queue", sa.String(10), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("player_matches")
