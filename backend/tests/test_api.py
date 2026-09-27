def _create_team(client, **overrides):
    body = {
        "name": "Nordlicht Esports", "tag": "NLE", "min_members": 4,
        "members": [{"riot_id": f"{n}#EUW", "role": r} for n, r in (
            ("NLE Frostbite", "TOP"), ("NLE Waldgeist", "JUNGLE"), ("NLE Polaris", "MIDDLE"),
            ("NLE Kompass", "BOTTOM"), ("NLE Leuchtturm", "UTILITY"), ("NLE Treibholz", ""))],
    }
    body.update(overrides)
    return client.post("/api/teams", json=body)


def test_meta(client):
    data = client.get("/api/meta").json()
    assert data["demo"] is True and data["configured"] is True
    assert data["champions"]["266"]["id"] == "Aatrox"
    assert data["positions"]["BOTTOM"] == "ADC"


def test_player_games_and_analysis(client):
    resp = client.get("/api/players/NLE Polaris/EUW/games", params={"count": 20})
    assert resp.status_code == 200
    data = resp.json()
    assert data["account"]["game_name"] == "NLE Polaris"
    assert len(data["games"]) == 20
    game = data["games"][0]
    assert game["blue"]["side"] == "blue" and len(game["blue"]["players"]) == 5

    ids = [g["match_id"] for g in data["games"][:3]]
    resp = client.get("/api/analysis", params={"m": ids, "focus": data["account"]["puuid"]})
    assert resp.status_code == 200
    analysis = resp.json()
    assert analysis["players"][0]["focus"] is True
    assert len(analysis["matches"]) == 3
    assert "gold_diff" in analysis["series"]


def test_player_errors(client):
    assert client.get("/api/players/Nobody/EUW/games").status_code == 404
    assert client.get("/api/players/Name/TOOLONG/games").status_code == 400
    assert client.get("/api/analysis").status_code == 422
    assert client.get("/api/matches/EUW1_1").status_code == 404


def test_team_lifecycle(client):
    resp = _create_team(client)
    assert resp.status_code == 201, resp.text
    team = resp.json()
    tid = team["id"]
    assert len(team["members"]) == 6
    assert client.get("/api/teams").json()[0]["id"] == tid

    report = client.get(f"/api/teams/{tid}/report").json()
    assert report["history"] == [] and report["report"]["overview"]["games"] == 0

    job = client.post(f"/api/teams/{tid}/sync").json()
    assert job["status"] in {"running", "done"}
    client.app.state.service.jobs._jobs[tid]  # Job existiert
    # auf den Hintergrund-Thread warten
    import time
    for _ in range(100):
        job = client.get(f"/api/teams/{tid}/sync").json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "done", job

    report = client.get(f"/api/teams/{tid}/report").json()
    ov = report["report"]["overview"]
    assert ov["games"] == len(report["history"]) > 20
    assert ov["wins"] + ov["losses"] == ov["games"]
    assert report["team"]["last_synced"] is not None
    assert all(row["selected"] for row in report["history"])

    filtered = client.get(f"/api/teams/{tid}/report", params={"label": "official", "side": "blue", "last": 3}).json()
    assert filtered["filters"] == {"label": "official", "side": "blue", "patch": "", "opponent": "", "last": 3}
    assert filtered["report"]["overview"]["games"] <= 3
    assert sum(r["selected"] for r in filtered["history"]) == filtered["report"]["overview"]["games"]

    mid = report["history"][0]["match_id"]
    assert client.patch(f"/api/teams/{tid}/games/{mid}", json={"included": False, "label": "scrim"}).status_code == 204
    after = client.get(f"/api/teams/{tid}/report").json()
    assert after["report"]["overview"]["games"] == ov["games"] - 1
    row = next(r for r in after["history"] if r["match_id"] == mid)
    assert row["label"] == "scrim" and not row["included"]
    assert client.patch(f"/api/teams/{tid}/games/EUW1_0", json={"included": False}).status_code == 404

    assert client.get(f"/api/matches/{mid}").json()["match_id"] == mid

    resp = client.put(f"/api/teams/{tid}", json={"name": "NLE", "tag": "N", "min_members": 5,
                                                   "members": [{"riot_id": "NLE Polaris#EUW"}]})
    assert resp.status_code == 200 and resp.json()["min_members"] == 5
    assert client.delete(f"/api/teams/{tid}").status_code == 204
    assert client.get(f"/api/teams/{tid}").status_code == 404


def test_team_validation(client):
    resp = _create_team(client, members=[{"riot_id": "Nobody#EUW"}])
    assert resp.status_code == 422
    assert "nicht gefunden" in resp.json()["detail"]["errors"][0]
    assert _create_team(client, name="").status_code == 422
    assert _create_team(client, min_members=9).status_code == 422


def test_without_source_returns_503(store, tmp_path):
    from fastapi.testclient import TestClient

    from primestats.app import create_app
    from primestats.config import Settings
    app = create_app(Settings(demo=False, api_key=None, ddragon_fetch=False, cache_dir=tmp_path,
                              auto_migrate=False), store=store)
    with TestClient(app) as client:
        assert client.get("/api/meta").json()["configured"] is False
        assert client.get("/api/teams").status_code == 503
