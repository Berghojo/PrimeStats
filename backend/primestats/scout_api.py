"""Suche/Turnier-Scouting nach einem oder mehreren Spielern (öffentlich).

Die Suche sammelt die Turnierspiele der gesuchten Spieler (alle zusammen oder mindestens einer). Im Report
lassen sich danach bis zu fünf Spieler auswählen, um die Statistik auf deren Spiele einzugrenzen.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from .deps import RateLimit, Service, client_ip
from .riot import NotFound
from .schemas import (Filters, HistoryRow, ScoutFilters, RosterPlayer, ScoutIn, ScoutPlayer, ScoutReportOut, ScoutStartOut,
                      ScoutSummary, SyncJobOut)
from .services import scout_key
from .store import Member, Team
from .team_stats import LABELS, GameRecord, build_report, filter_records, history_rows, patches

def with_players(records: list[GameRecord], puuids: list[str], match: str) -> list[GameRecord]:
    """Spiele, in denen alle (``match="all"``) bzw. mindestens einer (``"any"``) der Spieler im Team stand."""
    if not puuids:
        return records
    wanted = set(puuids)
    out = []
    for r in records:
        on_team = {p.puuid for p in r.us.players}
        if (wanted <= on_team) if match == "all" else (wanted & on_team):
            out.append(r)
    return out

router = APIRouter(prefix="/api/scout")
scout_limit = RateLimit(limit=20, window=3600)


def _job_key(key: str) -> tuple[str, str]:
    return ("scout", key)


@router.post("", response_model=ScoutStartOut, status_code=status.HTTP_202_ACCEPTED)
def start_scout(body: ScoutIn, request: Request, service: Service):
    if not service.online:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scouting braucht einen Riot-API-Key.")
    accounts, errors = [], []
    for riot_id in body.riot_ids:
        try:
            accounts.append(service.account(riot_id))
        except ValueError as exc:
            errors.append(f"{riot_id}: {exc}")
        except NotFound as exc:
            errors.append(exc.message)
    if errors:
        raise HTTPException(422, {"message": "Spieler konnten nicht gefunden werden.", "errors": errors})
    accounts = list({a["puuid"]: a for a in accounts}.values())
    mode = body.mode if len(accounts) > 1 else "all"
    key = scout_key([a["puuid"] for a in accounts], mode)
    running = service.jobs.get(_job_key(key))
    if not (running and running.status == "running"):
        scout_limit.check(client_ip(request))
    job = service.jobs.run(_job_key(key), lambda j: service.scout(accounts, j, mode=mode))
    return ScoutStartOut(
        key=key,
        mode=mode,
        players=[ScoutPlayer(puuid=a["puuid"], game_name=a["gameName"], tag_line=a["tagLine"]) for a in accounts],
        job=SyncJobOut.model_validate(job),
    )


@router.get("", response_model=list[ScoutSummary])
def recent_scouts(service: Service, limit: Annotated[int, Query(ge=1, le=50)] = 12):
    return [ScoutSummary(**s) for s in service.store.recent_scouts(limit)]


@router.get("/{key}/status", response_model=SyncJobOut | None)
def scout_status(key: str, service: Service):
    return service.jobs.get(_job_key(key))


@router.get("/{key}", response_model=ScoutReportOut)
def scout_report(key: str, service: Service, params: Annotated[ScoutFilters, Query()]):
    scout = service.store.get_scout(key)
    if scout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dieses Scouting gibt es (noch) nicht.")
    filters = Filters(**params.model_dump(include={"label", "side", "patch", "last", "exclude"}))
    if filters.label not in {"all", *LABELS}:
        filters.label = "all"
    roster = scout["roster"]
    names = " + ".join(f"{p['game_name']}#{p['tag_line']}" for p in scout["players"])
    team = Team(id=0, name=names, tag="", min_members=len(scout["players"]), created_at=scout["updated_at"],
                last_synced=scout["updated_at"],
                members=[Member(r["puuid"], r["game_name"], r["tag_line"], r["position"]) for r in roster])
    match = params.match or scout["mode"]
    in_roster = {r["puuid"] for r in roster}
    focus = list(dict.fromkeys(p for p in params.focus if p in in_roster))
    records = with_players(service.scout_records(scout), focus, match)
    selected = filter_records(records, **filters.model_dump())
    selected_ids = {r.match.match_id for r in filter_records(records, **filters.model_dump(exclude={"exclude"}))}
    excluded = set(filters.exclude)
    job = service.jobs.get(_job_key(key))
    return ScoutReportOut(
        key=key,
        mode=scout["mode"],
        players=[ScoutPlayer(**p) for p in scout["players"]],
        roster=[RosterPlayer(**r) for r in roster],
        updated_at=scout["updated_at"],
        filters=filters,
        focus=focus,
        match=match,
        report=build_report(team, selected),
        history=[HistoryRow(**row, selected=row["match_id"] in selected_ids, excluded=row["match_id"] in excluded)
                 for row in history_rows(records)],
        patches=patches(records),
        job=SyncJobOut.model_validate(job) if job else None,
    )
