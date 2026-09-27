"""SQLite-Persistenz: API-Cache (Accounts, Matches, Timelines) und Teams.

Matchdaten ändern sich nach Spielende nie mehr, deshalb wird alles, was einmal
von der Riot-API geladen wurde, dauerhaft (zlib-komprimiert) zwischengespeichert.
Das schont das Rate-Limit enorm.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    riot_id     TEXT PRIMARY KEY,          -- lower-case "name#tag"
    puuid       TEXT NOT NULL,
    game_name   TEXT NOT NULL,
    tag_line    TEXT NOT NULL,
    fetched_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
    match_id      TEXT PRIMARY KEY,
    game_creation INTEGER,
    data          BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS timelines (
    match_id TEXT PRIMARY KEY,
    data     BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS timeline_summaries (
    match_id TEXT PRIMARY KEY,
    version  INTEGER NOT NULL,
    data     BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    tag         TEXT NOT NULL DEFAULT '',
    min_members INTEGER NOT NULL DEFAULT 4,
    created_at  REAL NOT NULL,
    last_synced REAL
);
CREATE TABLE IF NOT EXISTS team_members (
    team_id   INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    puuid     TEXT NOT NULL,
    game_name TEXT NOT NULL,
    tag_line  TEXT NOT NULL,
    role      TEXT NOT NULL DEFAULT '',
    position  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (team_id, puuid)
);
CREATE TABLE IF NOT EXISTS team_games (
    team_id  INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    match_id TEXT NOT NULL,
    side     INTEGER NOT NULL,            -- teamId des Teams in diesem Match (100/200)
    label    TEXT NOT NULL DEFAULT '',    -- '', 'official', 'scrim'
    included INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (team_id, match_id)
);
"""


def _pack(obj: Any) -> bytes:
    return zlib.compress(json.dumps(obj, separators=(",", ":")).encode("utf-8"), 6)


def _unpack(blob: bytes) -> Any:
    return json.loads(zlib.decompress(blob).decode("utf-8"))


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
    created_at: float
    last_synced: float | None
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


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Für ":memory:" (Tests) wird eine einzelne geteilte Verbindung genutzt.
        self._shared: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        with self._connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self.path == ":memory:":
            with self._lock:
                if self._shared is None:
                    self._shared = sqlite3.connect(":memory:", check_same_thread=False)
                    self._shared.execute("PRAGMA foreign_keys = ON")
                with self._shared:
                    yield self._shared
            return
        con = sqlite3.connect(self.path, timeout=30)
        try:
            con.execute("PRAGMA foreign_keys = ON")
            con.execute("PRAGMA journal_mode = WAL")
            with con:
                yield con
        finally:
            con.close()

    # ------------------------------------------------------------------ cache
    def get_account(self, riot_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT puuid, game_name, tag_line FROM accounts WHERE riot_id = ?",
                (riot_id.lower(),),
            ).fetchone()
        if not row:
            return None
        return {"puuid": row[0], "gameName": row[1], "tagLine": row[2]}

    def put_account(self, riot_id: str, account: dict) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO accounts VALUES (?, ?, ?, ?, ?)",
                (riot_id.lower(), account["puuid"], account["gameName"], account["tagLine"], time.time()),
            )

    def get_match(self, match_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT data FROM matches WHERE match_id = ?", (match_id,)).fetchone()
        return _unpack(row[0]) if row else None

    def put_match(self, match_id: str, data: dict) -> None:
        created = data.get("info", {}).get("gameCreation")
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO matches VALUES (?, ?, ?)", (match_id, created, _pack(data))
            )

    def has_matches(self, match_ids: list[str]) -> set[str]:
        if not match_ids:
            return set()
        with self._connect() as con:
            marks = ",".join("?" * len(match_ids))
            rows = con.execute(f"SELECT match_id FROM matches WHERE match_id IN ({marks})", match_ids)
            return {r[0] for r in rows}

    def get_timeline(self, match_id: str) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT data FROM timelines WHERE match_id = ?", (match_id,)).fetchone()
        return _unpack(row[0]) if row else None

    def put_timeline(self, match_id: str, data: dict) -> None:
        with self._connect() as con:
            con.execute("INSERT OR REPLACE INTO timelines VALUES (?, ?)", (match_id, _pack(data)))

    def get_timeline_summary(self, match_id: str, version: int) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT data FROM timeline_summaries WHERE match_id = ? AND version = ?",
                (match_id, version),
            ).fetchone()
        return _unpack(row[0]) if row else None

    def put_timeline_summary(self, match_id: str, version: int, data: dict) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO timeline_summaries VALUES (?, ?, ?)",
                (match_id, version, _pack(data)),
            )

    # ------------------------------------------------------------------ teams
    def create_team(self, name: str, tag: str, min_members: int, members: list[Member]) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO teams (name, tag, min_members, created_at) VALUES (?, ?, ?, ?)",
                (name, tag, min_members, time.time()),
            )
            team_id = int(cur.lastrowid)
            self._write_members(con, team_id, members)
        return team_id

    def update_team(self, team_id: int, name: str, tag: str, min_members: int, members: list[Member]) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE teams SET name = ?, tag = ?, min_members = ? WHERE id = ?",
                (name, tag, min_members, team_id),
            )
            con.execute("DELETE FROM team_members WHERE team_id = ?", (team_id,))
            self._write_members(con, team_id, members)

    @staticmethod
    def _write_members(con: sqlite3.Connection, team_id: int, members: list[Member]) -> None:
        con.executemany(
            "INSERT OR REPLACE INTO team_members VALUES (?, ?, ?, ?, ?, ?)",
            [(team_id, m.puuid, m.game_name, m.tag_line, m.role, i) for i, m in enumerate(members)],
        )

    def delete_team(self, team_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM teams WHERE id = ?", (team_id,))

    def list_teams(self) -> list[Team]:
        with self._connect() as con:
            ids = [r[0] for r in con.execute("SELECT id FROM teams ORDER BY name COLLATE NOCASE")]
        return [t for t in (self.get_team(i) for i in ids) if t]

    def get_team(self, team_id: int) -> Team | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT id, name, tag, min_members, created_at, last_synced FROM teams WHERE id = ?",
                (team_id,),
            ).fetchone()
            if not row:
                return None
            members = [
                Member(puuid=r[0], game_name=r[1], tag_line=r[2], role=r[3])
                for r in con.execute(
                    "SELECT puuid, game_name, tag_line, role FROM team_members "
                    "WHERE team_id = ? ORDER BY position",
                    (team_id,),
                )
            ]
        return Team(*row, members=members)

    def mark_synced(self, team_id: int) -> None:
        with self._connect() as con:
            con.execute("UPDATE teams SET last_synced = ? WHERE id = ?", (time.time(), team_id))

    def add_team_games(self, team_id: int, games: list[tuple[str, int, str]]) -> int:
        """Fügt (match_id, side, label) hinzu; bestehende Einträge bleiben unverändert."""
        with self._connect() as con:
            before = con.total_changes
            con.executemany(
                "INSERT OR IGNORE INTO team_games (team_id, match_id, side, label) VALUES (?, ?, ?, ?)",
                [(team_id, mid, side, label) for mid, side, label in games],
            )
            return con.total_changes - before

    def team_games(self, team_id: int) -> list[TeamGame]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT tg.match_id, tg.side, tg.label, tg.included FROM team_games tg "
                "LEFT JOIN matches m ON m.match_id = tg.match_id "
                "WHERE tg.team_id = ? ORDER BY m.game_creation DESC",
                (team_id,),
            ).fetchall()
        return [TeamGame(r[0], r[1], r[2], bool(r[3])) for r in rows]

    def update_team_game(self, team_id: int, match_id: str, *, label: str | None = None,
                         included: bool | None = None) -> None:
        with self._connect() as con:
            if label is not None:
                con.execute(
                    "UPDATE team_games SET label = ? WHERE team_id = ? AND match_id = ?",
                    (label, team_id, match_id),
                )
            if included is not None:
                con.execute(
                    "UPDATE team_games SET included = ? WHERE team_id = ? AND match_id = ?",
                    (int(included), team_id, match_id),
                )
