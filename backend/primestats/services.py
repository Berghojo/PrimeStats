"""Geschäftslogik: Spielersuche, Team-Synchronisation und Laden von Spielen."""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from dataclasses import dataclass, field

from .matches import MatchSummary, parse_match
from .riot import MatchSource, RiotAPIError, split_riot_id
from .store import Member, Store, Team
from .team_stats import GameRecord, default_label, match_side_for_team
from .timeline import SUMMARY_VERSION, summarize_timeline

log = logging.getLogger(__name__)

#: Abfragen für Custom Games: queue=0 (Custom-Lobbys inkl. Turniercode-Spiele) und type=tourney
CUSTOM_QUERIES = ({"queue": 0}, {"type": "tourney"})
PARSE_CACHE_SIZE = 4096


class PrimeStats:
    def __init__(self, store: Store, source: MatchSource, sync_match_count: int = 100):
        self.store = store
        self.source = source
        self.sync_match_count = sync_match_count
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
        ids: list[str] = []
        for query in CUSTOM_QUERIES:
            for mid in self.source.match_ids(puuid, count, **query):
                if mid not in ids:
                    ids.append(mid)
        # Match-IDs sind pro Plattform aufsteigend -> neueste zuerst
        return sorted(ids, key=_match_sort_key, reverse=True)

    # -------------------------------------------------------------- player
    def player_games(self, riot_id: str, count: int = 20) -> tuple[dict, list[MatchSummary]]:
        account = self.account(riot_id)
        ids = self.custom_match_ids(account["puuid"], count)[:count]
        games = []
        for mid in ids:
            match = self.match(mid)
            if match.is_custom:
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
        ids = [tg.match_id for tg in games]
        raw = self.store.get_matches([mid for mid in ids if not self._is_parsed(mid)])
        summaries = self.store.get_timeline_summaries(ids, SUMMARY_VERSION) if with_timeline else {}
        records = []
        for tg in games:
            try:
                match = self._parse_from(tg.match_id, raw.get(tg.match_id))
            except RiotAPIError as exc:
                log.warning("Spiel %s nicht ladbar: %s", tg.match_id, exc)
                continue
            records.append(GameRecord(match, tg.side, tg.label, tg.included, summaries.get(tg.match_id)))
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

        # 1) Match-IDs aller Mitglieder sammeln; Kandidaten = IDs, die bei genug Mitgliedern auftauchen
        progress.update("Lade Spiellisten der Mitglieder …", 0, len(team.members))
        occurrences: Counter = Counter()
        for i, member in enumerate(team.members, 1):
            occurrences.update(set(self.custom_match_ids(member.puuid, self.sync_match_count)))
            progress.update(f"Spielliste von {member.game_name} geladen", i, len(team.members))
        known = {tg.match_id for tg in self.store.team_games(team.id)}
        candidates = [mid for mid, c in occurrences.items() if c >= min_members and mid not in known]
        candidates.sort(key=_match_sort_key, reverse=True)

        # 2) Matchdetails laden und prüfen, ob die Spieler im selben Team waren
        found: list[tuple[str, int, str]] = []
        for i, mid in enumerate(candidates, 1):
            progress.update(f"Prüfe Spiel {i}/{len(candidates)}", i, len(candidates))
            match = self.match(mid)
            if not match.is_custom:
                continue
            side = match_side_for_team(match, puuids, min_members)
            if side is not None:
                found.append((mid, side, default_label(match)))
        progress.new_games = self.store.add_team_games(team.id, found)

        # 3) Timelines für alle Teamspiele (fehlende nachladen)
        games = self.store.team_games(team.id)
        done = self.store.summarized_matches([tg.match_id for tg in games], SUMMARY_VERSION)
        missing = [tg for tg in games if tg.match_id not in done]
        for i, tg in enumerate(missing, 1):
            progress.update(f"Lade Timeline {i}/{len(missing)}", i, len(missing))
            try:
                self.timeline_summary(self.match(tg.match_id))
            except RiotAPIError as exc:  # Timeline optional – Spiel bleibt trotzdem erhalten
                log.warning("Timeline für %s nicht verfügbar: %s", tg.match_id, exc)
        self.store.mark_synced(team.id)


def _match_sort_key(match_id: str) -> int:
    try:
        return int(match_id.rsplit("_", 1)[-1])
    except ValueError:
        return 0


@dataclass
class SyncJob:
    team_id: int
    status: str = "running"         # running | done | error
    message: str = "Starte …"
    done: int = 0
    total: int = 0
    new_games: int = 0
    error: str = ""
    started: float = field(default_factory=time.time)
    finished: float | None = None

    def update(self, message: str, done: int, total: int) -> None:
        self.message, self.done, self.total = message, done, total

    @property
    def percent(self) -> int:
        return int(100 * self.done / self.total) if self.total else 0


class SyncJobs:
    """Führt Team-Syncs im Hintergrund aus (ein Job pro Team gleichzeitig)."""

    def __init__(self, app: PrimeStats):
        self.app = app
        self._jobs: dict[int, SyncJob] = {}
        self._lock = threading.Lock()

    def get(self, team_id: int) -> SyncJob | None:
        return self._jobs.get(team_id)

    def start(self, team: Team, background: bool = True) -> SyncJob:
        with self._lock:
            job = self._jobs.get(team.id)
            if job and job.status == "running":
                return job
            job = self._jobs[team.id] = SyncJob(team.id)
        if background:
            threading.Thread(target=self._run, args=(team, job), daemon=True).start()
        else:
            self._run(team, job)
        return job

    def _run(self, team: Team, job: SyncJob) -> None:
        try:
            self.app.sync_team(team, job)
            job.status = "done"
            job.message = f"Fertig – {job.new_games} neue Spiele gefunden."
        except Exception as exc:  # noqa: BLE001 - Fehler dem Nutzer anzeigen
            log.exception("Sync für Team %s fehlgeschlagen", team.id)
            job.status = "error"
            job.error = getattr(exc, "message", None) or str(exc)
            job.message = "Synchronisation fehlgeschlagen."
        finally:
            job.finished = time.time()
