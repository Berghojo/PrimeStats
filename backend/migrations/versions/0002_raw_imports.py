"""Rohdaten von LCU-Importen

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_imports",
        sa.Column("match_id", sa.String(40), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("game", postgresql.JSONB(), nullable=False),
        sa.Column("timeline", postgresql.JSONB()),
        sa.Column("uploader", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("raw_imports")
