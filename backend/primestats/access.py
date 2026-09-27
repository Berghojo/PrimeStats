"""Sichtbarkeit und Berechtigungen.

- Turniercode-Spiele stammen aus der öffentlichen Riot-API und sind für alle sichtbar.
- Hochgeladene Scrims sieht nur, wer mitgespielt hat (verknüpfter Riot-Account) oder Zugriff auf ein
  Team hat, dem das Spiel zugeordnet ist.
- Teams sehen Ersteller und Kader-Mitglieder mit verknüpftem Account; öffentliche Teams alle.
  Bearbeiten dürfen Ersteller und verknüpfte Kader-Mitglieder, löschen nur der Ersteller.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .matches import MatchSummary
from .store import Store, Team, UserAccount


@dataclass
class Viewer:
    user: UserAccount | None = None
    puuids: set[str] = field(default_factory=set)
    member_teams: set[int] = field(default_factory=set)   # erstellt oder im Kader
    public_teams: set[int] = field(default_factory=set)

    @classmethod
    def load(cls, store: Store, user: UserAccount | None) -> "Viewer":
        public = store.public_team_ids()
        if user is None:
            return cls(public_teams=public)
        puuids = {link.puuid for link in store.linked_riot_accounts(user.id)}
        return cls(user, puuids, store.team_ids_for(user.id, puuids), public)

    @property
    def visible_teams(self) -> set[int]:
        return self.member_teams | self.public_teams

    def can_view_team(self, team: Team) -> bool:
        return team.public or team.id in self.member_teams

    def can_edit_team(self, team: Team) -> bool:
        return self.user is not None and team.id in self.member_teams

    def can_delete_team(self, team: Team) -> bool:
        return self.user is not None and team.owner_id == self.user.id

    def can_view_match(self, match: MatchSummary, store: Store) -> bool:
        if not match.private:
            return True
        if self.puuids & {p.puuid for p in match.participants}:
            return True
        return bool(store.teams_with_match(match.match_id) & self.visible_teams)
