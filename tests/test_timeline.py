from primestats.matches import parse_match
from primestats.timeline import analysis_payload, average_series, player_series, summarize_timeline, team_series


def _first(demo_source):
    mid = next(iter(demo_source.matches))
    match = parse_match(demo_source.matches[mid])
    return match, summarize_timeline(demo_source.timelines[mid], match)


def test_summary_matches_final_scoreboard(demo_source):
    match, summary = _first(demo_source)
    for p in match.participants:
        row = summary["players"][p.puuid]
        assert row["kills"][-1] == p.kills
        assert row["deaths"][-1] == p.deaths
        assert row["assists"][-1] == p.assists
        assert len(row["gold"]) == summary["minutes"]


def test_lane_diffs_are_antisymmetric(demo_source):
    match, summary = _first(demo_source)
    blue_mid = match.teams[100].by_position()["MIDDLE"]
    red_mid = match.teams[200].by_position()["MIDDLE"]
    a = player_series(summary, match, blue_mid.puuid)["gold_diff"]
    b = player_series(summary, match, red_mid.puuid)["gold_diff"]
    assert all(x == -y for x, y in zip(a, b))


def test_team_series_sign(demo_source):
    match, summary = _first(demo_source)
    blue = team_series(summary, 100)
    red = team_series(summary, 200)
    assert blue[0] == 0 or blue[0] == -red[0]
    assert all(x == -y for x, y in zip(blue, red))


def test_average_series_handles_different_lengths():
    values, counts = average_series([[0, 10, 20], [0, 20]])
    assert values == [0, 15, 20]
    assert counts == [2, 2, 1]


def test_average_series_truncates_sparse_tail():
    values, counts = average_series([[1, 1, 1, 1], [1, 1], [1, 1]], min_share=0.5)
    assert len(values) == 2 and counts == [3, 3]


def test_analysis_payload_focus_first(demo_source):
    items = []
    for mid in list(demo_source.matches)[:3]:
        match = parse_match(demo_source.matches[mid])
        items.append((match, summarize_timeline(demo_source.timelines[mid], match)))
    focus = {items[0][0].participants[3].puuid}
    payload = analysis_payload(items, focus)
    assert payload["players"][0]["puuid"] in focus
    assert set(payload["series"]) >= {"gold", "gold_diff", "kp"}
