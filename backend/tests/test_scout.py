import time

from primestats.matches import parse_match
from primestats.team_stats import infer_roster

from .conftest import other_client


def _wait(client, puuid):
    for _ in range(200):
        job = client.get(f"/api/scout/{puuid}/status").json()
        if job and job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("Scouting läuft zu lange")


def test_infer_roster_from_player_games(demo_source):
    polaris = demo_source.account("NLE Polaris#EUW")["puuid"]
    matches = [parse_match(demo_source.matches[mid]) for mid in demo_source.by_puuid[polaris]]
    roster = infer_roster(matches, polaris)
    names = [r["game_name"] for r in roster]
    assert names[0] == "NLE Polaris"
    assert set(names) >= {"NLE Frostbite", "NLE Waldgeist", "NLE Kompass", "NLE Leuchtturm"}
    assert all(not n.startswith(("RHW", "BSK", "ALP", "HFK")) for n in names)   # Gegner gehören nicht dazu
    assert not any(n in {"Kaffeetasse", "Blitzbirne"} for n in names)          # Zufallsbekanntschaften auch nicht
    assert roster[0]["position"] == "MIDDLE"


def test_infer_roster_single_game(demo_source):
    mid = next(iter(demo_source.matches))
    match = parse_match(demo_source.matches[mid])
    player = match.teams[100].players[0]
    assert len(infer_roster([match], player.puuid)) == 5
    assert infer_roster([match], "unbekannt") == []


def test_scout_opponent_from_single_player(client, demo_source):
    # anonym, ohne Konto: nur einen Spieler des Gegners eingeben
    resp = client.post("/api/scout", json={"riot_id": "BSK Skalde#EUW"})
    assert resp.status_code == 202, resp.text
    puuid = resp.json()["puuid"]
    job = _wait(client, puuid)
    assert job["status"] == "done", job

    report = client.get(f"/api/scout/{puuid}").json()
    assert report["player"]["game_name"] == "BSK Skalde"     # alles läuft unter dem gesuchten Spieler
    assert "team_tag" not in report and "opponents" not in report
    assert {r["game_name"] for r in report["roster"]} == {f"BSK {n}" for n in
                                                          ("Runenstein", "Wikinger", "Skalde", "Drakkar", "Hjalmar")}
    assert report["report"]["overview"]["games"] == len(report["history"]) > 0
    # nur öffentliche Turnierspiele, keine Scrims
    assert all(r["tournament"] for r in report["history"])
    assert report["report"]["enemy_bans"] or report["report"]["our_bans"]
    assert client.get(f"/api/scout/{puuid}", params={"side": "blue"}).json()["filters"]["side"] == "blue"

    # erscheint in der Liste der letzten Scoutings und ist für alle abrufbar
    assert client.get("/api/scout").json()[0]["game_name"] == "BSK Skalde"
    assert other_client(client).get(f"/api/scout/{puuid}").status_code == 200


def test_scout_finds_games_without_the_searched_player(client, demo_source):
    # Polaris wurde in einigen Turnierspielen durch Treibholz ersetzt – das Scouting findet sie trotzdem
    polaris = demo_source.account("NLE Polaris#EUW")["puuid"]
    own = {m for m in demo_source.by_puuid[polaris] if demo_source.matches[m]["info"].get("tournamentCode")}
    team = {m for m, d in demo_source.matches.items() if d["info"].get("tournamentCode")
            and any(p["riotIdGameName"].startswith("NLE") for p in d["info"]["participants"])}
    assert team - own, "Demo-Daten sollten Turnierspiele ohne Polaris enthalten"

    puuid = client.post("/api/scout", json={"riot_id": "NLE Polaris#EUW"}).json()["puuid"]
    assert _wait(client, puuid)["status"] == "done"
    found = {r["match_id"] for r in client.get(f"/api/scout/{puuid}").json()["history"]}
    assert found == team


def test_scout_errors(client, offline_client):
    assert client.post("/api/scout", json={"riot_id": "Nobody#EUW"}).status_code == 404
    # Spieler ohne Turnierspiele: Job endet mit verständlicher Meldung
    puuid = client.post("/api/scout", json={"riot_id": "Kaffeetasse#EUW"}).json()["puuid"]
    job = _wait(client, puuid)
    assert job["status"] == "error" and "keine Turnierspiele" in job["error"]
    assert client.post("/api/scout", json={"riot_id": "Kaputt"}).status_code == 400
    assert client.get("/api/scout/unbekannt").status_code == 404
    assert offline_client.post("/api/scout", json={"riot_id": "NLE Polaris#EUW"}).status_code == 503
