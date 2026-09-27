"""Generierte Beispieldaten im Format der Riot-API (für Demo-Modus und Tests).

Alle Spieler- und Teamnamen sind frei erfunden.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone

from .ddragon import FALLBACK_FILE
from .matches import POSITIONS
from .riot import NotFound, split_riot_id

DEMO_TEAM = ("Nordlicht Esports", "NLE", [
    ("NLE Frostbite", "TOP"), ("NLE Waldgeist", "JUNGLE"), ("NLE Polaris", "MIDDLE"),
    ("NLE Kompass", "BOTTOM"), ("NLE Leuchtturm", "UTILITY"), ("NLE Treibholz", "MIDDLE"),
])
OPPONENTS = [
    ("RHW", ["RHW Stahlwerk", "RHW Nebelhorn", "RHW Kranich", "RHW Pegel", "RHW Anker"], 0.45),
    ("BSK", ["BSK Runenstein", "BSK Wikinger", "BSK Skalde", "BSK Drakkar", "BSK Hjalmar"], 0.60),
    ("ALP", ["ALP Gipfel", "ALP Murmel", "ALP Enzian", "ALP Steinbock", "ALP Firn"], 0.35),
    ("HFK", ["HFK Kaimauer", "HFK Lotse", "HFK Möwe", "HFK Kogge", "HFK Tide"], 0.52),
]
RANDOMS = ["Kaffeetasse", "Blitzbirne", "Nachteule", "Wolkenbruch", "Zimtstern", "Laubfrosch",
           "Sturmtief", "Pixelhexe", "Kieselstein", "Glühwurm", "Schneeflocke", "Papierflieger"]

POOLS = {
    "TOP": ["Aatrox", "KSante", "Renekton", "Gnar", "Jax", "Rumble", "Ornn"],
    "JUNGLE": ["LeeSin", "Viego", "Sejuani", "Vi", "Maokai", "XinZhao", "MonkeyKing"],
    "MIDDLE": ["Ahri", "Orianna", "Syndra", "Taliyah", "Azir", "Sylas", "Yone"],
    "BOTTOM": ["Jinx", "Kaisa", "Ezreal", "Varus", "Xayah", "Ashe", "Zeri"],
    "UTILITY": ["Nautilus", "Rakan", "Alistar", "Leona", "Braum", "Thresh", "Renata"],
}
BAN_POOL = ["Rell", "Kalista", "Vi", "Skarner", "Corki", "Poppy", "Rumble", "Aurora", "Ambessa",
            "Nidalee", "Leblanc", "Yasuo", "Lucian", "Pantheon", "Camille", "Galio"]

GPM = {"TOP": 380, "JUNGLE": 360, "MIDDLE": 400, "BOTTOM": 420, "UTILITY": 265}
XPM = {"TOP": 520, "JUNGLE": 430, "MIDDLE": 540, "BOTTOM": 440, "UTILITY": 360}
CSM = {"TOP": 7.6, "JUNGLE": 5.8, "MIDDLE": 8.2, "BOTTOM": 8.8, "UTILITY": 1.1}
DPM = {"TOP": 520, "JUNGLE": 380, "MIDDLE": 700, "BOTTOM": 760, "UTILITY": 220}
KILL_WEIGHT = {"TOP": 0.9, "JUNGLE": 1.1, "MIDDLE": 1.3, "BOTTOM": 1.4, "UTILITY": 0.3}
XP_LEVELS = [0, 280, 660, 1140, 1720, 2400, 3180, 4060, 5040, 6120, 7300, 8580, 9960, 11440,
             13020, 14700, 16480, 18360]


def _champion_keys() -> dict[str, int]:
    data = json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
    return {c["id"]: int(c["key"]) for c in data["data"].values()}


def _puuid(name: str) -> str:
    base = "".join(ch for ch in name.lower() if ch.isalnum())
    return f"demo-{base}".ljust(78, "x")


def _level(xp: float) -> int:
    return max(i + 1 for i, need in enumerate(XP_LEVELS) if xp >= need)


class DemoSource:
    """Erfüllt das MatchSource-Protokoll mit deterministisch generierten Spielen."""

    def __init__(self, seed: int = 7, now: datetime | None = None):
        self.rng = random.Random(seed)
        self.now = now or datetime.now(timezone.utc)
        self.champs = _champion_keys()
        self.accounts: dict[str, dict] = {}
        self.matches: dict[str, dict] = {}
        self.timelines: dict[str, dict] = {}
        self.by_puuid: dict[str, list[str]] = {}
        self._generate()

    # --------------------------------------------------------------- API
    def account(self, riot_id: str) -> dict:
        name, tag = split_riot_id(riot_id)
        acc = self.accounts.get(f"{name}#{tag}".lower())
        if not acc:
            raise NotFound(404, f"Spieler {name}#{tag} wurde nicht gefunden (Demo: z.B. 'NLE Polaris#EUW').")
        return acc

    def match_ids(self, puuid: str, count: int = 20, *, queue: int | None = None,
                  type: str | None = None, start: int = 0) -> list[str]:
        # Wie die echte Riot-API: Custom Games gibt es nur mit Turniercode
        ids = [i for i in self.by_puuid.get(puuid, []) if self.matches[i]["info"].get("tournamentCode")]
        return ids[start:start + count]

    def match(self, match_id: str) -> dict:
        if match_id not in self.matches:
            raise NotFound(404, "Match nicht gefunden.")
        return self.matches[match_id]

    def timeline(self, match_id: str) -> dict:
        if match_id not in self.timelines:
            raise NotFound(404, "Timeline nicht gefunden.")
        return self.timelines[match_id]

    # ---------------------------------------------------------- generator
    def _player(self, name: str) -> dict:
        key = f"{name}#EUW".lower()
        if key not in self.accounts:
            self.accounts[key] = {"puuid": _puuid(name), "gameName": name, "tagLine": "EUW"}
        return self.accounts[key]

    def _generate(self) -> None:
        rng = self.rng
        _, _, roster = DEMO_TEAM
        start = (self.now - timedelta(days=56)).replace(hour=0, minute=0, second=0, microsecond=0)
        for week in range(8):
            monday = start + timedelta(days=7 * week)
            # Prime-League-Spieltag (Bo2, Turniercode) am Sonntag
            tag, names, strength = OPPONENTS[week % len(OPPONENTS)]
            code = f"EUW04demo-{week:04d}-{rng.randrange(16 ** 8):08x}"
            for game in range(2):
                self._game(monday + timedelta(days=6, hours=18, minutes=70 * game),
                           self._lineup(roster, sub_chance=0.1), names, strength, code, us_blue=game == 0)
            # Scrims unter der Woche
            for day in rng.sample([0, 1, 2, 3], k=rng.choice([1, 2])):
                tag, names, strength = rng.choice(OPPONENTS)
                for game in range(rng.choice([2, 3])):
                    self._game(monday + timedelta(days=day, hours=19, minutes=45 * game),
                               self._lineup(roster, sub_chance=0.25), names, strength, "",
                               us_blue=rng.random() < 0.5)
            # Private Custom-Lobby mit nur zwei Teammitgliedern (soll nicht als Teamspiel zählen)
            if week % 3 == 1:
                mixed = [roster[0][0], roster[2][0]] + rng.sample(RANDOMS, 3)
                others = rng.sample([n for n in RANDOMS if n not in mixed], 5)
                self._game(monday + timedelta(days=4, hours=21), mixed, others, 0.5, "", us_blue=True)
        for ids in self.by_puuid.values():
            ids.sort(reverse=True)

    def _lineup(self, roster, sub_chance: float) -> list[str]:
        names = [name for name, _ in roster[:5]]
        if self.rng.random() < sub_chance:
            names[self.rng.choice([0, 2])] = roster[5][0]
        return names

    def _game(self, when: datetime, us: list[str], them: list[str], their_strength: float,
              code: str, us_blue: bool) -> None:
        rng = self.rng
        # Match-IDs steigen wie bei Riot mit der Zeit an
        match_id = f"EUW1_{7_000_000_000 + int(when.timestamp()) - 1_700_000_000}"
        blue_names, red_names = (us, them) if us_blue else (them, us)
        p_us = 0.58 - (their_strength - 0.5) * 0.8
        us_win = rng.random() < p_us
        blue_win = us_win == us_blue
        minutes = rng.randint(24, 37)
        seconds = rng.randint(0, 59)
        duration = minutes * 60 + seconds
        created_ms = int(when.timestamp() * 1000)

        # Champions ziehen
        taken: set[str] = set()
        lineup = []  # (participantId, name, team, pos, champ)
        for team_id, names in ((100, blue_names), (200, red_names)):
            for idx, (name, pos) in enumerate(zip(names, POSITIONS)):
                pool = [c for c in POOLS[pos] if c not in taken]
                weights = [len(pool) - i + (3 if i == 0 else 0) for i in range(len(pool))]
                offset = sum(map(ord, name)) % len(pool)
                pool = pool[offset:] + pool[:offset]
                champ = rng.choices(pool, weights=weights)[0]
                taken.add(champ)
                pid = idx + 1 if team_id == 100 else idx + 6
                lineup.append((pid, name, team_id, pos, champ))
        bans = {}
        for team_id in (100, 200):
            options = [c for c in BAN_POOL if c not in taken]
            chosen = rng.sample(options, 5)
            taken.update(chosen)
            bans[team_id] = chosen

        # Vorsprung (Gold) des blauen Teams über die Zeit
        sign = 1 if blue_win else -1
        amplitude = rng.uniform(2500, 11000)
        walk = 0.0
        lead = []
        for t in range(minutes + 1):
            walk += rng.gauss(0, 350)
            base = sign * amplitude * (t / minutes) ** 1.4
            if t > 0 and rng.random() < 0.25:  # Comebacks: frühe Führung des Verlierers
                base -= sign * 900 * math.exp(-t / 10)
            lead.append(base + walk * min(1, t / 6) * (1 - t / (minutes + 4)))

        # Kills
        total_kills = rng.randint(14, 42)
        events = []
        kda = {pid: [0, 0, 0] for pid, *_ in lineup}
        first_blood_team = None
        for _ in range(total_kills):
            ts = int(rng.triangular(150, duration - 10, duration * 0.6) * 1000)
            blue_share = 0.5 + 0.25 * max(-1, min(1, lead[min(ts // 60000, minutes)] / 5000))
            killer_team = 100 if rng.random() < blue_share else 200
            mates = [row for row in lineup if row[2] == killer_team]
            enemies = [row for row in lineup if row[2] != killer_team]
            killer = rng.choices(mates, weights=[KILL_WEIGHT[r[3]] for r in mates])[0]
            victim = rng.choice(enemies)
            helpers = [r[0] for r in rng.sample([m for m in mates if m != killer], rng.randint(0, 3))]
            events.append({"type": "CHAMPION_KILL", "timestamp": ts, "killerId": killer[0],
                           "victimId": victim[0], "assistingParticipantIds": helpers})
        events.sort(key=lambda e: e["timestamp"])
        for e in events:
            kda[e["killerId"]][0] += 1
            kda[e["victimId"]][1] += 1
            for h in e["assistingParticipantIds"]:
                kda[h][2] += 1
        if events:
            first_blood_team = 100 if events[0]["killerId"] <= 5 else 200

        # Objectives
        objectives = {100: dict.fromkeys(("dragon", "baron", "riftHerald", "horde", "atakhan", "tower",
                                          "inhibitor"), 0), 200: None}
        objectives[200] = dict(objectives[100])
        firsts: dict[str, int] = {}
        winner = 100 if blue_win else 200
        loser = 200 if blue_win else 100

        def take(kind: str, monster: str | None, t_min: float, favoured: float, sub: str | None = None,
                 count: int = 1):
            idx = min(int(t_min), minutes)
            p_blue = 0.5 + 0.35 * max(-1, min(1, lead[idx] / 4000))
            team = 100 if rng.random() < (p_blue * favoured + (1 - favoured) * 0.5) else 200
            objectives[team][kind] += count
            firsts.setdefault(kind, team)
            if monster:
                for c in range(count):
                    killer = rng.choice([r for r in lineup if r[2] == team and r[3] == "JUNGLE"])
                    ev = {"type": "ELITE_MONSTER_KILL", "timestamp": int((t_min * 60 + c * 20) * 1000),
                          "killerId": killer[0], "killerTeamId": team, "monsterType": monster}
                    if sub:
                        ev["monsterSubType"] = sub
                    events.append(ev)
            return team

        take("horde", "HORDE", rng.uniform(5.5, 7.5), 0.8, count=3)
        if minutes > 12:
            take("horde", "HORDE", rng.uniform(10, 12.5), 0.9, count=3)
        take("riftHerald", "RIFTHERALD", rng.uniform(14.5, 17), 0.9)
        t = rng.uniform(5.2, 7)
        dragon_types = ["FIRE_DRAGON", "WATER_DRAGON", "EARTH_DRAGON", "AIR_DRAGON", "HEXTECH_DRAGON",
                        "CHEMTECH_DRAGON"]
        while t < minutes - 1 and max(objectives[100]["dragon"], objectives[200]["dragon"]) < 4:
            take("dragon", "DRAGON", t, 1.0, sub=rng.choice(dragon_types))
            t += rng.uniform(5.2, 7.5)
        if minutes >= 21 and rng.random() < 0.7:
            take("atakhan", "ATAKHAN", rng.uniform(20.5, 23), 1.0)
        if minutes >= 26:
            objectives[winner]["baron"] += 1
            firsts.setdefault("baron", winner)
            jungler = next(r for r in lineup if r[2] == winner and r[3] == "JUNGLE")
            events.append({"type": "ELITE_MONSTER_KILL", "timestamp": int(rng.uniform(25.5, minutes - 0.5)
                                                                          * 60000),
                           "killerId": jungler[0], "killerTeamId": winner, "monsterType": "BARON_NASHOR"})
        objectives[winner]["tower"] = rng.randint(7, 11)
        objectives[loser]["tower"] = rng.randint(0, 5)
        objectives[winner]["inhibitor"] = rng.randint(1, 3)
        firsts["tower"] = winner if rng.random() < 0.7 else loser
        events.sort(key=lambda e: e["timestamp"])

        # Minutenwerte pro Spieler
        noise = {pid: rng.uniform(0.88, 1.12) for pid, *_ in lineup}
        frames = []
        for t in range(minutes + 1):
            pframes = {}
            for pid, name, team_id, pos, champ in lineup:
                side = 1 if team_id == 100 else -1
                active = max(0.0, t - 1.5)
                gold = 500 + GPM[pos] * active * noise[pid] + side * lead[t] * 0.2 * (1.1 if pos != "UTILITY" else 0.5)
                xp = XPM[pos] * t * noise[pid] + side * lead[t] * 0.12
                cs = CSM[pos] * active * noise[pid] + side * lead[t] / 600
                dmg = DPM[pos] * (t ** 1.15) * noise[pid] * (1 + side * lead[t] / 40000)
                pframes[str(pid)] = {
                    "participantId": pid,
                    "totalGold": int(max(500, gold)),
                    "currentGold": int(rng.uniform(0, 1200) if t else 500),
                    "xp": int(max(0, xp)),
                    "level": _level(max(0, xp)),
                    "minionsKilled": int(max(0, cs * (0.25 if pos == "JUNGLE" else 1))),
                    "jungleMinionsKilled": int(max(0, cs * 0.75)) if pos == "JUNGLE" else 0,
                    "damageStats": {"totalDamageDoneToChampions": int(max(0, dmg)),
                                    "totalDamageTaken": int(max(0, dmg * rng.uniform(0.8, 1.4)))},
                    "position": {"x": rng.randint(500, 14000), "y": rng.randint(500, 14000)},
                }
            frames.append({"timestamp": t * 60000 + (seconds * 1000 if t == minutes else 0),
                           "participantFrames": pframes, "events": []})
        for e in events:
            idx = min(e["timestamp"] // 60000 + 1, minutes)
            frames[idx]["events"].append(e)

        last = frames[-1]["participantFrames"]
        participants = []
        spells_other = [(4, 14), (4, 12), (4, 7), (4, 3)]
        for pid, name, team_id, pos, champ in lineup:
            acc = self._player(name)
            pf = last[str(pid)]
            k, d, a = kda[pid]
            s1, s2 = (4, 11) if pos == "JUNGLE" else spells_other[
                {"TOP": 1, "MIDDLE": 0, "BOTTOM": 2, "UTILITY": 3}[pos]]
            participants.append({
                "participantId": pid, "puuid": acc["puuid"], "riotIdGameName": name, "riotIdTagline": "EUW",
                "championId": self.champs.get(champ, 1), "championName": champ, "teamId": team_id,
                "teamPosition": pos, "individualPosition": pos, "win": (team_id == 100) == blue_win,
                "kills": k, "deaths": d, "assists": a,
                "totalMinionsKilled": pf["minionsKilled"], "neutralMinionsKilled": pf["jungleMinionsKilled"],
                "goldEarned": pf["totalGold"], "champLevel": pf["level"],
                "totalDamageDealtToChampions": pf["damageStats"]["totalDamageDoneToChampions"],
                "totalDamageTaken": pf["damageStats"]["totalDamageTaken"],
                "visionScore": int(minutes * {"UTILITY": 2.6, "JUNGLE": 1.6}.get(pos, 0.9) * noise[pid]),
                "wardsPlaced": int(minutes * {"UTILITY": 1.4, "JUNGLE": 0.6}.get(pos, 0.4)),
                "wardsKilled": int(minutes * {"UTILITY": 0.4, "JUNGLE": 0.35}.get(pos, 0.15)),
                "visionWardsBoughtInGame": rng.randint(1, 3) + (4 if pos == "UTILITY" else 0),
                "firstBloodKill": bool(events and events[0]["type"] == "CHAMPION_KILL"
                                       and events[0]["killerId"] == pid),
                "firstBloodAssist": False,
                "summoner1Id": s1, "summoner2Id": s2,
                **{f"item{i}": rng.choice([3031, 3071, 3157, 6653, 3065, 3190, 3742, 0]) for i in range(6)},
                "item6": 3340,
            })
        fb = next((e for e in events if e["type"] == "CHAMPION_KILL"), None)
        for p in participants:
            if fb and p["participantId"] in fb["assistingParticipantIds"]:
                p["firstBloodAssist"] = True

        teams = []
        for team_id in (100, 200):
            o = objectives[team_id]
            team_kills = sum(kda[pid][0] for pid, _, tid, *_ in lineup if tid == team_id)

            def obj(kind, kills, _team=team_id):
                return {"first": firsts.get(kind) == _team, "kills": kills}

            teams.append({
                "teamId": team_id, "win": (team_id == 100) == blue_win,
                "bans": [{"championId": self.champs.get(c, -1), "pickTurn": i + 1}
                         for i, c in enumerate(bans[team_id])],
                "objectives": {
                    "champion": {"first": first_blood_team == team_id, "kills": team_kills},
                    "tower": obj("tower", o["tower"]), "inhibitor": obj("inhibitor", o["inhibitor"]),
                    "dragon": obj("dragon", o["dragon"]), "baron": obj("baron", o["baron"]),
                    "riftHerald": obj("riftHerald", o["riftHerald"]), "horde": obj("horde", o["horde"]),
                    "atakhan": obj("atakhan", o["atakhan"]),
                },
            })

        info = {
            "gameCreation": created_ms, "gameStartTimestamp": created_ms + 90_000,
            "gameEndTimestamp": created_ms + 90_000 + duration * 1000, "gameDuration": duration,
            "gameMode": "CLASSIC", "gameType": "CUSTOM_GAME", "queueId": 0, "mapId": 11,
            "gameVersion": "15.18.700.1234" if when > self.now - timedelta(days=21) else "15.17.690.1111",
            "platformId": "EUW1", "participants": participants, "teams": teams,
        }
        if code:
            info["tournamentCode"] = code
        self.matches[match_id] = {"metadata": {"matchId": match_id,
                                               "participants": [p["puuid"] for p in participants]},
                                  "info": info}
        self.timelines[match_id] = {
            "metadata": {"matchId": match_id},
            "info": {"frameInterval": 60000, "frames": frames,
                     "participants": [{"participantId": p["participantId"], "puuid": p["puuid"]}
                                      for p in participants]},
        }
        for p in participants:
            self.by_puuid.setdefault(p["puuid"], []).append(match_id)


def demo_team_entries() -> tuple[str, str, list[tuple[str, str]]]:
    name, tag, roster = DEMO_TEAM
    return name, tag, [(f"{n}#EUW", pos) for n, pos in roster]


# ------------------------------------------------------------------ LCU
_LANE_ROLE = {"TOP": ("TOP", "SOLO"), "JUNGLE": ("JUNGLE", "NONE"), "MIDDLE": ("MIDDLE", "SOLO"),
              "BOTTOM": ("BOTTOM", "DUO_CARRY"), "UTILITY": ("BOTTOM", "DUO_SUPPORT")}


def to_lcu(match: dict, timeline: dict | None = None) -> dict:
    """Wandelt ein v5-Match (+Timeline) ins Format der League-Client-API um.

    Dient dem Demo-Modus und den Tests als Nachbildung dessen, was der Uploader aus dem
    Client liest (Struktur wie match-v4: participantIdentities, stats, "Win"/"Fail").
    """
    info = match["info"]
    participants, identities = [], []
    for p in info["participants"]:
        lane, role = _LANE_ROLE[p["teamPosition"]]
        stats = {k: v for k, v in p.items() if k not in {
            "participantId", "puuid", "riotIdGameName", "riotIdTagline", "championId", "championName",
            "teamId", "teamPosition", "individualPosition", "summoner1Id", "summoner2Id"}}
        participants.append({"participantId": p["participantId"], "teamId": p["teamId"],
                             "championId": p["championId"], "spell1Id": p["summoner1Id"],
                             "spell2Id": p["summoner2Id"], "stats": stats,
                             "timeline": {"lane": lane, "role": role}})
        identities.append({"participantId": p["participantId"],
                           "player": {"puuid": p["puuid"], "gameName": p["riotIdGameName"],
                                      "tagLine": p["riotIdTagline"], "summonerName": p["riotIdGameName"],
                                      "platformId": info["platformId"]}})
    teams = []
    for t in info["teams"]:
        o = t["objectives"]
        teams.append({
            "teamId": t["teamId"], "win": "Win" if t["win"] else "Fail", "bans": t["bans"],
            "firstBlood": o["champion"]["first"], "firstTower": o["tower"]["first"],
            "firstInhibitor": o["inhibitor"]["first"], "firstDargon": o["dragon"]["first"],
            "firstBaron": o["baron"]["first"], "firstRiftHerald": o["riftHerald"]["first"],
            "towerKills": o["tower"]["kills"], "inhibitorKills": o["inhibitor"]["kills"],
            "dragonKills": o["dragon"]["kills"], "baronKills": o["baron"]["kills"],
            "riftHeraldKills": o["riftHerald"]["kills"], "hordeKills": o["horde"]["kills"],
        })
    game = {
        "gameId": int(match["metadata"]["matchId"].split("_")[1]), "platformId": info["platformId"],
        "gameCreation": info["gameCreation"], "gameDuration": info["gameDuration"],
        "gameMode": info["gameMode"], "gameType": info["gameType"], "gameVersion": info["gameVersion"],
        "mapId": info["mapId"], "queueId": info["queueId"], "seasonId": 15,
        "participants": participants, "participantIdentities": identities, "teams": teams,
    }
    lcu_timeline = None
    if timeline:
        lcu_timeline = {"frameInterval": timeline["info"]["frameInterval"], "frames": timeline["info"]["frames"]}
    return {"game": game, "timeline": lcu_timeline}


def import_demo_scrims(service, source: "DemoSource") -> None:
    """Demo: Scrims ohne Turniercode so importieren, als hätte sie der Uploader hochgeladen."""
    items = [to_lcu(m, source.timelines.get(mid)) for mid, m in source.matches.items()
             if not m["info"].get("tournamentCode")]
    for i in range(0, len(items), 25):
        service.import_lcu(items[i:i + 25], uploader="demo")
