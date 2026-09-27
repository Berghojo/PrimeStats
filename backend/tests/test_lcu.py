import copy

import pytest

from primestats import lcu
from primestats.demo import to_lcu
from primestats.matches import parse_match
from primestats.timeline import summarize_timeline


def _scrim(demo_source):
    mid = next(m for m, d in demo_source.matches.items() if not d["info"].get("tournamentCode"))
    return demo_source.matches[mid], demo_source.timelines[mid]


def test_roundtrip_matches_original(demo_source):
    match, timeline = _scrim(demo_source)
    item = to_lcu(match, timeline)
    converted = lcu.convert_game(item["game"])
    assert converted["metadata"]["matchId"] == match["metadata"]["matchId"]

    original, parsed = parse_match(match), parse_match(converted)
    assert parsed.duration == original.duration and parsed.created == original.created
    for team_id in (100, 200):
        a, b = original.teams[team_id], parsed.teams[team_id]
        assert (a.win, a.bans, a.kills, a.towers, a.dragons, a.barons, a.heralds, a.grubs) == \
               (b.win, b.bans, b.kills, b.towers, b.dragons, b.barons, b.heralds, b.grubs)
        assert (a.first_blood, a.first_tower, a.first_dragon) == (b.first_blood, b.first_tower, b.first_dragon)
        for pa, pb in zip(a.players, b.players):
            assert (pa.puuid, pa.position, pa.champion_id, pa.kills, pa.deaths, pa.assists, pa.cs, pa.gold,
                    pa.damage, pa.vision_score, pa.control_wards) == \
                   (pb.puuid, pb.position, pb.champion_id, pb.kills, pb.deaths, pb.assists, pb.cs, pb.gold,
                    pb.damage, pb.vision_score, pb.control_wards)

    tl = lcu.convert_timeline(item["timeline"], converted)
    assert summarize_timeline(tl, parsed)["players"] == summarize_timeline(timeline, original)["players"]


def test_positions_from_lane_and_role(demo_source):
    match, _ = _scrim(demo_source)
    game = to_lcu(match)["game"]
    positions = {p["participantId"]: lcu.convert_game(game)["info"]["participants"][i]["teamPosition"]
                 for i, p in enumerate(game["participants"])}
    assert sorted(positions.values()) == sorted(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] * 2)


def test_tolerates_missing_roles_and_fields(demo_source):
    match, _ = _scrim(demo_source)
    game = copy.deepcopy(to_lcu(match)["game"])
    for p in game["participants"]:
        p.pop("timeline")
        p["stats"].pop("visionScore")
    for t in game["teams"]:
        t.pop("hordeKills")
    parsed = parse_match(lcu.convert_game(game))
    for team in parsed.teams.values():
        assert sorted(p.position for p in team.players) == sorted(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"])
        assert team.grubs == 0
        assert all(p.vision_score == 0 for p in team.players)


def test_rejects_garbage():
    with pytest.raises(lcu.LcuFormatError):
        lcu.convert_game({"gameId": 1})
    with pytest.raises(lcu.LcuFormatError):
        lcu.convert_timeline({"nope": 1}, {"metadata": {"matchId": "X"}, "info": {"participants": []}})
