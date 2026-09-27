"""Einordnung von Kills: Teamfight, Dive, Skirmish, Gank, Roam, 1v1 (Bot: 2v2), Jungle 1v1.

Geprüft wird in dieser Reihenfolge; die erste zutreffende Kategorie gilt:

1. ``teamfight`` – Teil einer Kette von mindestens 3 Kills (beider Teams), jeweils höchstens 20 s und
   2 500 Einheiten auseinander
2. ``dive`` – in Reichweite eines noch stehenden Turms des Opfers
3. ``skirmish`` – mindestens 3 Angreifer (Killer + Assists)
4. ``gank`` (Jungler der Angreifer beteiligt) bzw. ``roam`` (Laner einer anderen Lane)
5. ``lane`` – nur die direkten Lane-Gegner (Bot + Support zählen als eine Lane → 2v2);
   ``duel`` – Jungler gegen Jungler
6. ``other`` – ohne gegnerischen Champion (Turm, Minions)
"""

from __future__ import annotations

import math

from .matches import MatchSummary

TEAMFIGHT_KILLS = 3
TEAMFIGHT_SECONDS = 20
TEAMFIGHT_RANGE = 2500
DIVE_RANGE = 900
SKIRMISH_ATTACKERS = 3

#: Türme der blauen Seite (Spielkoordinaten); die roten sind die Punktspiegelung
_BLUE_TOWERS = [
    (981, 10441), (1512, 6699), (1169, 4287),       # Top: außen, innen, Inhib
    (5846, 6396), (5048, 4812), (3651, 3696),       # Mid
    (10504, 1029), (6919, 1483), (4281, 1253),      # Bot
    (1748, 2270), (2177, 1807),                     # Nexus
]
TOWERS = {100: _BLUE_TOWERS, 200: [(14870 - x, 14980 - y) for x, y in _BLUE_TOWERS]}


def _lane(position: str) -> str:
    return {"TOP": "top", "MIDDLE": "mid", "BOTTOM": "bot", "UTILITY": "bot", "JUNGLE": "jungle"}.get(position, "")


def base_kind(victim_position: str, attacker_positions: list[str]) -> str:
    """Gank/Roam/1v1 nur nach den beteiligten Rollen (ohne Teamfight, Dive, Skirmish)."""
    lanes = [_lane(p) for p in attacker_positions]
    if not [lane for lane in lanes if lane]:
        return "other"
    own = _lane(victim_position)
    if own == "jungle":
        return "roam" if any(lane not in ("jungle", "") for lane in lanes) else "duel"
    if "jungle" in lanes:
        return "gank"
    return "roam" if any(lane not in ("jungle", "", own) for lane in lanes) else "lane"


def teamfight_kills(kills: list[dict]) -> set[int]:
    """Indizes der Kills, die zu einer Teamfight-Kette gehören."""
    order = sorted(range(len(kills)), key=lambda i: kills[i]["t"])
    parent = list(range(len(kills)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for n, i in enumerate(order):
        for j in order[n + 1:]:
            if kills[j]["t"] - kills[i]["t"] > TEAMFIGHT_SECONDS:
                break
            if math.hypot(kills[j]["x"] - kills[i]["x"], kills[j]["y"] - kills[i]["y"]) <= TEAMFIGHT_RANGE:
                parent[find(j)] = find(i)
    sizes: dict[int, int] = {}
    for i in range(len(kills)):
        sizes[find(i)] = sizes.get(find(i), 0) + 1
    return {i for i in range(len(kills)) if sizes[find(i)] >= TEAMFIGHT_KILLS}


def tower_standing(team: int, x: int, y: int, t: int, lost: list[dict]) -> bool:
    """Steht ein Turm von ``team`` in Dive-Reichweite von (x, y) zum Zeitpunkt t?"""
    for tx, ty in TOWERS.get(team, []):
        if math.hypot(tx - x, ty - y) > DIVE_RANGE:
            continue
        destroyed = any(d["team"] == team and d["t"] <= t and math.hypot(d["x"] - tx, d["y"] - ty) < 600
                        for d in lost)
        if not destroyed:
            return True
    return False


def classify_kills(match: MatchSummary, timeline: dict) -> list[str]:
    """Kategorie für jeden Kill der Timeline (gleiche Reihenfolge wie ``timeline["kills"]``)."""
    kills = timeline.get("kills", [])
    by_pid = {p.participant_id: p for p in match.participants}
    fights = teamfight_kills(kills)
    lost = timeline.get("towers", [])
    kinds = []
    for i, k in enumerate(kills):
        victim = by_pid.get(k["victim"])
        attackers = [by_pid[pid] for pid in dict.fromkeys([k["killer"], *k["assists"]])
                     if pid in by_pid and victim is not None and by_pid[pid].team_id != victim.team_id]
        if victim is None or not attackers:
            kinds.append("other")
        elif i in fights:
            kinds.append("teamfight")
        elif tower_standing(victim.team_id, k["x"], k["y"], k["t"], lost):
            kinds.append("dive")
        elif len(attackers) >= SKIRMISH_ATTACKERS:
            kinds.append("skirmish")
        else:
            kinds.append(base_kind(victim.position, [a.position for a in attackers]))
    return kinds
