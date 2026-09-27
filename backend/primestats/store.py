"""Persistenz in PostgreSQL: API-Cache (Accounts, Matches, Timelines) und Teams.

Matchdaten ändern sich nach Spielende nie mehr, deshalb wird alles, was einmal
von der Riot-API geladen wurde, dauerhaft als JSONB gespeichert. Das schont das
Rate-Limit enorm.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .db import Account, Match, TeamGameRow, TeamMemberRow, TeamRow, Timeline, TimelineSummary


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

    @property
    def puuids(self) -> set[str]:
        return {m.puuid for m in self.members}


@dataclass
class TeamGame:
    match_id: str
    side: int
    label: str
    included: bool


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

    def create_team(self, name: str, tag: str, min_members: int, members: list[Member]) -> int:
        with self.session() as s:
            row = TeamRow(name=name, tag=tag, min_members=min_members, members=self._member_rows(members))
            s.add(row)
            s.flush()
            return row.id

    def update_team(self, team_id: int, name: str, tag: str, min_members: int, members: list[Member]) -> None:
        with self.session() as s:
            row = s.get(TeamRow, team_id)
            if row is None:
                return
            row.name, row.tag, row.min_members = name, tag, min_members
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
            [{"team_id": team_id, "match_id": mid, "side": side, "label": label, "included": True}
             for mid, side, label in games]
        ).on_conflict_do_nothing().returning(TeamGameRow.match_id)
        with self.session() as s:
            return len(s.execute(stmt).all())

    def team_games(self, team_id: int) -> list[TeamGame]:
        with self.session() as s:
            rows = s.execute(
                select(TeamGameRow.match_id, TeamGameRow.side, TeamGameRow.label, TeamGameRow.included)
                .outerjoin(Match, Match.match_id == TeamGameRow.match_id)
                .where(TeamGameRow.team_id == team_id)
                .order_by(Match.game_creation.desc().nulls_last(), TeamGameRow.match_id.desc())
            )
            return [TeamGame(*r) for r in rows]

    def update_team_game(self, team_id: int, match_id: str, *, label: str | None = None,
                         included: bool | None = None) -> bool:
        values: dict = {}
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
