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
from .team_stats import GameRecord, default_label, infer_roster, match_side_for_team
from .timeline import SUMMARY_VERSION, summarize_timeline

log = logging.getLogger(__name__)

#: Die Riot-API liefert Custom Games nur, wenn sie per Turniercode erstellt wurden (type=tourney).
#: Normale Custom-Lobbys (Scrims) kommen ausschließlich über den LCU-Uploader herein.
CUSTOM_QUERIES = ({"type": "tourney"},)
PARSE_CACHE_SIZE = 4096
#: Wie viele Turnierspiele je Spieler beim Scouting durchsucht werden
SCOUT_MATCH_COUNT = 50
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
        return self._records([(tg.match_id, tg.side, tg.label, tg.included) for tg in games], with_timeline)

    def _records(self, games: list[tuple[str, int, str, bool]], with_timeline: bool = True) -> list[GameRecord]:
        ids = [g[0] for g in games]
        raw = self.store.get_matches([mid for mid in ids if not self._is_parsed(mid)])
        summaries = self.store.get_timeline_summaries(ids, SUMMARY_VERSION) if with_timeline else {}
        records = []
        for mid, side, label, included in games:
            try:
                match = self._parse_from(mid, raw.get(mid))
            except RiotAPIError as exc:
                log.warning("Spiel %s nicht ladbar: %s", mid, exc)
                continue
            records.append(GameRecord(match, side, label, included, summaries.get(mid)))
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
    def scout(self, account: dict, progress: "SyncJob", min_members: int = 4,
              depth: int = SCOUT_MATCH_COUNT, timelines: int = SCOUT_TIMELINES) -> None:
        """Turnier-Scouting ab einem einzelnen Spieler.

        1. Turniercode-Spiele des Spielers laden und daraus den Kader ableiten (häufige Mitspieler).
        2. Turniercode-Spiele aller Kader-Spieler durchsuchen – so werden auch Spiele gefunden, in denen der
           gesuchte Spieler selbst fehlte.
        3. Alle Spiele behalten, in denen mindestens ``min_members`` Kader-Spieler zusammen spielten.
        Nutzt ausschließlich öffentliche Riot-API-Daten (keine hochgeladenen Scrims).
        """
        if not self.online:
            raise RiotAPIError(503, "Scouting braucht einen Riot-API-Key (LOL_API_KEY).")
        puuid = account["puuid"]
        progress.update(f"Lade Turnierspiele von {account['gameName']} …", 0, 1)
        own_ids = self.custom_match_ids(puuid, depth)
        own = []
        for i, mid in enumerate(own_ids, 1):
            progress.update(f"Lade Spiel {i}/{len(own_ids)}", i, len(own_ids))
            own.append(self.match(mid))
        own = [m for m in own if not m.private]
        roster = infer_roster(own, puuid)
        if not roster:
            raise RiotAPIError(404, f"{account['gameName']}#{account['tagLine']} hat keine Turnierspiele.")
        roster_puuids = {r["puuid"] for r in roster}
        needed = min(min_members, len(roster))

        # Eigene Spiele sind schon geladen; fremde nur abrufen, wenn sie in mehreren Kader-Listen
        # auftauchen (Toleranz 1, weil ältere Spiele aus einzelnen Listen herausfallen können).
        occurrences: Counter = Counter()
        for i, member in enumerate(roster[1:], 1):
            progress.update(f"Durchsuche Spiele von {member['game_name']} …", i, len(roster) - 1)
            occurrences.update(set(self.custom_match_ids(member["puuid"], depth)) - set(own_ids))
        others = {mid for mid, c in occurrences.items() if c >= max(1, needed - 1)}
        candidates = sorted({m.match_id for m in own} | others, key=_match_sort_key, reverse=True)
        games: list[tuple[str, int]] = []
        for i, mid in enumerate(candidates, 1):
            progress.update(f"Prüfe Spiel {i}/{len(candidates)}", i, len(candidates))
            match = self.match(mid)
            if match.private or not match.is_custom:
                continue
            side = match_side_for_team(match, roster_puuids, needed)
            if side is not None:
                games.append((mid, side))

        # Timelines (Goldkurven, Lane-Differenzen) für die neuesten Spiele
        recent = [mid for mid, _ in games][:timelines]
        missing = [mid for mid in recent if mid not in self.store.summarized_matches(recent, SUMMARY_VERSION)]
        for i, mid in enumerate(missing, 1):
            progress.update(f"Lade Timeline {i}/{len(missing)}", i, len(missing))
            try:
                self.timeline_summary(self.match(mid))
            except RiotAPIError as exc:
                log.warning("Timeline für %s nicht verfügbar: %s", mid, exc)

        # Kader-Statistik (Spiele je Spieler) auf Basis aller gefundenen Teamspiele aktualisieren
        counts: Counter = Counter()
        for mid, side in games:
            counts.update(p.puuid for p in self.match(mid).teams[side].players if p.puuid in roster_puuids)
        for r in roster:
            r["games"] = counts.get(r["puuid"], r["games"])
        self.store.put_scout(puuid, account["gameName"], account["tagLine"], roster, games, needed)
        progress.new_games = len(games)
        progress.done_message = f"Fertig – {len(games)} Turnierspiele von {len(roster)} Spielern gefunden."

    def scout_records(self, scout: dict) -> list[GameRecord]:
        return [r for r in self._records([(mid, side, "official", True) for mid, side in scout["games"]])
                if not r.match.private]


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
