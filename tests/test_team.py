from primestats.team_stats import build_report, filter_records, guess_team_tag, match_side_for_team


def test_sync_finds_only_team_games(service, synced_team, demo_source):
    games = service.store.team_games(synced_team.id)
    assert len(games) > 20
    puuids = synced_team.puuids
    for tg in games:
        match = service.match(tg.match_id)
        ours = [p for p in match.teams[tg.side].players if p.puuid in puuids]
        assert len(ours) >= 4
    # Lobbys mit nur zwei Teammitgliedern werden nicht übernommen
    ids = {tg.match_id for tg in games}
    mixed = [mid for mid, m in demo_source.matches.items()
             if sum(p["puuid"] in puuids for p in m["info"]["participants"]) == 2]
    assert mixed and not ids & set(mixed)


def test_sync_labels_tournament_code_games(service, synced_team):
    for tg in service.store.team_games(synced_team.id):
        match = service.match(tg.match_id)
        assert tg.label == ("official" if match.tournament_code else "scrim")


def test_resync_is_idempotent(service, synced_team):
    job = service.jobs.start(synced_team, background=False)
    assert job.status == "done" and job.new_games == 0


def test_report_numbers(service, synced_team):
    records = service.team_records(synced_team)
    report = build_report(synced_team, records)
    ov = report["overview"]
    assert ov["games"] == len(records)
    assert ov["wins"] == sum(r.win for r in records)
    assert ov["blue_games"] + ov["red_games"] == ov["games"]
    assert ov["timeline_games"] == len(records)
    members = [p for p in report["players"] if p["member"]]
    assert {p["name"] for p in members} <= {m.game_name for m in synced_team.members}
    for p in members:
        assert 0 <= p["winrate"] <= 1
        assert sum(c["games"] for c in p["champions"]) == p["games"]
    assert sum(p["games"] for p in report["picks"]) == 5 * len(records)


def test_filters(service, synced_team):
    records = service.team_records(synced_team)
    official = filter_records(records, label="official")
    assert official and all(r.match.tournament_code for r in official)
    blue = filter_records(records, side="blue")
    assert all(r.side == 100 for r in blue)
    assert len(filter_records(records, last=5)) == 5
    service.store.update_team_game(synced_team.id, records[0].match.match_id, included=False)
    assert len(filter_records(service.team_records(synced_team))) == len(records) - 1


def test_match_side_for_team(service, synced_team):
    tg = service.store.team_games(synced_team.id)[0]
    match = service.match(tg.match_id)
    assert match_side_for_team(match, synced_team.puuids, 4) == tg.side
    assert match_side_for_team(match, synced_team.puuids, 6) is None


def test_guess_team_tag():
    assert guess_team_tag(["WP Faun", "WP MoeBD", "WP x", "Other", "Foo"]) == "WP"
    assert guess_team_tag(["A", "B", "C"]) == ""
