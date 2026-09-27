"""Benutzerkonten, Riot-Verknüpfungen, Team-Besitzer

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(32), nullable=False),
        sa.Column("username_key", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "user_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_table(
        "riot_links",
        sa.Column("puuid", sa.String(100), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_name", sa.Text(), nullable=False),
        sa.Column("tag_line", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_upload_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_riot_links_user_id", "riot_links", ["user_id"])
    op.create_table(
        "link_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_link_codes_user_id", "link_codes", ["user_id"])
    op.add_column("teams", sa.Column("owner_id", sa.Integer(),
                                     sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_teams_owner_id", "teams", ["owner_id"])
    op.add_column("teams", sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_index("ix_teams_owner_id", "teams")
    op.drop_column("teams", "public")
    op.drop_column("teams", "owner_id")
    for table in ("link_codes", "riot_links", "user_sessions", "users"):
        op.drop_table(table)
