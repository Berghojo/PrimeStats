import copy

from primestats.matches import POSITIONS, parse_match


def test_parse_demo_match(demo_source):
    raw = next(iter(demo_source.matches.values()))
    match = parse_match(raw)
    assert set(match.teams) == {100, 200}
    assert match.is_custom
    for team in match.teams.values():
        assert [p.position for p in team.players] == list(POSITIONS)
        assert team.kills == sum(p.kills for p in team.players)
        assert len(team.bans) == 5
    assert match.teams[100].win != match.teams[200].win
    assert match.duration == raw["info"]["gameDuration"]


def test_opponent_lookup(demo_source):
    match = parse_match(next(iter(demo_source.matches.values())))
    mid = match.teams[100].by_position()["MIDDLE"]
    opp = match.opponent(mid)
    assert opp.team_id == 200 and opp.position == "MIDDLE"


def test_positions_inferred_for_custom_lobby_without_roles(demo_source):
    raw = copy.deepcopy(next(iter(demo_source.matches.values())))
    for p in raw["info"]["participants"]:
        p["teamPosition"] = ""
        p["individualPosition"] = "Invalid"
    match = parse_match(raw)
    for team in match.teams.values():
        positions = [p.position for p in team.players]
        assert sorted(positions) == sorted(POSITIONS)
        # Smite-Träger wird als Jungler erkannt
        jungler = next(p for p in team.players if 11 in p.spells)
        assert jungler.position == "JUNGLE"


def test_ignores_missing_bans(demo_source):
    raw = copy.deepcopy(next(iter(demo_source.matches.values())))
    raw["info"]["teams"][0]["bans"] = [{"championId": -1, "pickTurn": 1}]
    assert parse_match(raw).teams[100].bans == []
