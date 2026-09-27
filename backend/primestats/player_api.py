"""Spieler-Einzelansicht: Solo/Duo, Flex, Turnier und (sichtbare) Scrims eines Spielers."""

from __future__ import annotations

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from .deps import CurrentViewer, RateLimit, Service, client_ip
from .player_stats import build_player_report, filter_player_records, player_history
from .riot import NotFound
from .schemas import PlayerFilters, PlayerReportOut, PlayerStatsReport, ScoutPlayer, SyncJobOut
from .team_stats import patches

router = APIRouter(prefix="/api/players")
player_sync_limit = RateLimit(limit=30, window=3600)


def _account(service, name: str, tag: str) -> dict:
    try:
        return service.account(f"{name}#{tag}")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None


def _job_key(puuid: str) -> tuple[str, str]:
    return ("player", puuid)


@router.post("/{game_name}/{tag_line}/sync", response_model=SyncJobOut, status_code=status.HTTP_202_ACCEPTED)
def sync_player(game_name: str, tag_line: str, request: Request, service: Service):
    if not service.online:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Laden braucht einen Riot-API-Key.")
    account = _account(service, game_name, tag_line)
    running = service.jobs.get(_job_key(account["puuid"]))
    if not (running and running.status == "running"):
        player_sync_limit.check(client_ip(request))
    return service.jobs.run(_job_key(account["puuid"]), lambda job: service.sync_player(account, job))


@router.get("/{game_name}/{tag_line}/sync", response_model=SyncJobOut | None)
def player_sync_status(game_name: str, tag_line: str, service: Service):
    account = _account(service, game_name, tag_line)
    return service.jobs.get(_job_key(account["puuid"]))


@router.get("/{game_name}/{tag_line}/report", response_model=PlayerReportOut)
def player_report(game_name: str, tag_line: str, service: Service, viewer: CurrentViewer,
                  filters: Annotated[PlayerFilters, Query()]):
    account = _account(service, game_name, tag_line)
    puuid = account["puuid"]
    records = service.player_records(puuid, lambda m: viewer.can_view_match(m, service.store))
    in_filter = filter_player_records(records, puuid, queues=set(filters.queue), patch=filters.patch,
                                      last=filters.last, champion=filters.champion, role=filters.role)
    excluded = set(filters.exclude)
    selected = [r for r in in_filter if r.match.match_id not in excluded]
    stats = build_player_report(puuid, selected)
    stats["history"] = player_history(puuid, in_filter, excluded)
    champs = Counter(p.champion_id for r in records if (p := r.match.player(puuid)))
    roles = Counter(p.position for r in records if (p := r.match.player(puuid)) and p.position)
    job = service.jobs.get(_job_key(puuid))
    return PlayerReportOut(
        account=ScoutPlayer(puuid=puuid, game_name=account["gameName"], tag_line=account["tagLine"]),
        filters=filters,
        report=PlayerStatsReport(**{k: v for k, v in stats.items() if k not in ("puuid", "name", "tag")}),
        queue_counts=dict(Counter(r.label for r in records)),
        patches=patches(records),
        champions=[c for c, _ in champs.most_common()],
        roles=[r for r, _ in roles.most_common()],
        last_fetch=service.store.player_last_fetch(puuid),
        job=SyncJobOut.model_validate(job) if job else None,
    )
