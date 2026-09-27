"""REST-Endpunkte unter ``/api``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from .ddragon import DataDragon
from .matches import POSITION_LABELS
from .schemas import (AccountOut, AnalysisOut, ChampionOut, Filters, HistoryRow, MatchOut, MetaOut,
                      PlayerGamesOut, SyncJobOut, TeamGameUpdate, TeamIn, TeamOut, TeamReportOut)
from .services import PrimeStats
from .store import Team
from .team_stats import LABELS, build_report, filter_records, history_rows, opponents, patches
from .timeline import analysis_payload

router = APIRouter(prefix="/api")

MAX_ANALYSIS_GAMES = 30


def get_service(request: Request) -> PrimeStats:
    service = request.app.state.service
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Kein Riot-API-Key konfiguriert. Setze LOL_API_KEY oder PRIMESTATS_DEMO=1.")
    return service


Service = Annotated[PrimeStats, Depends(get_service)]


def _team_or_404(service: PrimeStats, team_id: int) -> Team:
    team = service.store.get_team(team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team nicht gefunden.")
    return team


# -------------------------------------------------------------------- Meta
@router.get("/meta", response_model=MetaOut)
def meta(request: Request) -> MetaOut:
    ddragon: DataDragon = request.app.state.ddragon
    champions = {c.key: ChampionOut(id=c.id, name=c.name) for c in ddragon.all()}
    return MetaOut(
        demo=request.app.state.settings.demo,
        configured=request.app.state.service is not None,
        ddragon_version=ddragon.version,
        champions=champions,
        positions=POSITION_LABELS,
        labels=LABELS,
    )


# ----------------------------------------------------------------- Spieler
@router.get("/players/{game_name}/{tag_line}/games", response_model=PlayerGamesOut)
def player_games(game_name: str, tag_line: str, service: Service,
                 count: Annotated[int, Query(ge=5, le=60)] = 20):
    try:
        account, games = service.player_games(f"{game_name}#{tag_line}", count)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return PlayerGamesOut(
        account=AccountOut(puuid=account["puuid"], game_name=account["gameName"], tag_line=account["tagLine"]),
        games=[MatchOut.of(g) for g in games],
    )


# ----------------------------------------------------------------- Matches
@router.get("/matches/{match_id}", response_model=MatchOut)
def match_detail(match_id: str, service: Service):
    return MatchOut.of(service.match(match_id))


@router.get("/analysis", response_model=AnalysisOut)
def analysis(service: Service, m: Annotated[list[str], Query(min_length=1)],
             focus: Annotated[list[str], Query()] = [], team: int | None = None):
    ids = list(dict.fromkeys(m))[:MAX_ANALYSIS_GAMES]
    items = []
    for mid in ids:
        match = service.match(mid)
        summary = service.timeline_summary(match)
        if summary:
            items.append((match, summary))
    focus_set = set(focus)
    if team is not None:
        team_obj = service.store.get_team(team)
        if team_obj:
            focus_set |= team_obj.puuids
    payload = analysis_payload(items, focus_set)
    matches = sorted((match for match, _ in items), key=lambda x: x.created, reverse=True)
    return AnalysisOut(**payload, matches=[MatchOut.of(x) for x in matches])


# ------------------------------------------------------------------- Teams
def _resolve(service: PrimeStats, body: TeamIn):
    members, errors = service.resolve_members([(m.riot_id, m.role) for m in body.members])
    if errors or not members:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            {"message": "Spieler konnten nicht gefunden werden.",
                             "errors": errors or ["Mindestens ein Spieler ist Pflicht."]})
    return members


@router.get("/teams", response_model=list[TeamOut])
def list_teams(service: Service):
    return service.store.list_teams()


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamIn, service: Service):
    members = _resolve(service, body)
    team_id = service.store.create_team(body.name, body.tag, body.min_members, members)
    return service.store.get_team(team_id)


@router.get("/teams/{team_id}", response_model=TeamOut)
def get_team(team_id: int, service: Service):
    return _team_or_404(service, team_id)


@router.put("/teams/{team_id}", response_model=TeamOut)
def update_team(team_id: int, body: TeamIn, service: Service):
    _team_or_404(service, team_id)
    members = _resolve(service, body)
    service.store.update_team(team_id, body.name, body.tag, body.min_members, members)
    return service.store.get_team(team_id)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: int, service: Service):
    _team_or_404(service, team_id)
    service.store.delete_team(team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/teams/{team_id}/report", response_model=TeamReportOut)
def team_report(team_id: int, service: Service, filters: Annotated[Filters, Query()]):
    team = _team_or_404(service, team_id)
    if filters.label not in {"all", *LABELS}:
        filters.label = "all"
    records = service.team_records(team)
    selected = filter_records(records, **filters.model_dump())
    selected_ids = {r.match.match_id for r in selected}
    history = [HistoryRow(**row, selected=row["match_id"] in selected_ids) for row in history_rows(records)]
    job = service.jobs.get(team_id)
    return TeamReportOut(
        team=TeamOut.model_validate(team),
        filters=filters,
        report=build_report(team, selected),
        history=history,
        patches=patches(records),
        opponents=opponents(records),
        job=SyncJobOut.model_validate(job) if job else None,
    )


@router.post("/teams/{team_id}/sync", response_model=SyncJobOut, status_code=status.HTTP_202_ACCEPTED)
def start_sync(team_id: int, service: Service):
    team = _team_or_404(service, team_id)
    return service.jobs.start(team)


@router.get("/teams/{team_id}/sync", response_model=SyncJobOut | None)
def sync_status(team_id: int, service: Service):
    _team_or_404(service, team_id)
    return service.jobs.get(team_id)


@router.patch("/teams/{team_id}/games/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_team_game(team_id: int, match_id: str, body: TeamGameUpdate, service: Service):
    _team_or_404(service, team_id)
    if not service.store.update_team_game(team_id, match_id, label=body.label, included=body.included):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Spiel gehört nicht zu diesem Team.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

