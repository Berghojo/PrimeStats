"""Auswertung für einen einzelnen Spieler über Solo/Duo, Flex, Turnier und Scrims."""

from __future__ import annotations

from collections import Counter

from .team_stats import GameRecord, _deaths, _kills
from .timeline import at, player_series

#: Queues der Einzelansicht: Schlüssel -> Abfrage an die Riot-API (Scrims kommen vom Uploader)
QUEUES: dict[str, dict] = {"solo": {"queue": 420}, "flex": {"queue": 440}, "tourney": {"type": "tourney"}}
QUEUE_KEYS = ("solo", "flex", "tourney", "scrim")


def _avg(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def filter_player_records(records: list[GameRecord], puuid: str, *, queues: set[str] | None = None, patch: str = "",
                          last: int = 0, champion: int = 0, role: str = "",
                          exclude: set[str] | None = None) -> list[GameRecord]:
    out = [r for r in records if not queues or r.label in queues]
    if patch:
        out = [r for r in out if r.match.version == patch]
    if champion:
        out = [r for r in out if (p := r.match.player(puuid)) and p.champion_id == champion]
    if role:
        out = [r for r in out if (p := r.match.player(puuid)) and p.position == role]
    out.sort(key=lambda r: r.match.created, reverse=True)
    out = out[:last] if last > 0 else out
    return [r for r in out if r.match.match_id not in exclude] if exclude else out


def history_row(rec: GameRecord, puuid: str) -> dict | None:
    """Alle Match-Historien-Daten eines Spiels aus Sicht des Spielers."""
    m, p = rec.match, rec.match.player(puuid)
    if p is None:
        return None
    series = player_series(rec.timeline, m, puuid) if rec.timeline else {}
    return {
        "match_id": m.match_id, "date": m.created, "queue": rec.label, "champion_id": p.champion_id,
        "position": p.position, "win": p.win, "kills": p.kills, "deaths": p.deaths, "assists": p.assists,
        "cs": p.cs, "duration": m.duration, "gd15": at(series.get("gold_diff"), 15) if series else None,
        "csd15": at(series.get("cs_diff"), 15) if series else None,
        "patch": m.version, "side": rec.us.side, "level": p.level, "gold": p.gold, "damage": p.damage,
        "vision": p.vision_score, "kp": (p.kills + p.assists) / rec.us.kills if rec.us.kills else None,
        "items": list(p.items), "spells": list(p.spells),
        "participants": [{"puuid": q.puuid, "name": q.name, "tag": q.tag, "team_id": q.team_id,
                          "position": q.position, "champion_id": q.champion_id, "kills": q.kills,
                          "deaths": q.deaths, "assists": q.assists}
                         for team_id in sorted(m.teams) for q in m.teams[team_id].players],
    }


def player_history(puuid: str, records: list[GameRecord], excluded: set[str]) -> list[dict]:
    rows = []
    for rec in sorted(records, key=lambda r: r.match.created, reverse=True):
        row = history_row(rec, puuid)
        if row:
            rows.append({**row, "excluded": rec.match.match_id in excluded})
    return rows


def build_player_report(puuid: str, records: list[GameRecord]) -> dict:
    """Kennzahlen, Champions, Rollen, Queues, Kills/Tode und Spieleliste eines Spielers."""
    games = []
    for rec in records:
        p = rec.match.player(puuid)
        if p is not None:
            games.append((rec, p))
    n = len(games)
    totals = Counter()
    gd10, gd15, csd15, xpd15 = [], [], [], []
    champs: dict[int, dict] = {}
    roles: dict[str, dict] = {}
    queues: dict[str, dict] = {}
    history = []
    deaths_all: list[dict] = []
    kills_all: list[dict] = []
    for rec, p in games:
        m = rec.match
        team_kills = rec.us.kills
        for key, value in (("wins", p.win), ("kills", p.kills), ("deaths", p.deaths), ("assists", p.assists),
                           ("cs", p.cs), ("gold", p.gold), ("damage", p.damage), ("vision", p.vision_score),
                           ("team_kills", team_kills), ("first_blood", p.first_blood)):
            totals[key] += value
        totals["minutes"] += m.minutes
        series = player_series(rec.timeline, m, puuid) if rec.timeline else {}
        g15 = at(series.get("gold_diff"), 15) if series else None
        if series:
            gd10.append(at(series["gold_diff"], 10))
            gd15.append(g15)
            csd15.append(at(series["cs_diff"], 15))
            xpd15.append(at(series["xp_diff"], 15))
        c = champs.setdefault(p.champion_id, {"champion_id": p.champion_id, "games": 0, "wins": 0, "kills": 0,
                                              "deaths": 0, "assists": 0, "cs": 0, "damage": 0, "minutes": 0.0,
                                              "positions": Counter()})
        for key, value in (("games", 1), ("wins", p.win), ("kills", p.kills), ("deaths", p.deaths),
                           ("assists", p.assists), ("cs", p.cs), ("damage", p.damage), ("minutes", m.minutes)):
            c[key] += value
        c["positions"][p.position] += 1
        for bucket, key in ((roles, p.position), (queues, rec.label)):
            b = bucket.setdefault(key, {"key": key, "games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0})
            for k2, v in (("games", 1), ("wins", p.win), ("kills", p.kills), ("deaths", p.deaths), ("assists", p.assists)):
                b[k2] += v
        history.append({
            "match_id": m.match_id, "date": m.created, "queue": rec.label, "champion_id": p.champion_id,
            "position": p.position, "win": p.win, "kills": p.kills, "deaths": p.deaths, "assists": p.assists,
            "cs": p.cs, "duration": m.duration, "gd15": g15,
        })
        if rec.timeline:
            d_list: list[dict] = []
            k_list: list[dict] = []
            _deaths(rec, d_list)
            _kills(rec, k_list)
            deaths_all += [d for d in d_list if d["puuid"] == puuid]
            kills_all += [k for k in k_list if any(b["puuid"] == puuid for b in k["by"])]

    def rate(a, b):
        return a / b if b else None

    minutes = totals["minutes"] or 1
    overview = {
        "games": n, "wins": totals["wins"], "winrate": rate(totals["wins"], n),
        "kills": rate(totals["kills"], n), "deaths": rate(totals["deaths"], n), "assists": rate(totals["assists"], n),
        "kda": (totals["kills"] + totals["assists"]) / max(totals["deaths"], 1) if n else None,
        "cspm": totals["cs"] / minutes if n else None, "gpm": totals["gold"] / minutes if n else None,
        "dpm": totals["damage"] / minutes if n else None, "vspm": totals["vision"] / minutes if n else None,
        "kp": rate(totals["kills"] + totals["assists"], totals["team_kills"]),
        "first_blood": rate(totals["first_blood"], n),
        "gd10": _avg(gd10), "gd15": _avg(gd15), "csd15": _avg(csd15), "xpd15": _avg(xpd15),
        "timeline_games": len([g for g in gd15 if g is not None]),
    }

    def finish(b: dict) -> dict:
        return {**b, "winrate": b["wins"] / b["games"], "kda": (b["kills"] + b["assists"]) / max(b["deaths"], 1)}

    champion_rows = []
    for c in sorted(champs.values(), key=lambda c: (-c["games"], -c["wins"])):
        row = finish(c)
        row["cspm"] = c["cs"] / max(c["minutes"], 1 / 60)
        row["dpm"] = c["damage"] / max(c["minutes"], 1 / 60)
        row["positions"] = [pos for pos, _ in c["positions"].most_common()]
        del row["minutes"], row["cs"], row["damage"]
        champion_rows.append(row)

    name = games[0][1].name if games else ""
    tag = games[0][1].tag if games else ""
    return {
        "puuid": puuid, "name": name, "tag": tag,
        "overview": overview,
        "champions": champion_rows,
        "roles": sorted((finish(r) for r in roles.values()), key=lambda r: -r["games"]),
        "queues": [finish(queues[k]) for k in QUEUE_KEYS if k in queues],
        "history": history,
        "deaths": deaths_all,
        "kills": kills_all,
    }
