"""Längere Anmeldenamen (E-Mail-Adressen erlaubt)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "username", type_=sa.String(64), existing_nullable=False)
    op.alter_column("users", "username_key", type_=sa.String(64), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("users", "username_key", type_=sa.String(32), existing_nullable=False)
    op.alter_column("users", "username", type_=sa.String(32), existing_nullable=False)
