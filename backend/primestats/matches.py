"""Umwandlung der rohen match-v5-Antwort in handliche Datenobjekte."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

POSITIONS = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
POSITION_LABELS = {"TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "ADC", "UTILITY": "Support"}
BLUE, RED = 100, 200
SMITE = 11


@dataclass
class PlayerLine:
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
    cs: int
    gold: int
    damage: int            # Schaden an Champions
    damage_taken: int
    vision_score: int
    wards_placed: int
    wards_killed: int
    control_wards: int
    level: int
    first_blood: bool      # Kill oder Assist am First Blood
    items: list[int] = field(default_factory=list)
    spells: tuple[int, int] = (0, 0)

    @property
    def riot_id(self) -> str:
        return f"{self.name}#{self.tag}" if self.tag else self.name

    @property
    def kda(self) -> float:
        return (self.kills + self.assists) / max(self.deaths, 1)


@dataclass
class TeamLine:
    team_id: int
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
    players: list[PlayerLine]

    @property
    def side(self) -> str:
        return "blue" if self.team_id == BLUE else "red"

    @property
    def gold(self) -> int:
        return sum(p.gold for p in self.players)

    @property
    def damage(self) -> int:
        return sum(p.damage for p in self.players)

    def by_position(self) -> dict[str, PlayerLine]:
        return {p.position: p for p in self.players}


@dataclass
class MatchSummary:
    match_id: str
    created: datetime
    duration: int          # Sekunden
    version: str           # Patch, z.B. "15.14"
    game_type: str
    queue_id: int
    tournament_code: str
    teams: dict[int, TeamLine]
    #: "riot" (Riot-API) oder "lcu" (per Uploader aus dem League Client)
    source: str = "riot"

    @property
    def minutes(self) -> float:
        return max(self.duration / 60, 1 / 60)

    @property
    def is_custom(self) -> bool:
        return self.game_type == "CUSTOM_GAME" or self.queue_id == 0

    @property
    def private(self) -> bool:
        """Hochgeladene Custom Games ohne Turniercode (Scrims) sind nicht öffentlich."""
        return self.source == "lcu" and not self.tournament_code

    @property
    def participants(self) -> list[PlayerLine]:
        return [p for t in self.teams.values() for p in t.players]

    def team_of(self, puuid: str) -> TeamLine | None:
        for team in self.teams.values():
            if any(p.puuid == puuid for p in team.players):
                return team
        return None

    def enemy_of(self, team_id: int) -> TeamLine:
        return self.teams[RED if team_id == BLUE else BLUE]

    def player(self, puuid: str) -> PlayerLine | None:
        return next((p for p in self.participants if p.puuid == puuid), None)

    def opponent(self, player: PlayerLine) -> PlayerLine | None:
        return self.enemy_of(player.team_id).by_position().get(player.position)


def _assign_positions(participants: list[dict]) -> dict[int, str]:
    """Positionen pro Participant – robust für Custom Games ohne Rolleninfo."""
    result: dict[int, str] = {}
    for key in ("teamPosition", "individualPosition"):
        guess = {p["participantId"]: p.get(key) or "" for p in participants}
        if all(v in POSITIONS for v in guess.values()) and len(set(guess.values())) == len(participants):
            return guess
        # teilweise verwertbar: eindeutige gültige Positionen übernehmen
        counts = Counter(guess.values())
        for pid, pos in guess.items():
            if pid not in result and pos in POSITIONS and counts[pos] == 1 and pos not in result.values():
                result[pid] = pos
    # Smite -> Jungle
    for p in participants:
        pid = p["participantId"]
        if pid not in result and SMITE in (p.get("summoner1Id"), p.get("summoner2Id")) \
                and "JUNGLE" not in result.values():
            result[pid] = "JUNGLE"
    # Rest in Lobby-Reihenfolge auffüllen
    free = [pos for pos in POSITIONS if pos not in result.values()]
    for p in participants:
        if p["participantId"] not in result and free:
            result[p["participantId"]] = free.pop(0)
    return result


def _objective(objectives: dict, key: str) -> tuple[int, bool]:
    obj = objectives.get(key) or {}
    return int(obj.get("kills", 0)), bool(obj.get("first", False))


def parse_match(data: dict) -> MatchSummary:
    info = data["info"]
    participants = info["participants"]
    teams: dict[int, TeamLine] = {}
    for team in info["teams"]:
        team_id = team["teamId"]
        members = sorted((p for p in participants if p["teamId"] == team_id), key=lambda p: p["participantId"])
        positions = _assign_positions(members)
        players = []
        for p in members:
            players.append(PlayerLine(
                participant_id=p["participantId"],
                puuid=p["puuid"],
                name=p.get("riotIdGameName") or p.get("summonerName") or "?",
                tag=p.get("riotIdTagline") or "",
                team_id=team_id,
                position=positions.get(p["participantId"], ""),
                champion_id=int(p["championId"]),
                win=bool(p["win"]),
                kills=p.get("kills", 0),
                deaths=p.get("deaths", 0),
                assists=p.get("assists", 0),
                cs=p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
                gold=p.get("goldEarned", 0),
                damage=p.get("totalDamageDealtToChampions", 0),
                damage_taken=p.get("totalDamageTaken", 0),
                vision_score=p.get("visionScore", 0),
                wards_placed=p.get("wardsPlaced", 0),
                wards_killed=p.get("wardsKilled", 0),
                control_wards=p.get("visionWardsBoughtInGame", 0),
                level=p.get("champLevel", 0),
                first_blood=bool(p.get("firstBloodKill") or p.get("firstBloodAssist")),
                items=[p.get(f"item{i}", 0) for i in range(7)],
                spells=(p.get("summoner1Id", 0), p.get("summoner2Id", 0)),
            ))
        players.sort(key=lambda pl: POSITIONS.index(pl.position) if pl.position in POSITIONS else 9)
        objectives = team.get("objectives") or {}
        kills, first_blood = _objective(objectives, "champion")
        towers, first_tower = _objective(objectives, "tower")
        dragons, first_dragon = _objective(objectives, "dragon")
        barons, first_baron = _objective(objectives, "baron")
        heralds, first_herald = _objective(objectives, "riftHerald")
        grubs, first_grubs = _objective(objectives, "horde")
        atakhan, _ = _objective(objectives, "atakhan")
        inhibitors, _ = _objective(objectives, "inhibitor")
        bans = [b["championId"] for b in sorted(team.get("bans") or [], key=lambda b: b.get("pickTurn", 0))]
        teams[team_id] = TeamLine(
            team_id=team_id, win=bool(team["win"]), bans=[b for b in bans if b and b > 0],
            kills=kills or sum(p.kills for p in players), towers=towers, inhibitors=inhibitors,
            dragons=dragons, barons=barons, heralds=heralds, grubs=grubs, atakhan=atakhan,
            first_blood=first_blood, first_tower=first_tower, first_dragon=first_dragon,
            first_baron=first_baron, first_herald=first_herald, first_grubs=first_grubs,
            players=players,
        )

    # gameDuration ist seit Patch 11.20 in Sekunden (davor Millisekunden)
    duration = int(info.get("gameDuration", 0))
    if "gameEndTimestamp" not in info and duration > 10_000:
        duration //= 1000
    version = ".".join(str(info.get("gameVersion", "")).split(".")[:2])
    created = datetime.fromtimestamp(info.get("gameCreation", 0) / 1000, tz=timezone.utc)
    return MatchSummary(
        match_id=data["metadata"]["matchId"],
        created=created,
        duration=duration,
        version=version,
        game_type=info.get("gameType", ""),
        queue_id=int(info.get("queueId", -1)),
        tournament_code=info.get("tournamentCode") or "",
        teams=teams,
        source=data["metadata"].get("source", "riot"),
    )
