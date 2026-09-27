"""Zuordnung League-Client-PUUID -> Riot-API-PUUID

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "puuid_aliases",
        sa.Column("client_puuid", sa.String(100), primary_key=True),
        sa.Column("puuid", sa.String(100), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("puuid_aliases")
