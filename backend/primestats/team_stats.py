"""Aggregation von Custom-Game-Statistiken für ein Team."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .matches import POSITIONS, MatchSummary
from .store import Team
from .timeline import MONSTERS, at, average_series, player_series, team_series

LABELS = {"official": "Prime League", "scrim": "Scrim", "": "Ohne Label"}


@dataclass
class GameRecord:
    match: MatchSummary
    side: int                       # teamId des eigenen Teams
    label: str = ""
    included: bool = True
    timeline: dict | None = None    # Ergebnis von timeline.summarize_timeline
    opponent: str = ""              # von Hand eingetragener Gegner (eigene Teamansicht)

    @property
    def us(self):
        return self.match.teams[self.side]

    @property
    def them(self):
        return self.match.enemy_of(self.side)

    @property
    def win(self) -> bool:
        return self.us.win


def _rate(part: float, total: float) -> float | None:
    return part / total if total else None


def _avg(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


@dataclass
class _PlayerAcc:
    puuid: str
    name: str = ""
    member: bool = False
    games: int = 0
    wins: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    gold: int = 0
    damage: int = 0
    damage_taken: int = 0
    vision: int = 0
    wards: int = 0
    wards_killed: int = 0
    control_wards: int = 0
    minutes: float = 0.0
    team_kills: int = 0
    team_damage: int = 0
    team_gold: int = 0
    first_bloods: int = 0
    positions: Counter = field(default_factory=Counter)
    champions: dict = field(default_factory=dict)
    gd10: list = field(default_factory=list)
    gd15: list = field(default_factory=list)
    csd15: list = field(default_factory=list)
    xpd15: list = field(default_factory=list)

    def finish(self) -> dict:
        g = self.games
        champs = sorted(self.champions.values(), key=lambda c: (-c["games"], -c["wins"]))
        for c in champs:
            c["winrate"] = c["wins"] / c["games"]
            c["kda"] = (c["kills"] + c["assists"]) / max(c["deaths"], 1)
        return {
            "puuid": self.puuid,
            "name": self.name,
            "member": self.member,
            "position": self.positions.most_common(1)[0][0] if self.positions else "",
            "games": g,
            "wins": self.wins,
            "winrate": self.wins / g,
            "kills": self.kills / g,
            "deaths": self.deaths / g,
            "assists": self.assists / g,
            "kda": (self.kills + self.assists) / max(self.deaths, 1),
            "cspm": self.cs / self.minutes,
            "gpm": self.gold / self.minutes,
            "dpm": self.damage / self.minutes,
            "dtpm": self.damage_taken / self.minutes,
            "vspm": self.vision / self.minutes,
            "wards": self.wards / g,
            "wards_killed": self.wards_killed / g,
            "control_wards": self.control_wards / g,
            "kp": _rate(self.kills + self.assists, self.team_kills),
            "damage_share": _rate(self.damage, self.team_damage),
            "gold_share": _rate(self.gold, self.team_gold),
            "first_blood": self.first_bloods / g,
            "gd10": _avg(self.gd10),
            "gd15": _avg(self.gd15),
            "csd15": _avg(self.csd15),
            "xpd15": _avg(self.xpd15),
            "champions": champs,
        }


#: So viele Minuten Pathing werden je Spiel übernommen
PATH_MINUTES = 15


def _jungle(rec: GameRecord, players: dict, paths: list, events: list) -> None:
    """Pathing und Kill-Beteiligung des eigenen Junglers in einem Spiel (braucht die Timeline)."""
    tl, us, match = rec.timeline, rec.us, rec.match
    jungler = next((p for p in us.players if p.position == "JUNGLE"), None)
    row = tl["players"].get(jungler.puuid) if (jungler and tl) else None
    if row is None:
        return
    pid = row["pid"]
    acc = players.setdefault(jungler.puuid, {"puuid": jungler.puuid, "name": jungler.name, "games": 0})
    acc["games"] += 1
    base = {"match_id": match.match_id, "win": rec.win, "side": us.side, "puuid": jungler.puuid}
    points = (row.get("path") or [])[:PATH_MINUTES + 1]
    if any(points):
        paths.append({**base, "date": match.created, "champion_id": jungler.champion_id, "points": points,
                      "jungle_cs": list(row.get("jcs") or [])[:PATH_MINUTES + 1]})
    for k in tl.get("kills", []):
        kind = ("kill" if k["killer"] == pid else "assist" if pid in k["assists"]
                else "death" if k["victim"] == pid else None)
        if kind:
            events.append({**base, "type": kind, "t": k["t"], "x": k["x"], "y": k["y"]})


def _lane(position: str) -> str:
    return {"TOP": "top", "MIDDLE": "mid", "BOTTOM": "bot", "UTILITY": "bot", "JUNGLE": "jungle"}.get(position, "")


def death_kind(victim_position: str, enemy_positions: list[str]) -> str:
    """Einordnung eines Todes nach den beteiligten Gegnern.

    Laner: "gank" (gegnerischer Jungler dabei), "roam" (Laner einer anderen Lane dabei), "gank_roam"
    (beides) oder "lane" (nur die direkten Lane-Gegner). Jungler: "roam" (ein gegnerischer Laner dabei)
    oder "duel" (nur der gegnerische Jungler). Ohne beteiligte Champions (Turm, Minions …): "other".
    """
    lanes = [_lane(p) for p in enemy_positions]
    if not [lane for lane in lanes if lane]:
        return "other"
    own = _lane(victim_position)
    if own == "jungle":
        return "roam" if any(lane not in ("jungle", "") for lane in lanes) else "duel"
    gank = "jungle" in lanes
    roam = any(lane not in ("jungle", "", own) for lane in lanes)
    return "gank_roam" if gank and roam else "gank" if gank else "roam" if roam else "lane"


def _deaths(rec: GameRecord, out: list) -> None:
    """Alle Tode der eigenen Spieler mit Ort, Zeit und beteiligten Gegnern (braucht die Timeline)."""
    tl, match = rec.timeline, rec.match
    by_pid = {p.participant_id: p for p in match.participants}
    ours = {p.participant_id for p in rec.us.players}
    for k in (tl or {}).get("kills", []):
        victim = by_pid.get(k["victim"])
        if victim is None or victim.participant_id not in ours:
            continue
        enemies = [by_pid[pid] for pid in dict.fromkeys([k["killer"], *k["assists"]])
                   if pid in by_pid and pid not in ours]
        out.append({
            "match_id": match.match_id, "date": match.created, "win": rec.win, "side": rec.us.side,
            "puuid": victim.puuid, "name": victim.name, "position": victim.position,
            "champion_id": victim.champion_id, "t": k["t"], "x": k["x"], "y": k["y"],
            "kind": death_kind(victim.position, [e.position for e in enemies]),
            "by": [{"position": e.position, "champion_id": e.champion_id, "name": e.name,
                    "killer": e.participant_id == k["killer"]} for e in enemies],
        })


def build_report(team: Team, records: list[GameRecord]) -> dict:
    """Berechnet alle Kennzahlen für die übergebenen (bereits gefilterten) Spiele."""
    records = sorted(records, key=lambda r: r.match.created)
    roster = {m.puuid: m for m in team.members}
    n = len(records)

    players: dict[str, _PlayerAcc] = {}
    picks: dict[int, dict] = {}
    champ_stats: dict[int, dict] = {}   # Champion-Pick-Tabelle (eigene Picks)
    enemy_picks: dict[int, dict] = {}
    our_bans: Counter = Counter()
    enemy_bans: Counter = Counter()
    monsters = {key: {"us": 0, "them": 0, "first": 0, "first_times": []} for key in MONSTERS}
    gold_curves: dict[str, list] = {"all": [], "win": [], "loss": []}
    trend = []
    jungle_players: dict[str, dict] = {}
    jungle_paths: list[dict] = []
    jungle_events: list[dict] = []
    deaths: list[dict] = []

    ov = Counter()
    durations = {"win": [], "loss": []}
    gd10_team, gd15_team = [], []

    for rec in records:
        us, them, match = rec.us, rec.them, rec.match
        ov["wins"] += rec.win
        ov[f"{us.side}_games"] += 1
        ov[f"{us.side}_wins"] += rec.win
        ov["kills"] += us.kills
        ov["deaths"] += them.kills
        ov["towers"] += us.towers
        ov["towers_lost"] += them.towers
        for obj in ("first_blood", "first_tower", "first_dragon", "first_herald", "first_grubs", "first_baron"):
            ov[obj] += getattr(us, obj)
        for key, attr in (("DRAGON", "dragons"), ("HORDE", "grubs"), ("RIFTHERALD", "heralds"),
                          ("BARON_NASHOR", "barons"), ("ATAKHAN", "atakhan")):
            monsters[key]["us"] += getattr(us, attr)
            monsters[key]["them"] += getattr(them, attr)
        durations["win" if rec.win else "loss"].append(match.duration)

        for cid in us.bans:
            our_bans[cid] += 1
        for cid in them.bans:
            enemy_bans[cid] += 1
        for p in them.players:
            e = enemy_picks.setdefault(p.champion_id, {"champion_id": p.champion_id, "games": 0, "wins": 0})
            e["games"] += 1
            e["wins"] += rec.win  # unsere Siege gegen diesen Champion

        tl = rec.timeline
        gd = None
        if tl:
            curve = team_series(tl, rec.side, "gold")
            gold_curves["all"].append(curve)
            gold_curves["win" if rec.win else "loss"].append(curve)
            gd10_team.append(at(curve, 10))
            gd = at(curve, 15)
            gd15_team.append(gd)
            firsts: dict[str, dict] = {}
            for ev in tl.get("objectives", []):
                firsts.setdefault(ev["type"], ev)
                if ev["type"] == "ELDER_DRAGON":
                    monsters["ELDER_DRAGON"]["us" if ev["team"] == rec.side else "them"] += 1
            for key, ev in firsts.items():
                if key in monsters and ev["team"] == rec.side:
                    monsters[key]["first_times"].append(ev["t"])
            _jungle(rec, jungle_players, jungle_paths, jungle_events)
            _deaths(rec, deaths)

        trend.append({"match_id": match.match_id, "date": match.created, "win": rec.win,
                      "gd15": gd, "kills": us.kills, "deaths": them.kills})

        team_gold = us.gold
        team_damage = us.damage
        for p in us.players:
            acc = players.get(p.puuid)
            if acc is None:
                acc = players[p.puuid] = _PlayerAcc(p.puuid, member=p.puuid in roster)
            acc.name = p.name
            acc.games += 1
            acc.wins += p.win
            acc.kills += p.kills
            acc.deaths += p.deaths
            acc.assists += p.assists
            acc.cs += p.cs
            acc.gold += p.gold
            acc.damage += p.damage
            acc.damage_taken += p.damage_taken
            acc.vision += p.vision_score
            acc.wards += p.wards_placed
            acc.wards_killed += p.wards_killed
            acc.control_wards += p.control_wards
            acc.minutes += match.minutes
            acc.team_kills += us.kills
            acc.team_damage += team_damage
            acc.team_gold += team_gold
            acc.first_bloods += p.first_blood
            acc.positions[p.position] += 1
            c = acc.champions.setdefault(p.champion_id, {"champion_id": p.champion_id, "games": 0, "wins": 0,
                                                         "kills": 0, "deaths": 0, "assists": 0})
            c["games"] += 1
            c["wins"] += p.win
            c["kills"] += p.kills
            c["deaths"] += p.deaths
            c["assists"] += p.assists
            pk = picks.setdefault(p.champion_id, {"champion_id": p.champion_id, "games": 0, "wins": 0,
                                                  "players": Counter()})
            pk["games"] += 1
            pk["wins"] += p.win
            pk["players"][acc.name] += 1
            cs = champ_stats.setdefault(p.champion_id, {
                "picks": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "minutes": 0.0,
                "damage": 0, "positions": Counter(), "players": {}})
            cs["picks"] += 1
            cs["wins"] += p.win
            cs["kills"] += p.kills
            cs["deaths"] += p.deaths
            cs["assists"] += p.assists
            cs["cs"] += p.cs
            cs["damage"] += p.damage
            cs["minutes"] += match.minutes
            cs["positions"][p.position] += 1
            pl = cs["players"].setdefault(p.puuid, {"name": acc.name, "games": 0, "wins": 0})
            pl["name"] = acc.name
            pl["games"] += 1
            pl["wins"] += p.win
            if tl:
                s = player_series(tl, match, p.puuid)
                if s:
                    acc.gd10.append(at(s["gold_diff"], 10))
                    acc.gd15.append(at(s["gold_diff"], 15))
                    acc.csd15.append(at(s["cs_diff"], 15))
                    acc.xpd15.append(at(s["xp_diff"], 15))

    def pos_key(pl: dict):
        pos = pl["position"]
        return (not pl["member"], POSITIONS.index(pos) if pos in POSITIONS else 9, -pl["games"])

    player_rows = sorted((acc.finish() for acc in players.values()), key=pos_key)
    for pk in picks.values():
        pk["winrate"] = pk["wins"] / pk["games"]
        pk["players"] = [name for name, _ in pk["players"].most_common()]
    champion_table = []
    for cid in set(champ_stats) | set(our_bans) | set(enemy_bans):
        cs = champ_stats.get(cid)
        row = {"champion_id": cid, "picks": 0, "wins": 0, "winrate": None, "kda": None, "kills": None,
               "deaths": None, "assists": None, "cspm": None, "dpm": None, "position": "", "positions": [],
               "players": [],
               "bans_by_us": our_bans[cid], "bans_against": enemy_bans[cid]}
        if cs:
            g = cs["picks"]
            row.update(picks=g, wins=cs["wins"], winrate=cs["wins"] / g,
                       kda=(cs["kills"] + cs["assists"]) / max(cs["deaths"], 1),
                       kills=cs["kills"] / g, deaths=cs["deaths"] / g, assists=cs["assists"] / g,
                       cspm=cs["cs"] / cs["minutes"], dpm=cs["damage"] / cs["minutes"],
                       position=cs["positions"].most_common(1)[0][0],
                       # alle Rollen, auf denen der Champion gespielt wurde (eine Zeile pro Champion)
                       positions=[{"position": pos, "games": k} for pos, k in cs["positions"].most_common()],
                       players=sorted(cs["players"].values(), key=lambda x: -x["games"]))
        # Präsenz: Anteil der Spiele, in denen der Champion gepickt oder (von einer Seite) gebannt wurde
        row["presence"] = (row["picks"] + row["bans_by_us"] + row["bans_against"]) / n if n else None
        champion_table.append(row)
    champion_table.sort(key=lambda r: (-r["picks"], -(r["presence"] or 0)))
    for e in enemy_picks.values():
        e["winrate"] = e["wins"] / e["games"]

    for m in monsters.values():
        total = m["us"] + m["them"]
        m["share"] = _rate(m["us"], total)
        m["us_avg"] = m["us"] / n if n else 0
        m["them_avg"] = m["them"] / n if n else 0
        m["first_time"] = _avg(m.pop("first_times"))

    curves = {}
    for key, rows in gold_curves.items():
        values, counts = average_series(rows, min_share=0.25)
        curves[key] = {"values": values, "counts": counts}

    all_durations = durations["win"] + durations["loss"]
    overview = {
        "games": n,
        "wins": ov["wins"],
        "losses": n - ov["wins"],
        "winrate": _rate(ov["wins"], n),
        "blue_games": ov["blue_games"], "blue_wins": ov["blue_wins"],
        "blue_winrate": _rate(ov["blue_wins"], ov["blue_games"]),
        "red_games": ov["red_games"], "red_wins": ov["red_wins"],
        "red_winrate": _rate(ov["red_wins"], ov["red_games"]),
        "duration": _avg(all_durations),
        "duration_win": _avg(durations["win"]),
        "duration_loss": _avg(durations["loss"]),
        "kills": ov["kills"] / n if n else None,
        "deaths": ov["deaths"] / n if n else None,
        "towers": ov["towers"] / n if n else None,
        "towers_lost": ov["towers_lost"] / n if n else None,
        "gd10": _avg(gd10_team),
        "gd15": _avg(gd15_team),
        "timeline_games": len(gold_curves["all"]),
        **{obj: _rate(ov[obj], n) for obj in ("first_blood", "first_tower", "first_dragon",
                                                "first_herald", "first_grubs", "first_baron")},
    }
    return {
        "overview": overview,
        "players": player_rows,
        "picks": sorted(picks.values(), key=lambda p: (-p["games"], -p["wins"])),
        "champion_table": champion_table,
        "enemy_picks": sorted(enemy_picks.values(), key=lambda p: (-p["games"], p["wins"])),
        "our_bans": [{"champion_id": c, "count": k} for c, k in our_bans.most_common()],
        "enemy_bans": [{"champion_id": c, "count": k} for c, k in enemy_bans.most_common()],
        "monsters": [{"key": k, "label": MONSTERS[k], **v} for k, v in monsters.items()
                     if v["us"] or v["them"]],
        "gold_curves": curves,
        "trend": trend,
        "deaths": deaths,
        "jungle": {"players": sorted(jungle_players.values(), key=lambda p: -p["games"]),
                   "paths": jungle_paths, "events": jungle_events, "path_minutes": PATH_MINUTES},
    }


def history_rows(records: list[GameRecord]) -> list[dict]:
    """Spielliste (neueste zuerst) inkl. ausgeschlossener Spiele für die Verwaltung."""
    rows = []
    for rec in sorted(records, key=lambda r: r.match.created, reverse=True):
        gd15 = None
        if rec.timeline:
            gd15 = at(team_series(rec.timeline, rec.side, "gold"), 15)
        rows.append({
            "match_id": rec.match.match_id,
            "date": rec.match.created,
            "duration": rec.match.duration,
            "patch": rec.match.version,
            "win": rec.win,
            "side": rec.us.side,
            "us": rec.us,
            "them": rec.them,
            "opponent": rec.opponent,
            "gold_diff": rec.us.gold - rec.them.gold,
            "gd15": gd15,
            "label": rec.label,
            "included": rec.included,
            "tournament": bool(rec.match.tournament_code),
        })
    return rows


def filter_records(records: list[GameRecord], *, label: str = "all", side: str = "all",
                   patch: str = "", last: int = 0) -> list[GameRecord]:
    out = [r for r in records if r.included]
    if label != "all":
        out = [r for r in out if r.label == label]
    if side in ("blue", "red"):
        out = [r for r in out if r.us.side == side]
    if patch:
        out = [r for r in out if r.match.version == patch]
    out.sort(key=lambda r: r.match.created, reverse=True)
    if last > 0:
        out = out[:last]
    return out


def match_side_for_team(match: MatchSummary, puuids: set[str], min_members: int) -> int | None:
    """teamId, auf der mindestens ``min_members`` Roster-Spieler zusammen gespielt haben."""
    best, best_count = None, 0
    for team_id, team in match.teams.items():
        count = sum(p.puuid in puuids for p in team.players)
        if count > best_count:
            best, best_count = team_id, count
    return best if best_count >= min_members else None


def together_side(match: MatchSummary, puuids: list[str]) -> int | None:
    """teamId, falls alle Spieler in diesem Match im selben Team standen."""
    sides = set()
    for puuid in puuids:
        team = match.team_of(puuid)
        if team is None:
            return None
        sides.add(team.team_id)
    return sides.pop() if len(sides) == 1 else None


def any_side(match: MatchSummary, puuids: list[str]) -> int | None:
    """teamId des Teams mit den meisten gesuchten Spielern (mindestens einer); bei Gleichstand zählt
    die Seite des zuerst genannten anwesenden Spielers."""
    counts: Counter = Counter()
    first: int | None = None
    for puuid in puuids:
        team = match.team_of(puuid)
        if team is not None:
            counts[team.team_id] += 1
            first = team.team_id if first is None else first
    if not counts:
        return None
    best = max(counts.values())
    return first if counts[first] == best else next(t for t, c in counts.items() if c == best)


def roster_from_games(games: list[tuple[MatchSummary, int]], searched: list[str]) -> list[dict]:
    """Alle Spieler, die in diesen Spielen im Team standen – gesuchte Spieler zuerst, dann nach Häufigkeit."""
    counts: Counter = Counter()
    positions: dict[str, Counter] = {}
    names: dict[str, tuple[str, str]] = {}
    for match, side in sorted(games, key=lambda g: g[0].created):
        for p in match.teams[side].players:
            counts[p.puuid] += 1
            positions.setdefault(p.puuid, Counter())[p.position] += 1
            names[p.puuid] = (p.name, p.tag)  # neuester Name gewinnt
    order = [p for p in searched if p in counts] + [p for p, _ in counts.most_common() if p not in searched]
    return [{"puuid": pid, "game_name": names[pid][0], "tag_line": names[pid][1], "games": counts[pid],
             "position": positions[pid].most_common(1)[0][0], "searched": pid in searched} for pid in order]


def default_label(match: MatchSummary) -> str:
    return "official" if match.tournament_code else "scrim"


def patches(records: list[GameRecord]) -> list[str]:
    return sorted({r.match.version for r in records},
                  key=lambda v: [int(x) if x.isdigit() else 0 for x in v.split(".")], reverse=True)


__all__ = [
    "GameRecord", "LABELS", "build_report", "history_rows", "filter_records", "match_side_for_team",
    "any_side", "default_label", "patches", "roster_from_games", "together_side",
]
