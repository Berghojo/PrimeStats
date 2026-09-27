"""Konvertierung von League-Client-Daten (LCU-API) ins match-v5-Format.

Der lokale League Client liefert über ``/lol-match-history/v1/games/{gameId}`` und
``/lol-match-history/v1/game-timelines/{gameId}`` Daten im älteren (match-v4-ähnlichen)
Format – im Gegensatz zur Riot-API aber auch für Custom Games ohne Turniercode.
Damit Parser und Statistiken unverändert funktionieren, wird hier ins v5-Format übersetzt.

Die LCU-API ist nicht offiziell dokumentiert; die Umwandlung ist deshalb bewusst
tolerant gegenüber fehlenden oder anders benannten Feldern.
"""

from __future__ import annotations

from typing import Any

from .matches import POSITIONS

#: v4-Lane/Rolle -> v5-Position
_LANES = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MIDDLE", "MID": "MIDDLE", "BOTTOM": "BOTTOM", "BOT": "BOTTOM"}
_SUPPORT_ROLES = {"DUO_SUPPORT", "SUPPORT"}

_STAT_KEYS = (
    "kills", "deaths", "assists", "totalMinionsKilled", "neutralMinionsKilled", "goldEarned",
    "totalDamageDealtToChampions", "totalDamageTaken", "visionScore", "wardsPlaced", "wardsKilled",
    "visionWardsBoughtInGame", "champLevel", "firstBloodKill", "firstBloodAssist",
    *(f"item{i}" for i in range(7)),
)


class LcuFormatError(ValueError):
    pass


def match_id(game: dict) -> str:
    platform = game.get("platformId") or "EUW1"
    return f"{platform}_{game['gameId']}"


def _first(d: dict, *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


def _position(participant: dict) -> str:
    for key in ("teamPosition", "individualPosition"):
        pos = participant.get(key) or participant.get("stats", {}).get(key)
        if pos in POSITIONS:
            return pos
    timeline = participant.get("timeline") or {}
    lane = _LANES.get(str(timeline.get("lane", "")).upper(), "")
    if lane == "BOTTOM" and str(timeline.get("role", "")).upper() in _SUPPORT_ROLES:
        return "UTILITY"
    return lane  # "" -> Parser ergänzt per Smite/Reihenfolge


def _win(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"win", "true"}
    return bool(value)


def convert_game(game: dict) -> dict:
    """LCU-Spiel -> match-v5-Dokument (``metadata`` + ``info``)."""
    try:
        identities = {pi["participantId"]: pi.get("player") or {} for pi in game["participantIdentities"]}
        raw_participants = game["participants"]
        raw_teams = game["teams"]
        game_id = game["gameId"]
    except (KeyError, TypeError) as exc:
        raise LcuFormatError(f"Unerwartetes LCU-Format: {exc!r}") from None

    team_win = {t["teamId"]: _win(t.get("win")) for t in raw_teams}
    participants = []
    for p in raw_participants:
        stats = p.get("stats") or {}
        player = identities.get(p["participantId"], {})
        team_id = p["teamId"]
        participants.append({
            "participantId": p["participantId"],
            "puuid": player.get("puuid") or f"unknown-{game_id}-{p['participantId']}",
            "riotIdGameName": player.get("gameName") or player.get("summonerName") or "?",
            "riotIdTagline": player.get("tagLine") or "",
            "championId": p.get("championId", 0),
            "teamId": team_id,
            "teamPosition": _position(p),
            "win": _win(stats["win"]) if "win" in stats else team_win.get(team_id, False),
            "summoner1Id": p.get("spell1Id", 0),
            "summoner2Id": p.get("spell2Id", 0),
            **{key: stats.get(key, 0) for key in _STAT_KEYS},
        })

    teams = []
    for t in raw_teams:
        team_id = t["teamId"]
        kills = sum(p["kills"] for p in participants if p["teamId"] == team_id)

        def obj(first_keys: tuple[str, ...], kill_keys: tuple[str, ...], _t=t) -> dict:
            return {"first": bool(_first(_t, *first_keys, default=False)), "kills": int(_first(_t, *kill_keys))}

        teams.append({
            "teamId": team_id,
            "win": team_win[team_id],
            "bans": [{"championId": b.get("championId", -1), "pickTurn": b.get("pickTurn", i + 1)}
                     for i, b in enumerate(t.get("bans") or [])],
            "objectives": {
                "champion": {"first": bool(t.get("firstBlood")), "kills": kills},
                "tower": obj(("firstTower",), ("towerKills",)),
                "inhibitor": obj(("firstInhibitor",), ("inhibitorKills",)),
                # der Client schreibt tatsächlich "firstDargon"
                "dragon": obj(("firstDragon", "firstDargon"), ("dragonKills",)),
                "baron": obj(("firstBaron",), ("baronKills",)),
                "riftHerald": obj(("firstRiftHerald",), ("riftHeraldKills",)),
                "horde": obj(("firstHorde",), ("hordeKills", "voidGrubKills")),
                "atakhan": obj(("firstAtakhan",), ("atakhanKills",)),
            },
        })

    duration = int(game.get("gameDuration", 0))
    if duration > 20_000:  # Millisekunden
        duration //= 1000
    info = {
        "gameCreation": game.get("gameCreation", 0),
        "gameDuration": duration,
        "gameEndTimestamp": game.get("gameCreation", 0) + duration * 1000,
        "gameMode": game.get("gameMode", ""),
        "gameType": game.get("gameType", "CUSTOM_GAME"),
        "gameVersion": game.get("gameVersion", ""),
        "mapId": game.get("mapId", 11),
        "platformId": game.get("platformId", "EUW1"),
        "queueId": game.get("queueId", 0),
        "participants": participants,
        "teams": teams,
    }
    if game.get("tournamentCode"):
        info["tournamentCode"] = game["tournamentCode"]
    return {
        "metadata": {"matchId": match_id(game), "participants": [p["puuid"] for p in participants],
                     "source": "lcu"},
        "info": info,
    }


def convert_timeline(timeline: dict, match: dict) -> dict:
    """LCU-Timeline -> match-v5-Timeline (Frames bleiben weitgehend gleich)."""
    frames = timeline.get("frames")
    if not isinstance(frames, list):
        raise LcuFormatError("Timeline ohne Frames.")
    return {
        "metadata": {"matchId": match["metadata"]["matchId"], "source": "lcu"},
        "info": {
            "frameInterval": timeline.get("frameInterval", 60000),
            "frames": frames,
            "participants": [{"participantId": p["participantId"], "puuid": p["puuid"]}
                             for p in match["info"]["participants"]],
        },
    }


def accounts(match: dict) -> list[dict]:
    """Riot-IDs aller Teilnehmer (für die Spielersuche ohne API-Key)."""
    return [{"puuid": p["puuid"], "gameName": p["riotIdGameName"], "tagLine": p["riotIdTagline"]}
            for p in match["info"]["participants"]
            if p["riotIdTagline"] and not p["puuid"].startswith("unknown-")]
