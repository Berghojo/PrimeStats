"""REST-Endpunkte unter ``/api`` (Spieler, Matches, Analyse, Teams)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from .access import Viewer
from .ddragon import DataDragon
from .deps import CurrentUser, CurrentViewer, Service
from .matches import POSITION_LABELS
from .schemas import (AccountOut, AnalysisOut, ChampionOut, Filters, HistoryRow, MatchOut, MetaOut,
                      PlayerGamesOut, SyncJobOut, TeamGameUpdate, TeamIn, TeamOut, TeamReportOut)
from .services import PrimeStats
from .store import Team
from .team_stats import LABELS, build_report, filter_records, history_rows, patches
from .timeline import analysis_payload

router = APIRouter(prefix="/api")

MAX_ANALYSIS_GAMES = 30
NOT_FOUND = "Team nicht gefunden."


def _visible_team(service: PrimeStats, viewer, team_id: int) -> Team:
    """Team, falls der Betrachter es sehen darf – sonst 404 (Existenz wird nicht verraten)."""
    team = service.store.get_team(team_id)
    if team is None or not viewer.can_view_team(team):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return team


def _editable_team(service: PrimeStats, viewer, team_id: int) -> Team:
    team = _visible_team(service, viewer, team_id)
    if not viewer.can_edit_team(team):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Nur der Ersteller und Kader-Mitglieder mit verknüpftem Riot-Account dürfen das Team ändern.")
    return team


# -------------------------------------------------------------------- Meta
@router.get("/meta", response_model=MetaOut)
def meta(request: Request) -> MetaOut:
    ddragon: DataDragon = request.app.state.ddragon
    champions = {c.key: ChampionOut(id=c.id, name=c.name) for c in ddragon.all()}
    return MetaOut(
        demo=request.app.state.settings.demo,
        configured=request.app.state.service.online,
        uploader_url=request.app.state.settings.uploader_url,
        ddragon_version=ddragon.version,
        champions=champions,
        positions=POSITION_LABELS,
        labels=LABELS,
    )


# ----------------------------------------------------------------- Spieler
@router.get("/players/{game_name}/{tag_line}/games", response_model=PlayerGamesOut)
def player_games(game_name: str, tag_line: str, service: Service, viewer: CurrentViewer,
                 count: Annotated[int, Query(ge=5, le=60)] = 20):
    try:
        account, games = service.player_games(f"{game_name}#{tag_line}", count,
                                              visible=lambda m: viewer.can_view_match(m, service.store))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return PlayerGamesOut(
        account=AccountOut(puuid=account["puuid"], game_name=account["gameName"], tag_line=account["tagLine"]),
        games=[MatchOut.of(g) for g in games],
    )


# ----------------------------------------------------------------- Matches
def _visible_match(service: PrimeStats, viewer, match_id: str):
    match = service.match(match_id)
    if not viewer.can_view_match(match, service.store):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return match


@router.get("/matches/{match_id}", response_model=MatchOut)
def match_detail(match_id: str, service: Service, viewer: CurrentViewer):
    return MatchOut.of(_visible_match(service, viewer, match_id))


@router.get("/analysis", response_model=AnalysisOut)
def analysis(service: Service, viewer: CurrentViewer, m: Annotated[list[str], Query(min_length=1)],
             focus: Annotated[list[str], Query()] = [], team: int | None = None):
    ids = list(dict.fromkeys(m))[:MAX_ANALYSIS_GAMES]
    items = []
    for mid in ids:
        match = _visible_match(service, viewer, mid)
        summary = service.timeline_summary(match, fetch=service.online)
        if summary:
            items.append((match, summary))
    focus_set = set(focus)
    if team is not None:
        team_obj = service.store.get_team(team)
        if team_obj and viewer.can_view_team(team_obj):
            focus_set |= team_obj.puuids
    payload = analysis_payload(items, focus_set)
    matches = sorted((match for match, _ in items), key=lambda x: x.created, reverse=True)
    return AnalysisOut(**payload, matches=[MatchOut.of(x) for x in matches])


# ------------------------------------------------------------------- Teams
def _resolve(service: PrimeStats, body: TeamIn):
    members, errors = service.resolve_members([(m.riot_id, m.role) for m in body.members])
    if errors or not members:
        raise HTTPException(422, {"message": "Spieler konnten nicht gefunden werden.",
                                  "errors": errors or ["Mindestens ein Spieler ist Pflicht."]})
    return members


@router.get("/teams", response_model=list[TeamOut])
def list_teams(service: Service, viewer: CurrentViewer):
    return [TeamOut.of(t, viewer) for t in service.store.list_teams() if viewer.can_view_team(t)]


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamIn, service: Service, user: CurrentUser):
    members = _resolve(service, body)
    team_id = service.store.create_team(body.name, body.tag, body.min_members, members,
                                        owner_id=user.id, public=body.public)
    team = service.store.get_team(team_id)
    return TeamOut.of(team, _viewer(service, user))


def _viewer(service: PrimeStats, user) -> Viewer:
    return Viewer.load(service.store, user)


@router.get("/teams/{team_id}", response_model=TeamOut)
def get_team(team_id: int, service: Service, viewer: CurrentViewer):
    return TeamOut.of(_visible_team(service, viewer, team_id), viewer)


@router.put("/teams/{team_id}", response_model=TeamOut)
def update_team(team_id: int, body: TeamIn, service: Service, viewer: CurrentViewer):
    _editable_team(service, viewer, team_id)
    members = _resolve(service, body)
    service.store.update_team(team_id, body.name, body.tag, body.min_members, members, public=body.public)
    return TeamOut.of(service.store.get_team(team_id), _viewer(service, viewer.user))


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: int, service: Service, viewer: CurrentViewer):
    team = _visible_team(service, viewer, team_id)
    if not viewer.can_delete_team(team):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur der Ersteller darf das Team löschen.")
    service.store.delete_team(team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/teams/{team_id}/report", response_model=TeamReportOut)
def team_report(team_id: int, service: Service, viewer: CurrentViewer, filters: Annotated[Filters, Query()]):
    team = _visible_team(service, viewer, team_id)
    if filters.label not in {"all", *LABELS}:
        filters.label = "all"
    records = service.team_records(team)
    if not viewer.can_see_scrims(team):
        records = [r for r in records if not r.match.private]
    selected = filter_records(records, **filters.model_dump())
    in_filter = {r.match.match_id for r in filter_records(records, **filters.model_dump(exclude={"exclude"}))}
    excluded = set(filters.exclude)
    history = [HistoryRow(**row, selected=row["match_id"] in in_filter, excluded=row["match_id"] in excluded)
               for row in history_rows(records)]
    job = service.jobs.get(team_id)
    return TeamReportOut(
        team=TeamOut.of(team, viewer),
        filters=filters,
        report=build_report(team, selected),
        history=history,
        patches=patches(records),
        job=SyncJobOut.model_validate(job) if job else None,
    )


@router.post("/teams/{team_id}/sync", response_model=SyncJobOut, status_code=status.HTTP_202_ACCEPTED)
def start_sync(team_id: int, service: Service, viewer: CurrentViewer):
    team = _editable_team(service, viewer, team_id)
    return service.jobs.start(team)


@router.get("/teams/{team_id}/sync", response_model=SyncJobOut | None)
def sync_status(team_id: int, service: Service, viewer: CurrentViewer):
    _visible_team(service, viewer, team_id)
    return service.jobs.get(team_id)


@router.patch("/teams/{team_id}/games/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_team_game(team_id: int, match_id: str, body: TeamGameUpdate, service: Service, viewer: CurrentViewer):
    _editable_team(service, viewer, team_id)
    bans = None
    if body.bans is not None:
        if match_id not in {tg.match_id for tg in service.store.team_games(team_id)}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Spiel gehört nicht zu diesem Team.")
        if any(t.bans for t in service.match(match_id).teams.values()):
            raise HTTPException(status.HTTP_409_CONFLICT, "Dieses Spiel hat bereits Bans aus dem Client.")
        picked = body.bans.us + body.bans.them
        if len(set(picked)) != len(picked):
            raise HTTPException(422, "Jeder Champion kann nur einmal gebannt werden.")
        bans = body.bans.model_dump() if picked else None
    if not service.store.update_team_game(team_id, match_id, label=body.label, included=body.included,
                                          opponent=body.opponent, bans=bans,
                                          clear_bans=body.bans is not None and bans is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Spiel gehört nicht zu diesem Team.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
