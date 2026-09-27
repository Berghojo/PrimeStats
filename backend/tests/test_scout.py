import time

from primestats.matches import parse_match
from primestats.team_stats import roster_from_games, together_side

from .conftest import other_client


def _wait(client, key):
    for _ in range(200):
        job = client.get(f"/api/scout/{key}/status").json()
        if job and job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("Scouting läuft zu lange")


def _tourney_games_any(demo_source, names):
    puuids = {demo_source.account(f"{n}#EUW")["puuid"] for n in names}
    return {mid for mid, m in demo_source.matches.items() if m["info"].get("tournamentCode")
            and puuids & {p["puuid"] for p in m["info"]["participants"]}}


def _tourney_games_together(demo_source, names):
    """Erwartung aus den Rohdaten: Turnierspiele, in denen alle Spieler im selben Team standen."""
    puuids = [demo_source.account(f"{n}#EUW")["puuid"] for n in names]
    result = set()
    for mid, m in demo_source.matches.items():
        if not m["info"].get("tournamentCode"):
            continue
        teams = {p["puuid"]: p["teamId"] for p in m["info"]["participants"]}
        if all(p in teams for p in puuids) and len({teams[p] for p in puuids}) == 1:
            result.add(mid)
    return result


def test_together_side_and_roster(demo_source):
    mid = next(iter(demo_source.matches))
    match = parse_match(demo_source.matches[mid])
    blue = [p.puuid for p in match.teams[100].players]
    red = [p.puuid for p in match.teams[200].players]
    assert together_side(match, blue[:3]) == 100
    assert together_side(match, [blue[0], red[0]]) is None
    assert together_side(match, [blue[0], "unbekannt"]) is None
    roster = roster_from_games([(match, 100)], [blue[2]])
    assert roster[0]["puuid"] == blue[2] and roster[0]["searched"]
    assert {r["puuid"] for r in roster} == set(blue)


def test_scout_single_player_uses_all_his_games(client, demo_source):
    resp = client.post("/api/scout", json={"riot_ids": ["BSK Skalde#EUW"]})
    assert resp.status_code == 202, resp.text
    key = resp.json()["key"]
    assert _wait(client, key)["status"] == "done"

    report = client.get(f"/api/scout/{key}").json()
    assert [p["game_name"] for p in report["players"]] == ["BSK Skalde"]
    assert {r["match_id"] for r in report["history"]} == _tourney_games_together(demo_source, ["BSK Skalde"])
    assert all(r["tournament"] for r in report["history"])             # nie Scrims
    assert report["roster"][0]["game_name"] == "BSK Skalde" and report["roster"][0]["searched"]
    assert {r["game_name"] for r in report["roster"][1:]} == {"BSK Runenstein", "BSK Wikinger", "BSK Drakkar",
                                                              "BSK Hjalmar"}
    assert report["report"]["champion_table"]
    assert client.get("/api/scout").json()[0]["players"][0]["game_name"] == "BSK Skalde"
    assert other_client(client).get(f"/api/scout/{key}").status_code == 200   # für alle abrufbar


def test_scout_multiple_players_requires_same_team(client, demo_source):
    # Treibholz ersetzt mal Frostbite, mal Polaris – zählen dürfen nur Spiele mit beiden im selben Team
    names = ["NLE Polaris", "NLE Treibholz"]
    expected = _tourney_games_together(demo_source, names)
    only_polaris = _tourney_games_together(demo_source, ["NLE Polaris"])
    assert expected and expected < only_polaris

    key = client.post("/api/scout", json={"riot_ids": [f"{n}#EUW" for n in names]}).json()["key"]
    assert _wait(client, key)["status"] == "done"
    report = client.get(f"/api/scout/{key}").json()
    assert {r["match_id"] for r in report["history"]} == expected
    assert [p["game_name"] for p in report["players"]] == names
    assert [r["searched"] for r in report["roster"][:2]] == [True, True]

    # Reihenfolge der Eingabe spielt für den Schlüssel keine Rolle
    again = client.post("/api/scout", json={"riot_ids": ["NLE Treibholz#EUW", "NLE Polaris#EUW"]}).json()
    assert again["key"] == key


def test_scout_any_mode_uses_games_of_at_least_one_player(client, demo_source):
    names = ["NLE Polaris", "NLE Treibholz"]
    resp = client.post("/api/scout", json={"riot_ids": [f"{n}#EUW" for n in names], "mode": "any"}).json()
    assert resp["mode"] == "any"
    assert _wait(client, resp["key"])["status"] == "done"
    report = client.get(f"/api/scout/{resp['key']}").json()
    assert report["mode"] == "any"
    found = {r["match_id"] for r in report["history"]}
    assert found == _tourney_games_any(demo_source, names)
    assert found > _tourney_games_together(demo_source, names)
    # "all" und "any" sind getrennte Scoutings
    all_key = client.post("/api/scout", json={"riot_ids": [f"{n}#EUW" for n in names]}).json()["key"]
    assert all_key != resp["key"]


def test_scout_any_mode_with_players_on_both_sides(client, demo_source):
    # Polaris und Skalde spielen gegeneinander: Gleichstand -> Seite des zuerst genannten Spielers
    resp = client.post("/api/scout", json={"riot_ids": ["NLE Polaris#EUW", "BSK Skalde#EUW"], "mode": "any"}).json()
    assert _wait(client, resp["key"])["status"] == "done"
    report = client.get(f"/api/scout/{resp['key']}").json()
    polaris = demo_source.account("NLE Polaris#EUW")["puuid"]
    for row in report["history"]:
        teams = {p["puuid"]: p["teamId"] for p in demo_source.matches[row["match_id"]]["info"]["participants"]}
        if polaris in teams:
            assert {"blue": 100, "red": 200}[row["side"]] == teams[polaris]


def test_single_player_ignores_mode(client):
    a = client.post("/api/scout", json={"riot_ids": ["BSK Skalde#EUW"], "mode": "any"}).json()
    b = client.post("/api/scout", json={"riot_ids": ["BSK Skalde#EUW"]}).json()
    assert a["key"] == b["key"] and a["mode"] == "all"


def test_scout_players_never_together(client):
    key = client.post("/api/scout", json={"riot_ids": ["NLE Polaris#EUW", "BSK Skalde#EUW"]}).json()["key"]
    job = _wait(client, key)
    assert job["status"] == "error" and "im selben Team" in job["error"]
    assert client.get(f"/api/scout/{key}").status_code == 404


def test_scout_errors(client, offline_client):
    resp = client.post("/api/scout", json={"riot_ids": ["NLE Polaris#EUW", "Nobody#EUW", "Kaputt"]})
    assert resp.status_code == 422 and len(resp.json()["detail"]["errors"]) == 2
    assert client.post("/api/scout", json={"riot_ids": []}).status_code == 422
    assert client.post("/api/scout", json={"riot_ids": ["a#b"] * 6}).status_code == 422
    assert client.post("/api/scout", json={"riot_ids": ["NLE Polaris#EUW"], "mode": "egal"}).status_code == 422
    key = client.post("/api/scout", json={"riot_ids": ["Kaffeetasse#EUW"]}).json()["key"]
    job = _wait(client, key)
    assert job["status"] == "error" and "keine Turnierspiele" in job["error"]
    assert client.get("/api/scout/unbekannt").status_code == 404
    assert offline_client.post("/api/scout", json={"riot_ids": ["NLE Polaris#EUW"]}).status_code == 503


def test_scout_finds_games_missing_from_the_players_own_list(store, demo_source):
    """Riot-Listen einzelner Spieler sind unvollständig: Spiele aus den Listen der Mitspieler ergänzen."""
    from primestats.services import PrimeStats, SyncJob

    polaris = demo_source.account("NLE Polaris#EUW")
    expected = _tourney_games_together(demo_source, ["NLE Polaris"])
    hidden = sorted(expected)[:3]

    class GappyList:
        def __getattr__(self, name):
            return getattr(demo_source, name)

        def match_ids(self, puuid, count=20, **kw):
            ids = demo_source.match_ids(puuid, count, **kw)
            return [m for m in ids if not (puuid == polaris["puuid"] and m in hidden)]

    svc = PrimeStats(store, GappyList())
    key = svc.scout([polaris], SyncJob("t"))
    found = {mid for mid, _ in store.get_scout(key)["games"]}
    assert found == expected                        # auch die 3 in der eigenen Liste fehlenden Spiele
    games = store.get_scout(key)["games"]
    assert [g[0] for g in games] == sorted((g[0] for g in games), reverse=True)


def test_report_narrows_to_selected_players(client, demo_source):
    # Suche nach Polaris und Ersatzspieler Treibholz einzeln (Vereinigung), danach im Report auswählen
    names = ["NLE Polaris", "NLE Treibholz"]
    resp = client.post("/api/scout", json={"riot_ids": [f"{n}#EUW" for n in names], "mode": "any"}).json()
    assert _wait(client, resp["key"])["status"] == "done"
    url = f"/api/scout/{resp['key']}"
    polaris, treibholz = (demo_source.account(f"{n}#EUW")["puuid"] for n in names)

    def games(**params):
        report = client.get(url, params=params).json()
        return report, {r["match_id"] for r in report["history"]}

    report, everything = games()
    assert report["focus"] == [] and report["match"] == "any"
    _, only_polaris = games(focus=[polaris])
    assert only_polaris == _tourney_games_any(demo_source, ["NLE Polaris"]) & everything
    _, both = games(focus=[polaris, treibholz], match="all")
    assert both == _tourney_games_together(demo_source, names)
    report, either = games(focus=[polaris, treibholz], match="any")
    assert either == everything and report["match"] == "any"
    assert report["report"]["overview"]["games"] == len(either)

    # unbekannte Spieler werden ignoriert, mehr als fünf abgelehnt
    report, _ = games(focus=["unbekannt"])
    assert report["focus"] == []
    assert client.get(url, params={"focus": [polaris] * 6}).status_code == 422
