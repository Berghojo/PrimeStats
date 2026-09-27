import time

from .conftest import link_riot, other_client, register


def _sync(client, name="NLE Polaris", tag="EUW"):
    resp = client.post(f"/api/players/{name}/{tag}/sync")
    assert resp.status_code == 202, resp.text
    for _ in range(200):
        job = client.get(f"/api/players/{name}/{tag}/sync").json()
        if job and job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("Laden hängt")


def test_player_report_over_queues(client, demo_source):
    assert _sync(client)["status"] == "done"
    polaris = demo_source.account("NLE Polaris#EUW")["puuid"]
    data = client.get("/api/players/NLE Polaris/EUW/report").json()
    counts = data["queue_counts"]
    assert counts["solo"] == len(demo_source.match_ids(polaris, 50, queue=420))
    assert counts["flex"] == len(demo_source.match_ids(polaris, 50, queue=440))
    assert counts["tourney"] == len(demo_source.match_ids(polaris, 50, type="tourney"))
    report = data["report"]
    assert report["overview"]["games"] == len(report["history"]) == sum(counts.values()) - counts.get("scrim", 0)
    assert {q["key"] for q in report["queues"]} == {"solo", "flex", "tourney"}
    assert report["champions"] and report["champions"][0]["games"] >= report["champions"][-1]["games"]
    assert report["roles"][0]["key"] == "MIDDLE"
    assert all(d["puuid"] == polaris for d in report["deaths"])
    assert all(any(b["puuid"] == polaris for b in k["by"]) for k in report["kills"])

    solo = client.get("/api/players/NLE Polaris/EUW/report", params={"queue": ["solo"]}).json()["report"]
    assert {g["queue"] for g in solo["history"]} == {"solo"}
    champ = report["champions"][0]["champion_id"]
    only = client.get("/api/players/NLE Polaris/EUW/report", params={"champion": champ, "last": 3}).json()["report"]
    assert {g["champion_id"] for g in only["history"]} == {champ} and len(only["history"]) <= 3


def test_scrims_only_for_roster_members(client, demo_source):
    # Scrims sind hochgeladene Spiele; ohne Kaderzugehörigkeit tauchen sie nicht auf
    anonymous = client.get("/api/players/NLE Polaris/EUW/report").json()
    assert "scrim" not in anonymous["queue_counts"]
    member = other_client(client)
    register(member, "polaris")
    link_riot(member, demo_source.account("NLE Polaris#EUW"))
    team = {"name": "NLE", "tag": "NLE", "min_members": 4,
            "members": [{"riot_id": f"NLE {n}#EUW"} for n in ("Frostbite", "Waldgeist", "Polaris", "Kompass", "Leuchtturm")]}
    team_id = member.post("/api/teams", json=team).json()["id"]
    member.post(f"/api/teams/{team_id}/sync")
    for _ in range(200):
        job = member.get(f"/api/teams/{team_id}/sync").json()
        if job and job["status"] != "running":
            break
        time.sleep(0.05)
    seen = member.get("/api/players/NLE Polaris/EUW/report").json()
    assert seen["queue_counts"].get("scrim", 0) > 0


def test_unknown_player_and_offline(client, offline_client):
    assert client.get("/api/players/Niemand/XYZ/report").status_code == 404
    assert offline_client.post("/api/players/NLE Polaris/EUW/sync").status_code in (503, 404)
