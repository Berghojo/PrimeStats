"""Sichtbarkeit und Berechtigungen.

- Turniercode-Spiele stammen aus der öffentlichen Riot-API und sind für alle sichtbar (auch fürs Scouting).
- Hochgeladene Scrims sehen ausschließlich Spieler eines Teams, dem das Spiel zugeordnet ist – also
  Konten, deren verknüpfter Riot-Account im Kader dieses Teams steht. Weder Mitspielen allein noch
  „Team erstellt“ oder „Team öffentlich“ reichen: Sonst könnte jeder ein Team aus fremden Riot-IDs
  anlegen und deren Scrims sehen.
- Teams sehen Ersteller und Kader-Mitglieder mit verknüpftem Account; öffentliche Teams alle (ohne Scrims).
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
    owned_teams: set[int] = field(default_factory=set)
    roster_teams: set[int] = field(default_factory=set)   # Kader enthält einen verknüpften Account

    @classmethod
    def load(cls, store: Store, user: UserAccount | None) -> "Viewer":
        if user is None:
            return cls()
        puuids = {link.puuid for link in store.linked_riot_accounts(user.id)}
        return cls(user, puuids, store.owned_team_ids(user.id), store.roster_team_ids(puuids))

    @property
    def member_teams(self) -> set[int]:
        return self.owned_teams | self.roster_teams

    def can_view_team(self, team: Team) -> bool:
        return team.public or team.id in self.member_teams

    def can_edit_team(self, team: Team) -> bool:
        return self.user is not None and team.id in self.member_teams

    def can_delete_team(self, team: Team) -> bool:
        return self.user is not None and team.owner_id == self.user.id

    def can_see_scrims(self, team: Team) -> bool:
        """Scrims eines Teams sind nur für Spieler im Kader sichtbar."""
        return team.id in self.roster_teams

    def can_view_match(self, match: MatchSummary, store: Store) -> bool:
        if not match.private:
            return True
        return bool(store.teams_with_match(match.match_id) & self.roster_teams)
