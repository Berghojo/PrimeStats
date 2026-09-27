"""Auswertung der match-v5-Timeline (Minutenwerte pro Spieler)."""

from __future__ import annotations

import math
from collections import defaultdict

from .matches import MatchSummary

#: Bei Änderungen am Format der Zusammenfassung erhöhen -> Cache wird neu berechnet
SUMMARY_VERSION = 3

RAW_SERIES = ("gold", "current_gold", "xp", "level", "cs", "jcs", "dmg", "dmg_taken", "kills", "deaths", "assists")

#: Werte, die auf der Analyse-Seite ausgewählt werden können
STATS: list[tuple[str, str]] = [
    ("gold", "Gold gesamt"),
    ("gold_diff", "Golddifferenz zum Lanegegner"),
    ("xp", "Erfahrung"),
    ("xp_diff", "XP-Differenz zum Lanegegner"),
    ("cs", "CS"),
    ("cs_diff", "CS-Differenz zum Lanegegner"),
    ("level", "Level"),
    ("dmg", "Schaden an Champions"),
    ("dmg_taken", "Erlittener Schaden"),
    ("current_gold", "Ungenutztes Gold"),
    ("kills", "Kills"),
    ("deaths", "Tode"),
    ("assists", "Assists"),
    ("kp", "Kill-Beteiligung (%)"),
]

MONSTERS = {
    "DRAGON": "Drache",
    "HORDE": "Grubs",
    "RIFTHERALD": "Herald",
    "BARON_NASHOR": "Baron",
    "ATAKHAN": "Atakhan",
    "ELDER_DRAGON": "Elder",
}


def summarize_timeline(timeline: dict, match: MatchSummary) -> dict:
    """Verdichtet die (große) Timeline auf Minutenreihen pro Spieler + Objectives."""
    info = timeline["info"]
    frames = info["frames"]
    pid_to_puuid = {int(p["participantId"]): p["puuid"] for p in info.get("participants", [])}
    team_of = {p.participant_id: p.team_id for p in match.participants}
    if not pid_to_puuid:
        pid_to_puuid = {p.participant_id: p.puuid for p in match.participants}

    events = sorted((e for f in frames for e in f.get("events", [])), key=lambda e: e.get("timestamp", 0))
    players: dict[str, dict] = {}
    for pid, puuid in pid_to_puuid.items():
        players[puuid] = {"pid": pid, "team": team_of.get(pid, 100 if pid <= 5 else 200),
                          **{k: [] for k in RAW_SERIES}, "path": []}

    kda = {pid: [0, 0, 0] for pid in pid_to_puuid}
    ev_idx = 0
    for frame in frames:
        ts = frame.get("timestamp", 0)
        while ev_idx < len(events) and events[ev_idx].get("timestamp", 0) <= ts:
            e = events[ev_idx]
            ev_idx += 1
            if e.get("type") != "CHAMPION_KILL":
                continue
            killer, victim = e.get("killerId", 0), e.get("victimId", 0)
            if killer in kda:
                kda[killer][0] += 1
            if victim in kda:
                kda[victim][1] += 1
            for helper in e.get("assistingParticipantIds") or []:
                if helper in kda:
                    kda[helper][2] += 1
        for pid, puuid in pid_to_puuid.items():
            pf = frame["participantFrames"].get(str(pid), {})
            dmg = pf.get("damageStats") or {}
            row = players[puuid]
            row["gold"].append(pf.get("totalGold", 0))
            row["current_gold"].append(pf.get("currentGold", 0))
            row["xp"].append(pf.get("xp", 0))
            row["level"].append(pf.get("level", 1))
            row["cs"].append(pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0))
            row["jcs"].append(pf.get("jungleMinionsKilled", 0))
            row["dmg"].append(dmg.get("totalDamageDoneToChampions", 0))
            row["dmg_taken"].append(dmg.get("totalDamageTaken", 0))
            row["kills"].append(kda[pid][0])
            row["deaths"].append(kda[pid][1])
            row["assists"].append(kda[pid][2])
            pos = pf.get("position") or {}
            row["path"].append([int(pos["x"]), int(pos["y"])] if "x" in pos and "y" in pos else None)

    kills = []
    for e in events:
        pos = e.get("position") or {}
        if e.get("type") == "CHAMPION_KILL" and "x" in pos and "y" in pos:
            kills.append({"t": round(e.get("timestamp", 0) / 1000), "x": int(pos["x"]), "y": int(pos["y"]),
                          "killer": e.get("killerId", 0), "victim": e.get("victimId", 0),
                          "assists": list(e.get("assistingParticipantIds") or [])})

    objectives = []
    first_blood = None
    for e in events:
        if e.get("type") == "ELITE_MONSTER_KILL":
            monster = e.get("monsterType", "")
            if monster == "DRAGON" and e.get("monsterSubType") == "ELDER_DRAGON":
                monster = "ELDER_DRAGON"
            team = e.get("killerTeamId") or team_of.get(e.get("killerId", 0))
            objectives.append({"t": round(e.get("timestamp", 0) / 60000, 2), "team": team, "type": monster})
        elif e.get("type") == "CHAMPION_KILL" and first_blood is None:
            victim_team = team_of.get(e.get("victimId", 0))
            if victim_team:
                first_blood = {"t": round(e.get("timestamp", 0) / 60000, 2),
                               "team": 200 if victim_team == 100 else 100}
    return {"minutes": len(frames), "players": players, "objectives": objectives, "first_blood": first_blood,
            "kills": kills}


def at(series: list | None, minute: int):
    if not series or minute >= len(series):
        return None
    return series[minute]


def player_series(summary: dict, match: MatchSummary, puuid: str) -> dict[str, list]:
    """Alle STATS-Reihen eines Spielers in einem Match (inkl. Lane-Differenzen und KP)."""
    me = summary["players"].get(puuid)
    if me is None:
        return {}
    out = {k: list(me[k]) for k in RAW_SERIES}
    player = match.player(puuid)
    opp = match.opponent(player) if player else None
    opp_series = summary["players"].get(opp.puuid) if opp else None
    for stat, base in (("gold_diff", "gold"), ("xp_diff", "xp"), ("cs_diff", "cs")):
        if opp_series:
            out[stat] = [a - b for a, b in zip(me[base], opp_series[base])]
        else:
            out[stat] = [None] * len(me[base])
    mates = [p for p in summary["players"].values() if p["team"] == me["team"]]
    team_kills = [sum(p["kills"][i] for p in mates) for i in range(len(me["kills"]))]
    out["kp"] = [round(100 * (k + a) / tk, 1) if tk else 0
                 for k, a, tk in zip(me["kills"], me["assists"], team_kills)]
    return out


def team_series(summary: dict, team_id: int, key: str = "gold") -> list[int]:
    """Differenz (eigenes Team − Gegner) eines Rohwerts pro Minute."""
    length = summary["minutes"]
    diff = [0] * length
    for p in summary["players"].values():
        sign = 1 if p["team"] == team_id else -1
        for i, v in enumerate(p[key][:length]):
            diff[i] += sign * v
    return diff


def average_series(rows: list[list], min_share: float = 0.0) -> tuple[list, list[int]]:
    """Mittelt Reihen unterschiedlicher Länge minutenweise; liefert auch die Stichprobengröße.

    Mit ``min_share`` wird die Reihe abgeschnitten, sobald weniger als dieser Anteil der Spiele
    noch läuft – sonst verzerren die wenigen langen Spiele das Ende der Kurve.
    """
    length = max((len(r) for r in rows), default=0)
    sums = [0.0] * length
    counts = [0] * length
    for row in rows:
        for i, v in enumerate(row):
            if v is not None:
                sums[i] += v
                counts[i] += 1
    # mindestens zwei Spiele pro Minute (sofern vorhanden), sonst dominiert ein einzelnes langes Spiel
    needed = max(min(2, len(rows)) if min_share else 1, math.ceil(len(rows) * min_share))
    while counts and counts[-1] < needed:
        counts.pop()
        sums.pop()
    return [round(s / c, 1) if c else None for s, c in zip(sums, counts)], counts


def analysis_payload(items: list[tuple[MatchSummary, dict]], focus: set[str] | None = None) -> dict:
    """Daten für die Diagrammseite: pro Spieler über alle gewählten Spiele gemittelte Reihen."""
    per_player: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    meta: dict[str, dict] = {}
    for match, summary in sorted(items, key=lambda it: it[0].created):
        for p in match.participants:
            series = player_series(summary, match, p.puuid)
            if not series:
                continue
            for stat, values in series.items():
                per_player[p.puuid][stat].append(values)
            m = meta.setdefault(p.puuid, {"puuid": p.puuid, "games": 0, "positions": {}})
            m["name"] = p.name
            m["games"] += 1
            m["positions"][p.position] = m["positions"].get(p.position, 0) + 1
    players = []
    series: dict[str, dict[str, list]] = {stat: {} for stat, _ in STATS}
    for puuid, stats in per_player.items():
        m = meta[puuid]
        m["position"] = max(m.pop("positions").items(), key=lambda kv: kv[1])[0]
        m["focus"] = bool(focus and puuid in focus)
        players.append(m)
        for stat, _ in STATS:
            series[stat][puuid] = average_series(stats[stat], min_share=0.5)[0]
    players.sort(key=lambda m: (not m["focus"], -m["games"], m["name"].lower()))
    minutes = max((len(v) for s in series.values() for v in s.values()), default=0)
    return {"stats": [{"key": k, "label": label} for k, label in STATS], "players": players,
            "series": series, "minutes": minutes}
