"""Turnier-Scouting: Kader und Statistiken eines Teams ab einem einzigen Spieler (öffentlich)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from .deps import RateLimit, Service, client_ip
from .schemas import (AccountOut, Filters, HistoryRow, RosterPlayer, ScoutIn, ScoutReportOut, ScoutStartOut,
                      ScoutSummary, SyncJobOut)
from .store import Member, Team
from .team_stats import LABELS, build_report, filter_records, history_rows, patches

router = APIRouter(prefix="/api/scout")
scout_limit = RateLimit(limit=20, window=3600)


def _job_key(puuid: str) -> tuple[str, str]:
    return ("scout", puuid)


@router.post("", response_model=ScoutStartOut, status_code=status.HTTP_202_ACCEPTED)
def start_scout(body: ScoutIn, request: Request, service: Service):
    if not service.online:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scouting braucht einen Riot-API-Key.")
    try:
        account = service.account(body.riot_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    key = _job_key(account["puuid"])
    running = service.jobs.get(key)
    if not (running and running.status == "running"):
        scout_limit.check(client_ip(request))
    job = service.jobs.run(key, lambda j: service.scout(account, j, min_members=body.min_members))
    return ScoutStartOut(puuid=account["puuid"], game_name=account["gameName"], tag_line=account["tagLine"],
                         job=SyncJobOut.model_validate(job))


@router.get("", response_model=list[ScoutSummary])
def recent_scouts(service: Service, limit: Annotated[int, Query(ge=1, le=50)] = 12):
    return [ScoutSummary(**s) for s in service.store.recent_scouts(limit)]


@router.get("/{puuid}/status", response_model=SyncJobOut | None)
def scout_status(puuid: str, service: Service):
    return service.jobs.get(_job_key(puuid))


@router.get("/{puuid}", response_model=ScoutReportOut)
def scout_report(puuid: str, service: Service, filters: Annotated[Filters, Query()]):
    scout = service.store.get_scout(puuid)
    if scout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Für diesen Spieler gibt es noch kein Scouting.")
    if filters.label not in {"all", *LABELS}:
        filters.label = "all"
    roster = scout["roster"]
    # Alles läuft unter dem gesuchten Spieler – kein geratenes Teamkürzel
    team = Team(id=0, name=f"{scout['game_name']}#{scout['tag_line']}", tag="", min_members=scout["min_members"],
                created_at=scout["updated_at"], last_synced=scout["updated_at"],
                members=[Member(r["puuid"], r["game_name"], r["tag_line"], r["position"]) for r in roster])
    records = service.scout_records(scout)
    selected = filter_records(records, **filters.model_dump())
    selected_ids = {r.match.match_id for r in selected}
    job = service.jobs.get(_job_key(puuid))
    return ScoutReportOut(
        player=AccountOut(puuid=scout["puuid"], game_name=scout["game_name"], tag_line=scout["tag_line"]),
        roster=[RosterPlayer(**r) for r in roster],
        min_members=scout["min_members"],
        updated_at=scout["updated_at"],
        filters=filters,
        report=build_report(team, selected),
        history=[HistoryRow(**row, selected=row["match_id"] in selected_ids) for row in history_rows(records)],
        patches=patches(records),
        job=SyncJobOut.model_validate(job) if job else None,
    )

