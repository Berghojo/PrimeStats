"""Initiales Schema: API-Cache und Teams

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("riot_id", sa.Text(), primary_key=True),
        sa.Column("puuid", sa.String(100), nullable=False),
        sa.Column("game_name", sa.Text(), nullable=False),
        sa.Column("tag_line", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_accounts_puuid", "accounts", ["puuid"])
    op.create_table(
        "matches",
        sa.Column("match_id", sa.String(40), primary_key=True),
        sa.Column("game_creation", sa.BigInteger()),
        sa.Column("data", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_matches_game_creation", "matches", ["game_creation"])
    op.create_table(
        "timelines",
        sa.Column("match_id", sa.String(40), primary_key=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "timeline_summaries",
        sa.Column("match_id", sa.String(40), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("min_members", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_synced", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "team_members",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("puuid", sa.String(100), primary_key=True),
        sa.Column("game_name", sa.Text(), nullable=False),
        sa.Column("tag_line", sa.Text(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
    )
    op.create_table(
        "team_games",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("match_id", sa.String(40), primary_key=True),
        sa.Column("side", sa.SmallInteger(), nullable=False),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    for table in ("team_games", "team_members", "teams", "timeline_summaries", "timelines", "matches",
                  "accounts"):
        op.drop_table(table)
