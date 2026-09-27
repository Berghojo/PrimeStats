from primestats.fights import TOWERS, classify_kills, teamfight_kills, tower_standing
from primestats.matches import parse_match


def _kill(t, x, y, killer, victim, assists=()):
    return {"t": t, "x": x, "y": y, "killer": killer, "victim": victim, "assists": list(assists)}


def test_teamfight_chain():
    kills = [_kill(600, 5000, 5000, 1, 6), _kill(610, 5500, 5200, 7, 2), _kill(625, 6500, 5800, 3, 8),
             _kill(700, 5000, 5000, 1, 9),                       # 75 s später: eigener Kill
             _kill(612, 12000, 12000, 4, 10)]                    # gleichzeitig, aber weit weg
    assert teamfight_kills(kills) == {0, 1, 2}


def test_dive_needs_a_standing_tower():
    x, y = TOWERS[100][0]                                        # blauer Top-Außenturm
    assert tower_standing(100, x + 300, y, 300, [])
    assert not tower_standing(200, x + 300, y, 300, [])          # kein roter Turm dort
    lost = [{"t": 200, "team": 100, "x": x, "y": y}]
    assert not tower_standing(100, x + 300, y, 300, lost)        # Turm schon gefallen
    assert tower_standing(100, x + 300, y, 150, lost)            # vor dem Fall noch da


def test_classify_order(demo_source):
    match = parse_match(next(iter(demo_source.matches.values())))
    pos = {p.participant_id: p.position for p in match.participants}
    blue = {p.position: p.participant_id for p in match.participants if p.team_id == 100}
    red = {p.position: p.participant_id for p in match.participants if p.team_id == 200}
    tx, ty = TOWERS[100][3]                                      # blauer Mid-Außenturm
    kills = [
        _kill(300, 1300, 8600, red["TOP"], blue["TOP"]),                                   # 1v1 auf Top
        _kill(320, 1300, 8000, red["JUNGLE"], blue["TOP"], [red["TOP"]]),                  # Gank
        _kill(400, 7400, 7400, red["MIDDLE"], blue["BOTTOM"], [red["UTILITY"]]),           # Roam (Mid)
        _kill(500, tx, ty, red["MIDDLE"], blue["MIDDLE"]),                                 # Dive
        _kill(900, 7000, 3000, red["JUNGLE"], blue["BOTTOM"], [red["MIDDLE"], red["TOP"]]),  # Skirmish
        _kill(1000, 3000, 12000, blue["JUNGLE"], red["JUNGLE"]),                           # Jungle 1v1
        _kill(1100, 3000, 12000, 0, blue["MIDDLE"]),                                       # ohne Champion
    ]
    assert pos[blue["TOP"]] == "TOP"
    assert classify_kills(match, {"kills": kills}) == ["lane", "gank", "roam", "dive", "skirmish", "duel", "other"]


def test_tower_positions_match_frontend():
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "towers.ts").read_text(encoding="utf-8")
    blue = src[src.index("const BLUE"):src.index("];", src.index("const BLUE"))]
    frontend = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+), (\d+)\]", blue)]
    assert frontend == TOWERS[100]
