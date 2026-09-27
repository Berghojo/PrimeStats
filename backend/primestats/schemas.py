"""Pydantic-Modelle der JSON-API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .matches import POSITIONS


class _Attrs(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------- Meta
class ChampionOut(BaseModel):
    id: str
    name: str


class MetaOut(BaseModel):
    demo: bool
    #: Riot-API verfügbar (sonst nur hochgeladene Spiele)
    configured: bool
    uploader_url: str
    ddragon_version: str
    champions: dict[int, ChampionOut]
    positions: dict[str, str]
    labels: dict[str, str]


# ----------------------------------------------------------------- Matches
class PlayerOut(_Attrs):
    participant_id: int
    puuid: str
    name: str
    tag: str
    team_id: int
    position: str
    champion_id: int
    win: bool
    kills: int
    deaths: int
    assists: int
    kda: float
    cs: int
    gold: int
    damage: int
    damage_taken: int
    vision_score: int
    wards_placed: int
    wards_killed: int
    control_wards: int
    level: int
    first_blood: bool
    items: list[int]
    spells: tuple[int, int]


class TeamSideOut(_Attrs):
    team_id: int
    side: Literal["blue", "red"]
    win: bool
    bans: list[int]
    kills: int
    towers: int
    inhibitors: int
    dragons: int
    barons: int
    heralds: int
    grubs: int
    atakhan: int
    first_blood: bool
    first_tower: bool
    first_dragon: bool
    first_baron: bool
    first_herald: bool
    first_grubs: bool
    gold: int
    damage: int
    players: list[PlayerOut]


class MatchOut(BaseModel):
    match_id: str
    created: datetime
    duration: int
    version: str
    game_type: str
    queue_id: int
    tournament_code: str
    blue: TeamSideOut
    red: TeamSideOut

    @classmethod
    def of(cls, match) -> "MatchOut":
        return cls(
            match_id=match.match_id, created=match.created, duration=match.duration, version=match.version,
            game_type=match.game_type, queue_id=match.queue_id, tournament_code=match.tournament_code,
            blue=TeamSideOut.model_validate(match.teams[100]), red=TeamSideOut.model_validate(match.teams[200]),
        )


class AccountOut(BaseModel):
    puuid: str
    game_name: str
    tag_line: str


class PlayerGamesOut(BaseModel):
    account: AccountOut
    games: list[MatchOut]


# ---------------------------------------------------------------- Analysis
class StatDef(BaseModel):
    key: str
    label: str


class AnalysisPlayer(BaseModel):
    puuid: str
    name: str
    games: int
    position: str
    focus: bool


class AnalysisOut(BaseModel):
    stats: list[StatDef]
    players: list[AnalysisPlayer]
    series: dict[str, dict[str, list[float | None]]]
    minutes: int
    matches: list[MatchOut]


# ------------------------------------------------------------------- Teams
class MemberIn(BaseModel):
    riot_id: str = Field(min_length=1, max_length=30)
    role: str = ""

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        return value if value in POSITIONS else ""


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    tag: str = Field(default="", max_length=8)
    min_members: int = Field(default=4, ge=1, le=5)
    public: bool = False
    members: list[MemberIn] = Field(min_length=1, max_length=12)

    @field_validator("name", "tag")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class MemberOut(_Attrs):
    puuid: str
    game_name: str
    tag_line: str
    role: str
    riot_id: str


class TeamOut(_Attrs):
    id: int
    name: str
    tag: str
    min_members: int
    created_at: datetime
    last_synced: datetime | None
    members: list[MemberOut]
    public: bool
    #: Berechtigungen des aktuellen Betrachters
    can_edit: bool = False
    can_delete: bool = False
    #: Scrims sind nur für Spieler im Kader (mit verknüpftem Riot-Account) sichtbar
    can_see_scrims: bool = False

    @classmethod
    def of(cls, team, viewer) -> "TeamOut":
        out = cls.model_validate(team)
        out.can_edit = viewer.can_edit_team(team)
        out.can_delete = viewer.can_delete_team(team)
        out.can_see_scrims = viewer.can_see_scrims(team)
        return out


class TeamGameUpdate(BaseModel):
    label: Literal["", "official", "scrim"] | None = None
    included: bool | None = None


class SyncJobOut(_Attrs):
    status: Literal["running", "done", "error"]
    message: str
    done: int
    total: int
    percent: int
    new_games: int
    error: str


# ------------------------------------------------------------ Team-Report
class Overview(BaseModel):
    games: int
    wins: int
    losses: int
    winrate: float | None
    blue_games: int
    blue_wins: int
    blue_winrate: float | None
    red_games: int
    red_wins: int
    red_winrate: float | None
    duration: float | None
    duration_win: float | None
    duration_loss: float | None
    kills: float | None
    deaths: float | None
    towers: float | None
    towers_lost: float | None
    gd10: float | None
    gd15: float | None
    timeline_games: int
    first_blood: float | None
    first_tower: float | None
    first_dragon: float | None
    first_herald: float | None
    first_grubs: float | None
    first_baron: float | None


class ChampionStat(BaseModel):
    champion_id: int
    games: int
    wins: int
    winrate: float
    kills: int
    deaths: int
    assists: int
    kda: float


class PlayerReport(BaseModel):
    puuid: str
    name: str
    member: bool
    position: str
    games: int
    wins: int
    winrate: float
    kills: float
    deaths: float
    assists: float
    kda: float
    cspm: float
    gpm: float
    dpm: float
    dtpm: float
    vspm: float
    wards: float
    wards_killed: float
    control_wards: float
    kp: float | None
    damage_share: float | None
    gold_share: float | None
    first_blood: float
    gd10: float | None
    gd15: float | None
    csd15: float | None
    xpd15: float | None
    champions: list[ChampionStat]


class PickStat(BaseModel):
    champion_id: int
    games: int
    wins: int
    winrate: float
    players: list[str] = []


class BanStat(BaseModel):
    champion_id: int
    count: int


class MonsterStat(BaseModel):
    key: str
    label: str
    us: int
    them: int
    share: float | None
    us_avg: float
    them_avg: float
    first_time: float | None


class Curve(BaseModel):
    values: list[float | None]
    counts: list[int]


class TrendPoint(BaseModel):
    match_id: str
    date: datetime
    win: bool
    gd15: float | None
    kills: int
    deaths: int


class Report(BaseModel):
    overview: Overview
    players: list[PlayerReport]
    picks: list[PickStat]
    enemy_picks: list[PickStat]
    our_bans: list[BanStat]
    enemy_bans: list[BanStat]
    monsters: list[MonsterStat]
    gold_curves: dict[str, Curve]
    trend: list[TrendPoint]


class HistoryRow(BaseModel):
    match_id: str
    date: datetime
    duration: int
    patch: str
    win: bool
    side: Literal["blue", "red"]
    us: TeamSideOut
    them: TeamSideOut
    opponent: str
    gold_diff: int
    gd15: float | None
    label: str
    included: bool
    tournament: bool
    selected: bool


class Filters(BaseModel):
    label: str = "all"
    side: str = "all"
    patch: str = ""
    opponent: str = ""
    last: int = 0


class TeamReportOut(BaseModel):
    team: TeamOut
    filters: Filters
    report: Report
    history: list[HistoryRow]
    patches: list[str]
    opponents: list[str]
    job: SyncJobOut | None


# ------------------------------------------------------------ Konten
_USERNAME = r"^[A-Za-z0-9_.\-]{3,32}$"


class RegisterIn(BaseModel):
    username: str = Field(pattern=_USERNAME, description="3–32 Zeichen: Buchstaben, Ziffern, _ . -")
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    username: str = Field(max_length=32)
    password: str = Field(max_length=200)


class PasswordIn(BaseModel):
    old_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class UserOut(_Attrs):
    id: int
    username: str
    created_at: datetime


class RiotLinkOut(_Attrs):
    puuid: str
    game_name: str
    tag_line: str
    riot_id: str
    linked_at: datetime
    last_upload_at: datetime | None


class MeOut(BaseModel):
    user: UserOut | None
    riot_accounts: list[RiotLinkOut] = []


class LinkCodeOut(BaseModel):
    code: str
    expires_at: datetime


# ------------------------------------------------------------ Uploader
class UploaderStatusIn(BaseModel):
    puuid: str = Field(min_length=10, max_length=100)
    key: str | None = Field(default=None, max_length=100)


class UploaderStatusOut(BaseModel):
    #: Riot-Account ist mit einem Konto verknüpft und der Geräteschlüssel passt
    linked: bool
    username: str | None = None


class UploaderLinkIn(BaseModel):
    code: str = Field(min_length=8, max_length=12)
    puuid: str = Field(min_length=10, max_length=100)
    game_name: str = Field(min_length=1, max_length=32)
    tag_line: str = Field(min_length=1, max_length=8)


class UploaderLinkOut(BaseModel):
    username: str
    #: Geräteschlüssel – das Tool speichert ihn lokal und schickt ihn bei jedem Upload mit
    key: str


class KnownIn(BaseModel):
    match_ids: list[str] = Field(max_length=2000)


class KnownOut(BaseModel):
    known: list[str]


class LcuGame(BaseModel):
    """Ein Spiel wie vom League Client geliefert (``/lol-match-history/v1/games/{id}``)."""

    game: dict
    timeline: dict | None = None


class ImportIn(BaseModel):
    games: list[LcuGame] = Field(max_length=50)


class ImportOut(BaseModel):
    imported: list[str]
    updated: list[str]
    skipped: list[str]
    errors: list[str]
    assigned: dict[str, int]


# ------------------------------------------------------------ Scouting
class ScoutIn(BaseModel):
    riot_id: str = Field(min_length=3, max_length=30)
    min_members: int = Field(default=4, ge=2, le=5)


class ScoutStartOut(BaseModel):
    puuid: str
    game_name: str
    tag_line: str
    job: SyncJobOut


class RosterPlayer(BaseModel):
    puuid: str
    game_name: str
    tag_line: str
    games: int
    position: str


class ScoutSummary(BaseModel):
    puuid: str
    game_name: str
    tag_line: str
    team_tag: str
    games: int
    roster: list[RosterPlayer]
    updated_at: datetime


class ScoutReportOut(BaseModel):
    player: AccountOut
    team_tag: str
    roster: list[RosterPlayer]
    min_members: int
    updated_at: datetime
    filters: Filters
    report: Report
    history: list[HistoryRow]
    patches: list[str]
    opponents: list[str]
    job: SyncJobOut | None
