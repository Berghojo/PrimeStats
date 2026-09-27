"""Frei eintragbarer Gegner je Teamspiel

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("team_games", sa.Column("opponent", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("team_games", "opponent")
