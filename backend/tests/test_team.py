from primestats.team_stats import build_report, filter_records, match_side_for_team


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


def test_champion_table(service, synced_team):
    records = service.team_records(synced_team)
    report = build_report(synced_team, records)
    table = report["champion_table"]
    n = len(records)
    assert sum(r["picks"] for r in table) == 5 * n
    assert sum(r["bans_by_us"] for r in table) == sum(b["count"] for b in report["our_bans"])
    assert sum(r["bans_against"] for r in table) == sum(b["count"] for b in report["enemy_bans"])
    for row in table:
        assert 0 <= row["presence"] <= 1
        if row["picks"]:
            assert sum(p["games"] for p in row["players"]) == row["picks"]
            assert 0 <= row["winrate"] <= 1 and row["position"] == row["positions"][0]["position"]
            assert sum(p["games"] for p in row["positions"]) == row["picks"]
        else:  # nur gebannt
            assert row["winrate"] is None and row["players"] == []
    assert [r["picks"] for r in table] == sorted((r["picks"] for r in table), reverse=True)


def test_champion_on_several_roles_is_one_row(service, synced_team):
    records = service.team_records(synced_team)
    # künstlich: denselben Champion in zwei Spielen auf verschiedenen Rollen spielen lassen
    a, b = records[0].us.players[0], records[1].us.players[2]   # Top bzw. Mid
    a.champion_id = b.champion_id = 99999
    table = build_report(synced_team, records[:2])["champion_table"]
    rows = [r for r in table if r["champion_id"] == 99999]
    assert len(rows) == 1
    assert {p["position"] for p in rows[0]["positions"]} == {a.position, b.position}
    assert {p["name"] for p in rows[0]["players"]} == {a.name, b.name}


def test_jungle_pathing_and_kill_locations(service, synced_team, demo_source):
    records = service.team_records(synced_team)
    jungle = build_report(synced_team, records)["jungle"]
    with_tl = [r for r in records if r.timeline]
    assert [p["name"] for p in jungle["players"]] == ["NLE Waldgeist"]
    assert len(jungle["paths"]) == len(with_tl)
    path = jungle["paths"][0]
    assert len(path["points"]) == jungle["path_minutes"] + 1 and all(len(pt) == 2 for pt in path["points"])

    # jedes Ereignis passt zu einem CHAMPION_KILL der Timeline, an dem der Jungler beteiligt war
    waldgeist = demo_source.account("NLE Waldgeist#EUW")["puuid"]
    for ev in jungle["events"][:30]:
        raw = demo_source.timelines[ev["match_id"]]
        pid = next(p.participant_id for p in service.match(ev["match_id"]).participants if p.puuid == waldgeist)
        kills = [e for f in raw["info"]["frames"] for e in f["events"] if e["type"] == "CHAMPION_KILL"
                 and e["position"] == {"x": ev["x"], "y": ev["y"]}]
        assert kills
        k = kills[0]
        expected = ("kill" if k["killerId"] == pid else "assist" if pid in k["assistingParticipantIds"]
                    else "death")
        assert ev["type"] == expected and 0 <= ev["x"] <= 15000
    assert {e["type"] for e in jungle["events"]} == {"kill", "assist", "death"}


def test_death_kinds():
    from primestats.team_stats import death_kind
    assert death_kind("TOP", ["JUNGLE", "TOP"]) == "gank"
    assert death_kind("MIDDLE", ["UTILITY"]) == "roam"
    assert death_kind("BOTTOM", ["UTILITY", "BOTTOM"]) == "lane"        # Botlane-Duo zählt als eigene Lane
    assert death_kind("UTILITY", ["MIDDLE", "JUNGLE"]) == "gank_roam"
    assert death_kind("JUNGLE", ["JUNGLE"]) == "duel"
    assert death_kind("JUNGLE", ["JUNGLE", "MIDDLE"]) == "roam"
    assert death_kind("TOP", []) == "other"


def test_report_lists_deaths_of_own_players(service, synced_team, demo_source):
    records = service.team_records(synced_team)
    deaths = build_report(synced_team, records)["deaths"]
    own = {m.puuid for m in synced_team.members}
    assert deaths and all(d["puuid"] in own for d in deaths)
    kinds = {d["kind"] for d in deaths}
    assert {"gank", "roam", "lane"} <= kinds
    for d in deaths[:40]:
        match = service.match(d["match_id"])
        enemy = {p.puuid for p in match.participants if p.team_id != match.player(d["puuid"]).team_id}
        assert all(b["position"] for b in d["by"])
        assert len(d["by"]) == len({b["name"] for b in d["by"]})
        assert all(p.puuid in enemy for p in match.participants if p.name in {b["name"] for b in d["by"]})
