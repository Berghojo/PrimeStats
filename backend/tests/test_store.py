from primestats.services import PrimeStats
from primestats.store import Member


class CountingSource:
    def __init__(self, demo):
        self.demo = demo
        self.calls = []

    def account(self, riot_id):
        self.calls.append(("account", riot_id))
        return self.demo.account(riot_id)

    def match_ids(self, *args, **kwargs):
        return self.demo.match_ids(*args, **kwargs)

    def match(self, match_id):
        self.calls.append(("match", match_id))
        return self.demo.match(match_id)

    def timeline(self, match_id):
        self.calls.append(("timeline", match_id))
        return self.demo.timeline(match_id)


def test_service_caches_api_responses_in_postgres(store, demo_source):
    source = CountingSource(demo_source)
    mid = next(iter(demo_source.matches))
    first = PrimeStats(store, source)
    first.account("NLE Polaris#EUW")
    match = first.match(mid)
    first.timeline_summary(match)
    assert len(source.calls) == 3
    # neue Service-Instanz (leerer Speicher-Cache) liest alles aus der Datenbank
    second = PrimeStats(store, source)
    second.account("nle polaris#euw")
    second.timeline_summary(second.match(mid))
    assert len(source.calls) == 3
    assert store.get_timeline(mid) == demo_source.timeline(mid)


def test_team_crud(store):
    members = [Member("p1", "A", "EUW", "TOP"), Member("p2", "B", "EUW", "")]
    team_id = store.create_team("Team", "T", 4, members)
    team = store.get_team(team_id)
    assert [m.riot_id for m in team.members] == ["A#EUW", "B#EUW"]
    assert team.last_synced is None

    store.update_team(team_id, "Team 2", "T2", 3, [Member("p2", "B", "EUW", "MIDDLE"), Member("p3", "C", "EUW")])
    team = store.get_team(team_id)
    assert (team.name, team.tag, team.min_members) == ("Team 2", "T2", 3)
    assert [(m.puuid, m.role) for m in team.members] == [("p2", "MIDDLE"), ("p3", "")]

    assert store.add_team_games(team_id, [("EUW1_1", 100, "scrim"), ("EUW1_2", 200, "official")]) == 2
    assert store.add_team_games(team_id, [("EUW1_1", 200, "official")]) == 0  # bleibt unverändert
    assert store.update_team_game(team_id, "EUW1_1", included=False)
    assert not store.update_team_game(team_id, "EUW1_9", included=False)
    games = {g.match_id: g for g in store.team_games(team_id)}
    assert games["EUW1_1"].side == 100 and not games["EUW1_1"].included

    store.mark_synced(team_id)
    assert store.get_team(team_id).last_synced is not None
    store.delete_team(team_id)
    assert store.get_team(team_id) is None
    assert store.team_games(team_id) == []
