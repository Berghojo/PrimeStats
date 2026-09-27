"""Von Hand nachgetragene Bans je Teamspiel

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("team_games", sa.Column("bans", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("team_games", "bans")
