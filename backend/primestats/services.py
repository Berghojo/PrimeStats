"""Geschäftslogik: Spielersuche, Team-Synchronisation und Laden von Spielen."""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from dataclasses import dataclass, field

from . import lcu
from .matches import MatchSummary, parse_match
from .riot import MatchSource, NotFound, RiotAPIError, split_riot_id
from .store import Member, Store, Team
from .team_stats import GameRecord, default_label, match_side_for_team
from .timeline import SUMMARY_VERSION, summarize_timeline

log = logging.getLogger(__name__)

#: Die Riot-API liefert Custom Games nur, wenn sie per Turniercode erstellt wurden (type=tourney).
#: Normale Custom-Lobbys (Scrims) kommen ausschließlich über den LCU-Uploader herein.
CUSTOM_QUERIES = ({"type": "tourney"},)
PARSE_CACHE_SIZE = 4096


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
