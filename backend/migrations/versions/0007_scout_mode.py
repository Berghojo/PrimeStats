"""Scouting-Modus: alle gesuchten Spieler zusammen oder mindestens einer

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scouts", sa.Column("mode", sa.String(8), nullable=False, server_default="all"))


def downgrade() -> None:
    op.drop_column("scouts", "mode")
