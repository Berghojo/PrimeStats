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
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    #: Öffentliche Teams (inkl. Scrims) sind für alle sichtbar, private nur für Mitglieder/Ersteller
    public: Mapped[bool] = mapped_column(Boolean, default=False)

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
    #: Gegner, frei eingetragen vom Team (z.B. für Scrims)
    opponent: Mapped[str] = mapped_column(String(40), default="")
    #: von Hand nachgetragene Bans {"us": [...], "them": [...]} (Custom-Lobby im Blind-Modus hat keine)
    bans: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PuuidAlias(Base):
    """League-Client-PUUID -> PUUID der Riot-API.

    Der Client kennt Spieler unter ihrer unverschlüsselten PUUID (UUID-Format), die Riot-API nur
    unter der je API-Key verschlüsselten. Hochgeladene Spiele werden auf die API-PUUID umgestellt,
    damit sie zu Teams, Verknüpfungen und Turnierspielen passen.
    """

    __tablename__ = "puuid_aliases"

    client_puuid: Mapped[str] = mapped_column(String(100), primary_key=True)
    puuid: Mapped[str] = mapped_column(String(100))


# ------------------------------------------------------------ LCU-Importe
class RawImport(Base):
    """Originaldaten aus dem League Client – erlaubt spätere Neukonvertierung."""

    __tablename__ = "raw_imports"

    match_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    game: Mapped[dict] = mapped_column(JSONB)
    timeline: Mapped[dict | None] = mapped_column(JSONB)
    uploader: Mapped[str] = mapped_column(Text, default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ----------------------------------------------------------------- Konten
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64))
    #: lower-case Benutzername für eindeutige Anmeldung
    username_key: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiotLink(Base):
    """Mit einem Konto verknüpfter Riot-Account (Nachweis über das Uploader-Tool)."""

    __tablename__ = "riot_links"

    puuid: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    game_name: Mapped[str] = mapped_column(Text)
    tag_line: Mapped[str] = mapped_column(Text)
    #: Hash des Geräteschlüssels, den das Tool beim Verknüpfen erhalten hat
    key_hash: Mapped[str] = mapped_column(String(64))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_upload_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LinkCode(Base):
    __tablename__ = "link_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SavedView(Base):
    """Gespeicherte Ansicht (sichtbare Panels in fester Reihenfolge) eines Kontos."""

    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    #: wofür die Ansicht gilt (derzeit nur "scout")
    kind: Mapped[str] = mapped_column(String(16), default="scout")
    name: Mapped[str] = mapped_column(String(40))
    panels: Mapped[list] = mapped_column(JSONB)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlayerMatch(Base):
    """Welche Spiele eines Spielers aus welcher Queue geladen wurden (Spieler-Einzelansicht)."""

    __tablename__ = "player_matches"

    puuid: Mapped[str] = mapped_column(String(100), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    #: "solo", "flex" oder "tourney"
    queue: Mapped[str] = mapped_column(String(10))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Group(Base):
    """Gruppe eines Kontos: mehrere Teams/Scoutings, die miteinander verglichen werden."""

    __tablename__ = "groups"

    #: zufälliger Schlüssel (teilbarer Link)
    key: Mapped[str] = mapped_column(String(24), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    #: [{"kind": "team"|"scout", "ref": "<team-id>|<scout-key>", "name": "<optional>"}]
    entries: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------- Scouting
class Scout(Base):
    """Ergebnis eines Turnier-Scoutings: Spiele, in denen alle gesuchten Spieler im selben Team standen."""

    __tablename__ = "scouts"

    #: Hash der sortierten PUUIDs der gesuchten Spieler
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    #: gesuchte Spieler [{puuid, game_name, tag_line}]
    players: Mapped[list] = mapped_column(JSONB)
    #: "all" = alle gesuchten Spieler im selben Team, "any" = mindestens einer spielt mit
    mode: Mapped[str] = mapped_column(String(8), default="all")
    #: alle Spieler, die in diesen Spielen im Team standen (gesuchte zuerst)
    roster: Mapped[list] = mapped_column(JSONB)
    #: [[match_id, side], ...]
    games: Mapped[list] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
