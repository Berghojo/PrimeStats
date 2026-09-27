"""SQLAlchemy-Modelle (PostgreSQL)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text,
                        func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------ API-Cache
class Account(Base):
    __tablename__ = "accounts"

    riot_id: Mapped[str] = mapped_column(Text, primary_key=True)  # lower-case "name#tag"
    puuid: Mapped[str] = mapped_column(String(100), index=True)
    game_name: Mapped[str] = mapped_column(Text)
    tag_line: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    game_creation: Mapped[int | None] = mapped_column(BigInteger, index=True)
    data: Mapped[dict] = mapped_column(JSONB)


class Timeline(Base):
    __tablename__ = "timelines"

    match_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB)


class TimelineSummary(Base):
    __tablename__ = "timeline_summaries"

    match_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSONB)


# --------------------------------------------------------------------- Teams
class TeamRow(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    tag: Mapped[str] = mapped_column(Text, default="")
    min_members: Mapped[int] = mapped_column(SmallInteger, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    members: Mapped[list["TeamMemberRow"]] = relationship(
        back_populates="team", cascade="all, delete-orphan", order_by="TeamMemberRow.position",
        passive_deletes=True)


class TeamMemberRow(Base):
    __tablename__ = "team_members"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    puuid: Mapped[str] = mapped_column(String(100), primary_key=True)
    game_name: Mapped[str] = mapped_column(Text)
    tag_line: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(10), default="")
    position: Mapped[int] = mapped_column(SmallInteger, default=0)

    team: Mapped[TeamRow] = relationship(back_populates="members")


class TeamGameRow(Base):
    __tablename__ = "team_games"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    side: Mapped[int] = mapped_column(SmallInteger)            # teamId des Teams (100/200)
    label: Mapped[str] = mapped_column(String(20), default="")  # '', 'official', 'scrim'
    included: Mapped[bool] = mapped_column(Boolean, default=True)
