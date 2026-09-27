"""Persistenz in PostgreSQL: API-Cache (Accounts, Matches, Timelines) und Teams.

Matchdaten ändern sich nach Spielende nie mehr, deshalb wird alles, was einmal
von der Riot-API geladen wurde, dauerhaft als JSONB gespeichert. Das schont das
Rate-Limit enorm.
"""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.dialects.postgresql import array, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .auth import token_hash
from .db import (Account, LinkCode, Match, RawImport, RiotLink, Scout, TeamGameRow, TeamMemberRow, TeamRow,
                 Timeline, TimelineSummary, User, UserSession)


@dataclass
class Member:
    puuid: str
    game_name: str
    tag_line: str
    role: str = ""

    @property
    def riot_id(self) -> str:
        return f"{self.game_name}#{self.tag_line}"


@dataclass
class Team:
    id: int
    name: str
    tag: str
    min_members: int
    created_at: datetime
    last_synced: datetime | None
    members: list[Member]
    owner_id: int | None = None
    public: bool = False

    @property
    def puuids(self) -> set[str]:
        return {m.puuid for m in self.members}


@dataclass
class UserAccount:
    id: int
    username: str
    created_at: datetime


@dataclass
class LinkedRiot:
    puuid: str
    game_name: str
    tag_line: str
    linked_at: datetime
    last_upload_at: datetime | None

    @property
    def riot_id(self) -> str:
        return f"{self.game_name}#{self.tag_line}"


@dataclass
class TeamGame:
    match_id: str
    side: int
    label: str
    included: bool
    opponent: str = ""


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


class Store:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, url: str) -> "Store":
        return cls(make_engine(url))

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions.begin() as session:
            yield session

    # ------------------------------------------------------------------ cache
    def get_account(self, riot_id: str) -> dict | None:
        with self.session() as s:
            row = s.get(Account, riot_id.lower())
            if not row:
                return None
            return {"puuid": row.puuid, "gameName": row.game_name, "tagLine": row.tag_line}

    def put_account(self, riot_id: str, account: dict) -> None:
        values = {"riot_id": riot_id.lower(), "puuid": account["puuid"], "game_name": account["gameName"],
                  "tag_line": account["tagLine"], "fetched_at": datetime.now(timezone.utc)}
        stmt = insert(Account).values(**values)
        stmt = stmt.on_conflict_do_update(index_elements=[Account.riot_id], set_=values)
        with self.session() as s:
            s.execute(stmt)

    def get_match(self, match_id: str) -> dict | None:
        with self.session() as s:
            return s.scalar(select(Match.data).where(Match.match_id == match_id))

    def put_match(self, match_id: str, data: dict) -> None:
        created = data.get("info", {}).get("gameCreation")
        stmt = insert(Match).values(match_id=match_id, game_creation=created, data=data)
        stmt = stmt.on_conflict_do_update(index_elements=[Match.match_id],
                                          set_={"data": data, "game_creation": created})
        with self.session() as s:
            s.execute(stmt)

    def get_timeline(self, match_id: str) -> dict | None:
        with self.session() as s:
            return s.scalar(select(Timeline.data).where(Timeline.match_id == match_id))

    def put_timeline(self, match_id: str, data: dict) -> None:
        stmt = insert(Timeline).values(match_id=match_id, data=data)
        stmt = stmt.on_conflict_do_update(index_elements=[Timeline.match_id], set_={"data": data})
        with self.session() as s:
            s.execute(stmt)

    def get_timeline_summary(self, match_id: str, version: int) -> dict | None:
        with self.session() as s:
            return s.scalar(select(TimelineSummary.data).where(
                TimelineSummary.match_id == match_id, TimelineSummary.version == version))

    def put_timeline_summary(self, match_id: str, version: int, data: dict) -> None:
        stmt = insert(TimelineSummary).values(match_id=match_id, version=version, data=data)
        stmt = stmt.on_conflict_do_update(index_elements=[TimelineSummary.match_id],
                                          set_={"version": version, "data": data})
        with self.session() as s:
            s.execute(stmt)

    def get_matches(self, match_ids: list[str]) -> dict[str, dict]:
        if not match_ids:
            return {}
        with self.session() as s:
            rows = s.execute(select(Match.match_id, Match.data).where(Match.match_id.in_(match_ids)))
            return {mid: data for mid, data in rows}

    def get_timeline_summaries(self, match_ids: list[str], version: int) -> dict[str, dict]:
        if not match_ids:
            return {}
        with self.session() as s:
            rows = s.execute(select(TimelineSummary.match_id, TimelineSummary.data).where(
                TimelineSummary.match_id.in_(match_ids), TimelineSummary.version == version))
            return {mid: data for mid, data in rows}

    def existing_matches(self, match_ids: list[str]) -> set[str]:
        if not match_ids:
            return set()
        with self.session() as s:
            return set(s.scalars(select(Match.match_id).where(Match.match_id.in_(match_ids))))

    def matches_with_players(self, puuids: set[str]) -> list[str]:
        """Gespeicherte Matches, an denen mindestens einer der Spieler teilgenommen hat."""
        if not puuids:
            return []
        participants = Match.data["metadata"]["participants"]
        with self.session() as s:
            return list(s.scalars(select(Match.match_id).where(participants.has_any(array(sorted(puuids))))))

    def put_raw_import(self, match_id: str, source: str, game: dict, timeline: dict | None,
                       uploader: str = "") -> None:
        values = {"match_id": match_id, "source": source, "game": game, "timeline": timeline,
                  "uploader": uploader}
        stmt = insert(RawImport).values(**values).on_conflict_do_update(
            index_elements=[RawImport.match_id], set_={k: v for k, v in values.items() if k != "match_id"})
        with self.session() as s:
            s.execute(stmt)

    def raw_imports(self) -> list[tuple[str, dict, dict | None]]:
        with self.session() as s:
            return [tuple(r) for r in s.execute(select(RawImport.match_id, RawImport.game, RawImport.timeline))]

    def summarized_matches(self, match_ids: list[str], version: int) -> set[str]:
        if not match_ids:
            return set()
        with self.session() as s:
            rows = s.scalars(select(TimelineSummary.match_id).where(
                TimelineSummary.match_id.in_(match_ids), TimelineSummary.version == version))
            return set(rows)

    # ------------------------------------------------------------------ teams
    @staticmethod
    def _member_rows(members: list[Member]) -> list[TeamMemberRow]:
        return [TeamMemberRow(puuid=m.puuid, game_name=m.game_name, tag_line=m.tag_line, role=m.role,
                              position=i) for i, m in enumerate(members)]

    def create_team(self, name: str, tag: str, min_members: int, members: list[Member],
                    owner_id: int | None = None, public: bool = False) -> int:
        with self.session() as s:
            row = TeamRow(name=name, tag=tag, min_members=min_members, members=self._member_rows(members),
                          owner_id=owner_id, public=public)
            s.add(row)
            s.flush()
            return row.id

    def update_team(self, team_id: int, name: str, tag: str, min_members: int, members: list[Member],
                    public: bool | None = None) -> None:
        with self.session() as s:
            row = s.get(TeamRow, team_id)
            if row is None:
                return
            row.name, row.tag, row.min_members = name, tag, min_members
            if public is not None:
                row.public = public
            row.members.clear()
            s.flush()
            row.members.extend(self._member_rows(members))

    def delete_team(self, team_id: int) -> None:
        with self.session() as s:
            s.execute(delete(TeamRow).where(TeamRow.id == team_id))

    @staticmethod
    def _to_team(row: TeamRow) -> Team:
        return Team(
            id=row.id, name=row.name, tag=row.tag, min_members=row.min_members,
            created_at=row.created_at, last_synced=row.last_synced,
            members=[Member(m.puuid, m.game_name, m.tag_line, m.role) for m in row.members],
            owner_id=row.owner_id, public=row.public,
        )

    def list_teams(self) -> list[Team]:
        with self.session() as s:
            rows = s.scalars(select(TeamRow).order_by(TeamRow.name))
            return [self._to_team(r) for r in rows]

    def get_team(self, team_id: int) -> Team | None:
        with self.session() as s:
            row = s.get(TeamRow, team_id)
            return self._to_team(row) if row else None

    def mark_synced(self, team_id: int) -> None:
        with self.session() as s:
            s.execute(update(TeamRow).where(TeamRow.id == team_id)
                      .values(last_synced=datetime.now(timezone.utc)))

    def add_team_games(self, team_id: int, games: list[tuple[str, int, str]]) -> int:
        """Fügt (match_id, side, label) hinzu; bestehende Einträge bleiben unverändert."""
        if not games:
            return 0
        stmt = insert(TeamGameRow).values(
            [{"team_id": team_id, "match_id": mid, "side": side, "label": label, "included": True, "opponent": ""}
             for mid, side, label in games]
        ).on_conflict_do_nothing().returning(TeamGameRow.match_id)
        with self.session() as s:
            return len(s.execute(stmt).all())

    def team_games(self, team_id: int) -> list[TeamGame]:
        with self.session() as s:
            rows = s.execute(
                select(TeamGameRow.match_id, TeamGameRow.side, TeamGameRow.label, TeamGameRow.included,
                       TeamGameRow.opponent)
                .outerjoin(Match, Match.match_id == TeamGameRow.match_id)
                .where(TeamGameRow.team_id == team_id)
                .order_by(Match.game_creation.desc().nulls_last(), TeamGameRow.match_id.desc())
            )
            return [TeamGame(*r) for r in rows]

    def update_team_game(self, team_id: int, match_id: str, *, label: str | None = None,
                         included: bool | None = None, opponent: str | None = None) -> bool:
        values: dict = {}
        if opponent is not None:
            values["opponent"] = opponent
        if label is not None:
            values["label"] = label
        if included is not None:
            values["included"] = included
        with self.session() as s:
            if not values:
                return s.get(TeamGameRow, (team_id, match_id)) is not None
            result = s.execute(update(TeamGameRow).where(
                TeamGameRow.team_id == team_id, TeamGameRow.match_id == match_id).values(**values))
            return result.rowcount > 0

    # ----------------------------------------------------------------- Konten
    def create_user(self, username: str, password_hash: str) -> UserAccount | None:
        """Legt ein Konto an; ``None``, wenn der Name (Groß-/Kleinschreibung egal) vergeben ist."""
        stmt = insert(User).values(username=username, username_key=username.lower(),
                                   password_hash=password_hash).on_conflict_do_nothing().returning(User.id)
        with self.session() as s:
            user_id = s.execute(stmt).scalar()
            if user_id is None:
                return None
            row = s.get(User, user_id)
            return UserAccount(row.id, row.username, row.created_at)

    def user_credentials(self, username: str) -> tuple[UserAccount, str] | None:
        with self.session() as s:
            row = s.scalar(select(User).where(User.username_key == username.lower()))
            return (UserAccount(row.id, row.username, row.created_at), row.password_hash) if row else None

    def get_user(self, user_id: int) -> UserAccount | None:
        with self.session() as s:
            row = s.get(User, user_id)
            return UserAccount(row.id, row.username, row.created_at) if row else None

    def set_password(self, user_id: int, password_hash: str) -> None:
        with self.session() as s:
            s.execute(update(User).where(User.id == user_id).values(password_hash=password_hash))

    def create_session(self, user_id: int, token: str, lifetime: timedelta) -> None:
        now = datetime.now(timezone.utc)
        with self.session() as s:
            s.execute(delete(UserSession).where(UserSession.expires_at < now))
            s.add(UserSession(token_hash=token_hash(token), user_id=user_id, expires_at=now + lifetime))

    def session_user(self, token: str) -> UserAccount | None:
        now = datetime.now(timezone.utc)
        with self.session() as s:
            row = s.execute(
                select(User).join(UserSession, UserSession.user_id == User.id)
                .where(UserSession.token_hash == token_hash(token), UserSession.expires_at > now)
            ).scalar()
            return UserAccount(row.id, row.username, row.created_at) if row else None

    def delete_session(self, token: str) -> None:
        with self.session() as s:
            s.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))

    # ---------------------------------------------------- Riot-Verknüpfungen
    def create_link_code(self, user_id: int, code: str, lifetime: timedelta) -> datetime:
        expires = datetime.now(timezone.utc) + lifetime
        with self.session() as s:
            s.execute(delete(LinkCode).where(LinkCode.user_id == user_id))  # nur ein aktiver Code je Konto
            s.add(LinkCode(code_hash=token_hash(code), user_id=user_id, expires_at=expires))
        return expires

    def redeem_link_code(self, code: str) -> int | None:
        """Löst einen Code ein (einmalig); liefert die Konto-ID."""
        now = datetime.now(timezone.utc)
        with self.session() as s:
            row = s.execute(delete(LinkCode).where(LinkCode.code_hash == token_hash(code))
                            .returning(LinkCode.user_id, LinkCode.expires_at)).first()
            s.execute(delete(LinkCode).where(LinkCode.expires_at < now))
        if row is None or row.expires_at < now:
            return None
        return row.user_id

    def link_riot(self, user_id: int, puuid: str, game_name: str, tag_line: str, key: str) -> None:
        values = {"user_id": user_id, "game_name": game_name, "tag_line": tag_line, "key_hash": token_hash(key),
                  "linked_at": datetime.now(timezone.utc)}
        stmt = insert(RiotLink).values(puuid=puuid, **values).on_conflict_do_update(
            index_elements=[RiotLink.puuid], set_=values)
        with self.session() as s:
            s.execute(stmt)

    def unlink_riot(self, user_id: int, puuid: str) -> bool:
        with self.session() as s:
            result = s.execute(delete(RiotLink).where(RiotLink.user_id == user_id, RiotLink.puuid == puuid))
            return result.rowcount > 0

    def riot_link_owner(self, puuid: str, key: str | None = None) -> int | None:
        """Konto-ID zu einem verknüpften Riot-Account (optional mit Prüfung des Geräteschlüssels)."""
        with self.session() as s:
            row = s.get(RiotLink, puuid)
            if row is None:
                return None
            if key is not None and not secrets.compare_digest(row.key_hash, token_hash(key)):
                return None
            return row.user_id

    def touch_riot_link(self, puuid: str) -> None:
        with self.session() as s:
            s.execute(update(RiotLink).where(RiotLink.puuid == puuid)
                      .values(last_upload_at=datetime.now(timezone.utc)))

    def linked_riot_accounts(self, user_id: int) -> list[LinkedRiot]:
        with self.session() as s:
            rows = s.scalars(select(RiotLink).where(RiotLink.user_id == user_id).order_by(RiotLink.linked_at))
            return [LinkedRiot(r.puuid, r.game_name, r.tag_line, r.linked_at, r.last_upload_at) for r in rows]

    def owned_team_ids(self, user_id: int) -> set[int]:
        with self.session() as s:
            return set(s.scalars(select(TeamRow.id).where(TeamRow.owner_id == user_id)))

    def roster_team_ids(self, puuids: set[str]) -> set[int]:
        """Teams, in deren Kader einer der Riot-Accounts steht."""
        if not puuids:
            return set()
        with self.session() as s:
            return set(s.scalars(select(TeamMemberRow.team_id).where(TeamMemberRow.puuid.in_(puuids))))

    def teams_with_match(self, match_id: str) -> set[int]:
        with self.session() as s:
            return set(s.scalars(select(TeamGameRow.team_id).where(TeamGameRow.match_id == match_id)))

    # --------------------------------------------------------------- Scouting
    def put_scout(self, key: str, players: list[dict], roster: list[dict], games: list[tuple[str, int]]) -> None:
        values = {"players": players, "roster": roster, "games": [list(g) for g in games],
                  "updated_at": datetime.now(timezone.utc)}
        stmt = insert(Scout).values(key=key, **values).on_conflict_do_update(index_elements=[Scout.key], set_=values)
        with self.session() as s:
            s.execute(stmt)

    def get_scout(self, key: str) -> dict | None:
        with self.session() as s:
            row = s.get(Scout, key)
            if row is None:
                return None
            return {"key": row.key, "players": row.players, "roster": row.roster,
                    "games": [tuple(g) for g in row.games], "updated_at": row.updated_at}

    def recent_scouts(self, limit: int = 10) -> list[dict]:
        with self.session() as s:
            rows = s.scalars(select(Scout).order_by(Scout.updated_at.desc()).limit(limit))
            return [{"key": r.key, "players": r.players, "roster": r.roster, "games": len(r.games),
                     "updated_at": r.updated_at} for r in rows]
