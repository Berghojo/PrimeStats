"""Gruppen: mehrere Teams bzw. Scoutings speichern und ihre Kennzahlen und Spieler vergleichen.

Verglichen werden nur Turnierspiele (Prime League, mit Turniercode) – Scrims und Custom Games ohne Code zählen
nicht, damit alle Teams auf derselben Grundlage stehen. Gruppen gibt es nur für angemeldete Nutzer: Eine Gruppe
gehört einem Konto, andere angemeldete Nutzer können sie über den Link ansehen. Teams, die der Betrachter nicht
sehen darf, erscheinen nur als „nicht verfügbar“.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from .deps import CurrentUser, CurrentViewer, Service
from .schemas import (GroupCompareOut, GroupEntry, GroupEntryOut, GroupFilters, GroupIn, GroupOut, GroupSummary, GroupTeamStats,
                      GroupUpdate, MonsterStat, Overview, PlayerReport)
from .scout_api import scout_team, scout_title
from .store import GroupData
from .team_stats import build_report, filter_records, patches

router = APIRouter(prefix="/api/groups")

#: Obergrenze je Konto
MAX_GROUPS = 30
MAX_ENTRIES = 16
NOT_FOUND = "Diese Gruppe gibt es nicht."


def _entries(body_entries) -> list[dict]:
    """Einträge ohne Doppelte (gleiches Team/Scouting nur einmal)."""
    seen, out = set(), []
    for e in body_entries:
        if (e.kind, e.ref) not in seen:
            seen.add((e.kind, e.ref))
            out.append({"kind": e.kind, "ref": e.ref, "name": e.name})
    return out


def _resolve(service, viewer, entry: dict):
    """(Eintrag für die Ausgabe, Team, Spiele) – Team/Spiele sind ``None``, wenn nicht verfügbar."""
    name = entry.get("name", "")
    if entry["kind"] == "team":
        team = service.store.get_team(int(entry["ref"]))
        if team is None or not viewer.can_view_team(team):
            return GroupEntryOut(**entry, title=name or "Team nicht verfügbar", available=False), None, None
        out = GroupEntryOut(**entry, title=name or team.name, tag=team.tag)
        return out, team, lambda: service.team_records(team)
    scout = service.store.get_scout(entry["ref"])
    if scout is None:
        return GroupEntryOut(**entry, title=name or "Scouting nicht verfügbar", available=False), None, None
    return (GroupEntryOut(**entry, title=name or scout_title(scout)), scout_team(scout),
            lambda: service.scout_records(scout))


def _group_out(service, viewer, group: GroupData) -> GroupOut:
    return GroupOut(key=group.key, name=group.name, updated_at=group.updated_at,
                    can_edit=viewer.user is not None and viewer.user.id == group.user_id,
                    entries=[_resolve(service, viewer, e)[0] for e in group.entries])


def _get(service, key: str) -> GroupData:
    group = service.store.get_group(key)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return group


@router.get("", response_model=list[GroupSummary])
def list_groups(service: Service, viewer: CurrentViewer, user: CurrentUser):
    return [GroupSummary(key=g.key, name=g.name, updated_at=g.updated_at,
                         teams=[e.title for e in _group_out(service, viewer, g).entries])
            for g in service.store.list_groups(user.id)]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupIn, service: Service, viewer: CurrentViewer, user: CurrentUser):
    if service.store.count_groups(user.id) >= MAX_GROUPS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_GROUPS} Gruppen – bitte eine löschen.")
    return _group_out(service, viewer, service.store.create_group(user.id, body.name, _entries(body.entries)))


@router.get("/{key}", response_model=GroupOut)
def get_group(key: str, service: Service, viewer: CurrentViewer, _user: CurrentUser):
    return _group_out(service, viewer, _get(service, key))


@router.patch("/{key}", response_model=GroupOut)
def update_group(key: str, body: GroupUpdate, service: Service, viewer: CurrentViewer, user: CurrentUser):
    entries = _entries(body.entries) if body.entries is not None else None
    group = service.store.update_group(user.id, key, name=body.name, entries=entries)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return _group_out(service, viewer, group)


@router.post("/{key}/entries", response_model=GroupOut)
def add_entry(key: str, body: GroupEntry, service: Service, viewer: CurrentViewer, user: CurrentUser):
    """Hängt ein Team/Scouting an (z.B. „Zu Gruppe hinzufügen“ auf der Team- oder Scouting-Seite)."""
    group = service.store.get_group(key)
    if group is None or group.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    entries = _entries([GroupEntry(**e) for e in group.entries] + [body])
    if len(entries) > MAX_ENTRIES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_ENTRIES} Teams je Gruppe.")
    return _group_out(service, viewer, service.store.update_group(user.id, key, entries=entries))


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(key: str, service: Service, user: CurrentUser):
    if not service.store.delete_group(user.id, key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{key}/compare", response_model=GroupCompareOut)
def compare_group(key: str, service: Service, viewer: CurrentViewer, _user: CurrentUser, filters: Annotated[GroupFilters, Query()]):
    group = _get(service, key)
    if filters.side not in {"all", "blue", "red"}:
        filters.side = "all"
    teams, all_patches = [], set()
    for entry in group.entries:
        out, team, load = _resolve(service, viewer, entry)
        if team is None:
            teams.append(GroupTeamStats(entry=out))
            continue
        job = service.jobs.get(team.id if entry["kind"] == "team" else ("scout", entry["ref"]))
        records = [r for r in load() if r.match.tournament_code]  # nur Turnierspiele
        all_patches.update(patches(records))
        report = build_report(team, filter_records(records, **filters.model_dump()))
        teams.append(GroupTeamStats(
            entry=out,
            syncing=bool(job and job.status == "running"),
            overview=Overview(**report["overview"]),
            monsters=[MonsterStat(**m) for m in report["monsters"]],
            players=[PlayerReport(**{**p, "champions": p["champions"][:3]}) for p in report["players"]],
        ))
    ordered = sorted(all_patches, key=lambda v: [int(x) if x.isdigit() else 0 for x in v.split(".")], reverse=True)
    return GroupCompareOut(group=_group_out(service, viewer, group), filters=filters, patches=ordered, teams=teams)
