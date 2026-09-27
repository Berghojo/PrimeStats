"""Geschäftslogik: Spielersuche, Team-Synchronisation und Laden von Spielen."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import Counter
from dataclasses import dataclass, field

from . import lcu
from .matches import MatchSummary, parse_match
from .riot import MatchSource, NotFound, RiotAPIError, split_riot_id
from .store import Member, Store, Team
from .team_stats import (GameRecord, any_side, default_label, match_side_for_team, roster_from_games,
                         together_side)
from .timeline import SUMMARY_VERSION, summarize_timeline

log = logging.getLogger(__name__)

#: Die Riot-API liefert Custom Games nur, wenn sie per Turniercode erstellt wurden (type=tourney).
#: Normale Custom-Lobbys (Scrims) kommen ausschließlich über den LCU-Uploader herein.
CUSTOM_QUERIES = ({"type": "tourney"},)
PARSE_CACHE_SIZE = 4096
#: Wie viele Einträge der Turnier-Liste je Spieler beim Scouting durchsucht werden
#: (die Liste type=tourney enthält auch Nicht-Custom-Spiele wie Clash, daher großzügig)
SCOUT_MATCH_COUNT = 100
#: Wie viele der häufigsten Mitspieler beim Scouting zusätzlich durchsucht werden
SCOUT_MATES = 6
#: Für wie viele der neuesten Scouting-Spiele Timelines geladen werden
SCOUT_TIMELINES = 30


class OfflineSource:
    """Platzhalter ohne Riot-API-Key: nur importierte Spiele sind verfügbar."""

    online = False

    def _fail(self, *_args, **_kwargs):
        raise RiotAPIError(503, "Kein Riot-API-Key konfiguriert – nur hochgeladene Spiele sind verfügbar.")

    def account(self, riot_id: str) -> dict:
        name, tag = split_riot_id(riot_id)
        raise NotFound(404, f"Spieler {name}#{tag} ist in keinem hochgeladenen Spiel enthalten "
                            "(ohne Riot-API-Key sind nur hochgeladene Spieler bekannt).")

    match_ids = _fail
    match = _fail
    timeline = _fail


@dataclass
class ImportResult:
    imported: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    assigned: dict[str, int] = field(default_factory=dict)


class PrimeStats:
    def __init__(self, store: Store, source: MatchSource, sync_match_count: int = 100):
        self.store = store
        self.source = source
        self.sync_match_count = sync_match_count
        self.online = getattr(source, "online", True)
        self.jobs = SyncJobs(self)
        self._parsed: dict[str, MatchSummary] = {}
        self._parsed_lock = threading.Lock()

    # ------------------------------------------------------------- matches
    def account(self, riot_id: str) -> dict:
        name, tag = split_riot_id(riot_id)
        key = f"{name}#{tag}"
        cached = self.store.get_account(key)
        if cached:
            return cached
        data = self.source.account(key)
        self.store.put_account(key, data)
        return data

    def raw_match(self, match_id: str) -> dict:
        data = self.store.get_match(match_id)
        if data is None:
            data = self.source.match(match_id)
            self.store.put_match(match_id, data)
        return data

    def _remember(self, match_id: str, match: MatchSummary) -> None:
        with self._parsed_lock:
            if len(self._parsed) >= PARSE_CACHE_SIZE:
                self._parsed.pop(next(iter(self._parsed)))
            self._parsed[match_id] = match

    def match(self, match_id: str) -> MatchSummary:
        """Geparstes Match (Speicher-Cache → Datenbank → Riot-API)."""
        match = self._parsed.get(match_id)
        if match is None:
            match = parse_match(self.raw_match(match_id))
            self._remember(match_id, match)
        return match

    def timeline_summary(self, match: MatchSummary, fetch: bool = True) -> dict | None:
        summary = self.store.get_timeline_summary(match.match_id, SUMMARY_VERSION)
        if summary is not None:
            return summary
        raw = self.store.get_timeline(match.match_id)
        if raw is None:
            if not fetch:
                return None
            raw = self.source.timeline(match.match_id)
            self.store.put_timeline(match.match_id, raw)
        summary = summarize_timeline(raw, match)
        self.store.put_timeline_summary(match.match_id, SUMMARY_VERSION, summary)
        return summary

    def custom_match_ids(self, puuid: str, count: int) -> list[str]:
        """Turniercode-Spiele laut Riot-API (leer ohne API-Key)."""
        ids: list[str] = []
        if not self.online:
            return ids
        for query in CUSTOM_QUERIES:
            for mid in self.source.match_ids(puuid, count, **query):
                if mid not in ids:
                    ids.append(mid)
        # Match-IDs sind pro Plattform aufsteigend -> neueste zuerst
        return sorted(ids, key=_match_sort_key, reverse=True)

    # -------------------------------------------------------------- player
    def player_games(self, riot_id: str, count: int = 20,
                     visible=lambda match: True) -> tuple[dict, list[MatchSummary]]:
        account = self.account(riot_id)
        ids = set(self.custom_match_ids(account["puuid"], count))
        ids |= set(self.store.matches_with_players({account["puuid"]}))  # hochgeladene Scrims
        ids = sorted(ids, key=_match_sort_key, reverse=True)[:count]
        games = []
        for mid in ids:
            match = self.match(mid)
            if match.is_custom and visible(match):
                games.append(match)
        games.sort(key=lambda m: m.created, reverse=True)
        return account, games

    # --------------------------------------------------------------- teams
    def resolve_members(self, entries: list[tuple[str, str]]) -> tuple[list[Member], list[str]]:
        """Löst (riot_id, rolle)-Paare zu Mitgliedern auf; liefert auch Fehlermeldungen."""
        members, errors, seen = [], [], set()
        for riot_id, role in entries:
            riot_id = riot_id.strip()
            if not riot_id:
                continue
            try:
                acc = self.account(riot_id)
            except (ValueError, RiotAPIError) as exc:
                errors.append(f"{riot_id}: {exc}")
                continue
            if acc["puuid"] in seen:
                continue
            seen.add(acc["puuid"])
            members.append(Member(acc["puuid"], acc["gameName"], acc["tagLine"], role))
        return members, errors

    def team_records(self, team: Team, with_timeline: bool = True) -> list[GameRecord]:
        """Alle gespeicherten Spiele eines Teams (ohne API-Aufrufe)."""
        games = self.store.team_games(team.id)
        return self._records([(tg.match_id, tg.side, tg.label, tg.included, tg.opponent) for tg in games],
                             with_timeline)

    def _records(self, games: list[tuple[str, int, str, bool, str]], with_timeline: bool = True) -> list[GameRecord]:
        ids = [g[0] for g in games]
        raw = self.store.get_matches([mid for mid in ids if not self._is_parsed(mid)])
        summaries = self.store.get_timeline_summaries(ids, SUMMARY_VERSION) if with_timeline else {}
        records = []
        for mid, side, label, included, opponent in games:
            try:
                match = self._parse_from(mid, raw.get(mid))
            except RiotAPIError as exc:
                log.warning("Spiel %s nicht ladbar: %s", mid, exc)
                continue
            records.append(GameRecord(match, side, label, included, summaries.get(mid), opponent))
        return records

    def _is_parsed(self, match_id: str) -> bool:
        return match_id in self._parsed

    def _parse_from(self, match_id: str, data: dict | None) -> MatchSummary:
        if match_id not in self._parsed and data is not None:
            self._remember(match_id, parse_match(data))
        return self.match(match_id)

    def sync_team(self, team: Team, progress: "SyncJob") -> None:
        puuids = team.puuids
        min_members = min(team.min_members, max(len(puuids), 1))

        known = {tg.match_id for tg in self.store.team_games(team.id)}

        # 0) Bereits gespeicherte Spiele (z.B. per Uploader hochgeladene Scrims) zuordnen
        progress.update("Prüfe gespeicherte Spiele …", 0, 1)
        stored = [mid for mid in self.store.matches_with_players(puuids) if mid not in known]
        found = self._team_matches(stored, puuids, min_members)

        # 1) Turniercode-Spiele aller Mitglieder über die Riot-API; Kandidaten = IDs, die bei genug
        #    Mitgliedern auftauchen
        tourney: set[str] = set()
        if self.online:
            occurrences: Counter = Counter()
            for i, member in enumerate(team.members, 1):
                progress.update(f"Lade Spielliste von {member.game_name} …", i - 1, len(team.members))
                occurrences.update(set(self.custom_match_ids(member.puuid, self.sync_match_count)))
            tourney = {mid for mid, c in occurrences.items() if c >= min_members}
            candidates = sorted(tourney - known - set(stored), key=_match_sort_key, reverse=True)

            # 2) Matchdetails laden und prüfen, ob die Spieler im selben Team waren
            for i, mid in enumerate(candidates, 1):
                progress.update(f"Prüfe Spiel {i}/{len(candidates)}", i, len(candidates))
                found += self._team_matches([mid], puuids, min_members, official=True)
        progress.new_games = self.store.add_team_games(team.id, found)

        # 3) Timelines für alle Teamspiele (fehlende nachladen)
        games = self.store.team_games(team.id)
        done = self.store.summarized_matches([tg.match_id for tg in games], SUMMARY_VERSION)
        missing = [tg for tg in games if tg.match_id not in done]
        for i, tg in enumerate(missing, 1):
            progress.update(f"Lade Timeline {i}/{len(missing)}", i, len(missing))
            try:
                self.timeline_summary(self.match(tg.match_id), fetch=self.online)
            except RiotAPIError as exc:  # Timeline optional – Spiel bleibt trotzdem erhalten
                log.warning("Timeline für %s nicht verfügbar: %s", tg.match_id, exc)
        self.store.mark_synced(team.id)


    def _team_matches(self, match_ids: list[str], puuids: set[str], min_members: int,
                      official: bool = False) -> list[tuple[str, int, str]]:
        found = []
        for mid in match_ids:
            match = self.match(mid)
            if not match.is_custom:
                continue
            side = match_side_for_team(match, puuids, min_members)
            if side is not None:
                found.append((mid, side, "official" if official else default_label(match)))
        return found

    # ------------------------------------------------------------- imports
    def known_matches(self, match_ids: list[str]) -> set[str]:
        return self.store.existing_matches(match_ids)

    def import_lcu(self, items: list[dict], uploader: str = "",
                   allowed_puuids: set[str] | None = None) -> ImportResult:
        """Importiert Spiele aus dem League Client (Format der LCU-API).

        Bereits vorhandene Matches (z.B. über die Riot-API geladene Turnierspiele) werden nicht
        überschrieben; fehlende Timelines werden aber ergänzt. Mit ``allowed_puuids`` werden nur
        Spiele angenommen, in denen einer dieser Riot-Accounts mitgespielt hat.
        """
        result = ImportResult()
        existing = self.store.existing_matches([lcu.match_id(i["game"]) for i in items if "gameId" in i.get("game", {})])
        new_ids: list[str] = []
        for item in items:
            game, raw_timeline = item.get("game") or {}, item.get("timeline")
            try:
                converted = lcu.convert_game(game)
                mid = converted["metadata"]["matchId"]
                timeline = lcu.convert_timeline(raw_timeline, converted) if raw_timeline else None
            except (lcu.LcuFormatError, KeyError, TypeError) as exc:
                result.errors.append(f"{game.get('gameId', '?')}: {exc}")
                continue
            if converted["info"]["gameType"] != "CUSTOM_GAME" and converted["info"]["queueId"] != 0:
                result.skipped.append(mid)
                continue
            if allowed_puuids is not None and not allowed_puuids & set(converted["metadata"]["participants"]):
                result.errors.append(f"{mid}: Keiner deiner verknüpften Riot-Accounts hat mitgespielt.")
                continue
            self.store.put_raw_import(mid, "lcu", game, raw_timeline, uploader)
            if mid in existing:
                if timeline and self.store.get_timeline(mid) is None:
                    self.store.put_timeline(mid, timeline)
                    result.updated.append(mid)
                else:
                    result.skipped.append(mid)
                continue
            self.store.put_match(mid, converted)
            if timeline:
                self.store.put_timeline(mid, timeline)
            for acc in lcu.accounts(converted):
                self.store.put_account(f"{acc['gameName']}#{acc['tagLine']}", acc)
            result.imported.append(mid)
            new_ids.append(mid)
        result.assigned = self.assign_to_teams(new_ids + result.updated)
        return result

    def assign_to_teams(self, match_ids: list[str]) -> dict[str, int]:
        """Ordnet (neu importierte) Spiele allen passenden Teams zu und berechnet Timelines."""
        assigned: dict[str, int] = {}
        if not match_ids:
            return assigned
        for team in self.store.list_teams():
            min_members = min(team.min_members, max(len(team.puuids), 1))
            found = self._team_matches(match_ids, team.puuids, min_members)
            added = self.store.add_team_games(team.id, found)
            if added:
                assigned[team.name] = added
        for mid in match_ids:
            if self.store.get_timeline(mid) is not None:
                self.timeline_summary(self.match(mid), fetch=False)
        return assigned


    # ------------------------------------------------------------ Scouting
    def scout(self, accounts: list[dict], progress: "SyncJob", mode: str = "all", depth: int = SCOUT_MATCH_COUNT,
              timelines: int = SCOUT_TIMELINES) -> str:
        """Turnier-Scouting für einen oder mehrere Spieler.

        ``mode="all"``: Ein Spiel zählt nur, wenn **alle** gesuchten Spieler darin im selben Team standen.
        ``mode="any"``: Jedes Spiel, in dem **mindestens einer** der gesuchten Spieler mitspielte; gewertet
        wird dessen Team (bei Spielern auf beiden Seiten das mit den meisten gesuchten Spielern).
        Bei einem einzelnen Spieler sind beide Modi gleich. Die übrigen Spieler des Teams werden als
        Mitspieler ausgewiesen. Nutzt ausschließlich öffentliche Riot-API-Daten (keine Scrims).
        Liefert den Schlüssel des gespeicherten Ergebnisses.
        """
        if not self.online:
            raise RiotAPIError(503, "Scouting braucht einen Riot-API-Key (LOL_API_KEY).")
        puuids = [a["puuid"] for a in accounts]
        names = ", ".join(f"{a['gameName']}#{a['tagLine']}" for a in accounts)

        pick_side = together_side if mode == "all" else any_side
        games: list[tuple[str, int]] = []
        checked: set[str] = set()

        def check(ids: set[str], label: str) -> None:
            todo = sorted(ids - checked, key=_match_sort_key, reverse=True)
            for i, mid in enumerate(todo, 1):
                progress.update(f"{label}: prüfe Spiel {i}/{len(todo)}", i, len(todo))
                checked.add(mid)
                match = self.match(mid)
                if match.private or not match.is_custom:
                    continue
                side = pick_side(match, puuids)
                if side is not None:
                    games.append((mid, side))

        # 1) Turnierlisten der gesuchten Spieler
        own: set[str] = set()
        for i, acc in enumerate(accounts, 1):
            progress.update(f"Lade Turnierspiele von {acc['gameName']} …", i - 1, len(accounts))
            own |= set(self.custom_match_ids(acc["puuid"], depth))
        check(own, "Eigene Spiele")

        # 2) Die Riot-Liste eines Spielers ist nicht vollständig (live beobachtet: Spiele fehlen in der
        #    eigenen Liste, stehen aber in denen der Mitspieler). Deshalb auch die Listen der häufigsten
        #    Mitspieler durchsuchen – gezählt werden weiterhin nur Spiele mit den gesuchten Spielern.
        if games:
            roster = roster_from_games([(self.match(mid), side) for mid, side in games], puuids)
            mates = [r for r in roster if not r["searched"] and r["games"] >= 2][:SCOUT_MATES]
            for i, mate in enumerate(mates, 1):
                progress.update(f"Lade Turnierspiele von {mate['game_name']} …", i, len(mates))
                check(set(self.custom_match_ids(mate["puuid"], depth)), mate["game_name"])
        games.sort(key=lambda g: _match_sort_key(g[0]), reverse=True)
        if not games:
            if len(accounts) == 1 or mode == "any":
                raise RiotAPIError(404, f"{names}: keine Turnierspiele gefunden.")
            raise RiotAPIError(404, f"Keine Turnierspiele, in denen {names} im selben Team standen.")

        recent = [mid for mid, _ in games][:timelines]
        done = self.store.summarized_matches(recent, SUMMARY_VERSION)
        missing = [mid for mid in recent if mid not in done]
        for i, mid in enumerate(missing, 1):
            progress.update(f"Lade Timeline {i}/{len(missing)}", i, len(missing))
            try:
                self.timeline_summary(self.match(mid))
            except RiotAPIError as exc:
                log.warning("Timeline für %s nicht verfügbar: %s", mid, exc)

        roster = roster_from_games([(self.match(mid), side) for mid, side in games], puuids)
        players = [{"puuid": a["puuid"], "game_name": a["gameName"], "tag_line": a["tagLine"]} for a in accounts]
        key = scout_key(puuids, mode)
        self.store.put_scout(key, players, roster, games, mode)
        progress.new_games = len(games)
        progress.done_message = f"Fertig – {len(games)} Turnierspiele gefunden."
        return key

    def scout_records(self, scout: dict) -> list[GameRecord]:
        return [r for r in self._records([(mid, side, "official", True, "") for mid, side in scout["games"]])
                if not r.match.private]


def scout_key(puuids: list[str], mode: str = "all") -> str:
    """Stabiler Schlüssel für Spielerkombination + Modus (Reihenfolge egal; bei einem Spieler ist der
    Modus bedeutungslos)."""
    unique = sorted(set(puuids))
    mode = "all" if len(unique) == 1 else mode
    return hashlib.sha1(("|".join(unique) + ("" if mode == "all" else "|any")).encode()).hexdigest()


def _match_sort_key(match_id: str) -> int:
    try:
        return int(match_id.rsplit("_", 1)[-1])
    except ValueError:
        return 0


@dataclass
class SyncJob:
    key: object
    status: str = "running"         # running | done | error
    message: str = "Starte …"
    done: int = 0
    total: int = 0
    new_games: int = 0
    error: str = ""
    done_message: str = ""
    started: float = field(default_factory=time.time)
    finished: float | None = None

    def update(self, message: str, done: int, total: int) -> None:
        self.message, self.done, self.total = message, done, total

    @property
    def percent(self) -> int:
        return int(100 * self.done / self.total) if self.total else 0


class SyncJobs:
    """Führt Team-Syncs und Scoutings im Hintergrund aus (ein Job je Schlüssel gleichzeitig)."""

    def __init__(self, app: PrimeStats):
        self.app = app
        self._jobs: dict[object, SyncJob] = {}
        self._lock = threading.Lock()

    def get(self, key) -> SyncJob | None:
        return self._jobs.get(key)

    def start(self, team: Team, background: bool = True) -> SyncJob:
        return self.run(team.id, lambda job: self.app.sync_team(team, job), background)

    def run(self, key, fn, background: bool = True) -> SyncJob:
        with self._lock:
            job = self._jobs.get(key)
            if job and job.status == "running":
                return job
            job = self._jobs[key] = SyncJob(key)
        if background:
            threading.Thread(target=self._run, args=(fn, job), daemon=True).start()
        else:
            self._run(fn, job)
        return job

    def _run(self, fn, job: SyncJob) -> None:
        try:
            fn(job)
            job.status = "done"
            job.message = job.done_message or f"Fertig – {job.new_games} neue Spiele gefunden."
        except Exception as exc:  # noqa: BLE001 - Fehler dem Nutzer anzeigen
            log.exception("Job %s fehlgeschlagen", job.key)
            job.status = "error"
            job.error = getattr(exc, "message", None) or str(exc)
            job.message = "Fehlgeschlagen."
        finally:
            job.finished = time.time()
