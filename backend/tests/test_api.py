import time

from .conftest import link_riot, other_client, register

TEAM = {
    "name": "Nordlicht Esports", "tag": "NLE", "min_members": 4,
    "members": [{"riot_id": f"{n}#EUW", "role": r} for n, r in (
        ("NLE Frostbite", "TOP"), ("NLE Waldgeist", "JUNGLE"), ("NLE Polaris", "MIDDLE"),
        ("NLE Kompass", "BOTTOM"), ("NLE Leuchtturm", "UTILITY"), ("NLE Treibholz", ""))],
}


def _create_team(client, **overrides):
    return client.post("/api/teams", json={**TEAM, **overrides})


def _wait_for_sync(client, tid):
    job = client.post(f"/api/teams/{tid}/sync").json()
    for _ in range(200):
        if job["status"] != "running":
            break
        time.sleep(0.05)
        job = client.get(f"/api/teams/{tid}/sync").json()
    assert job["status"] == "done", job
    return job


def test_meta(client):
    data = client.get("/api/meta").json()
    assert data["demo"] is True and data["configured"] is True
    assert data["champions"]["266"]["id"] == "Aatrox"
    assert data["positions"]["BOTTOM"] == "ADC"


def test_scrims_only_visible_to_team_players(client, demo_source):
    anon = client.get("/api/players/NLE Polaris/EUW/games", params={"count": 60}).json()
    assert anon["account"]["game_name"] == "NLE Polaris"
    assert anon["games"] and all(g["tournament_code"] for g in anon["games"])

    # verknüpft, aber (noch) in keinem Team -> weiterhin keine Scrims
    register(client)
    link_riot(client, demo_source.account("NLE Polaris#EUW"))
    alone = client.get("/api/players/NLE Polaris/EUW/games", params={"count": 60}).json()
    assert len(alone["games"]) == len(anon["games"])

    # Team mit Polaris im Kader -> Scrims des Teams sichtbar
    tid = _create_team(client).json()["id"]
    _wait_for_sync(client, tid)
    own = client.get("/api/players/NLE Polaris/EUW/games", params={"count": 60}).json()
    assert len(own["games"]) > len(anon["games"])
    scrim = next(g for g in own["games"] if not g["tournament_code"])
    assert client.get(f"/api/matches/{scrim['match_id']}").status_code == 200
    assert other_client(client).get(f"/api/matches/{scrim['match_id']}").status_code == 404

    ids = [g["match_id"] for g in own["games"][:3]]
    resp = client.get("/api/analysis", params={"m": ids, "focus": own["account"]["puuid"]})
    assert resp.status_code == 200
    analysis = resp.json()
    assert analysis["players"][0]["focus"] is True and len(analysis["matches"]) == 3
    assert "gold_diff" in analysis["series"]
    assert other_client(client).get("/api/analysis", params={"m": [scrim["match_id"]]}).status_code == 404


def test_player_errors(client):
    assert client.get("/api/players/Nobody/EUW/games").status_code == 404
    assert client.get("/api/players/Name/TOOLONG/games").status_code == 400
    assert client.get("/api/analysis").status_code == 422
    assert client.get("/api/matches/EUW1_1").status_code == 404


def test_team_lifecycle(client, demo_source):
    assert _create_team(client).status_code == 401  # nur angemeldet
    register(client, "kapitaen")
    resp = _create_team(client)
    assert resp.status_code == 201, resp.text
    team = resp.json()
    tid = team["id"]
    assert team["can_edit"] and team["can_delete"] and team["public"] is False
    assert team["can_see_scrims"] is False   # Ersteller ohne verknüpften Account im Kader
    assert [t["id"] for t in client.get("/api/teams").json()] == [tid]

    report = client.get(f"/api/teams/{tid}/report").json()
    assert report["history"] == [] and report["report"]["overview"]["games"] == 0

    _wait_for_sync(client, tid)
    only_official = client.get(f"/api/teams/{tid}/report").json()
    assert {r["label"] for r in only_official["history"]} == {"official"}

    link_riot(client, demo_source.account("NLE Polaris#EUW"))
    report = client.get(f"/api/teams/{tid}/report").json()
    assert report["team"]["can_see_scrims"] is True
    ov = report["report"]["overview"]
    assert ov["games"] == len(report["history"]) > len(only_official["history"])
    assert {r["label"] for r in report["history"]} == {"official", "scrim"}
    assert report["team"]["last_synced"] is not None
    assert all(row["selected"] for row in report["history"])

    filtered = client.get(f"/api/teams/{tid}/report", params={"label": "official", "side": "blue", "last": 3}).json()
    assert filtered["filters"] == {"label": "official", "side": "blue", "patch": "", "opponent": "", "last": 3}
    assert filtered["report"]["overview"]["games"] <= 3

    mid = report["history"][0]["match_id"]
    assert client.patch(f"/api/teams/{tid}/games/{mid}", json={"included": False, "label": "scrim"}).status_code == 204
    after = client.get(f"/api/teams/{tid}/report").json()
    assert after["report"]["overview"]["games"] == ov["games"] - 1
    row = next(r for r in after["history"] if r["match_id"] == mid)
    assert row["label"] == "scrim" and not row["included"]
    assert client.patch(f"/api/teams/{tid}/games/EUW1_0", json={"included": False}).status_code == 404

    resp = client.put(f"/api/teams/{tid}", json={"name": "NLE", "tag": "N", "min_members": 5, "public": True,
                                                  "members": [{"riot_id": "NLE Polaris#EUW"}]})
    assert resp.status_code == 200 and resp.json()["min_members"] == 5 and resp.json()["public"]
    assert client.delete(f"/api/teams/{tid}").status_code == 204
    assert client.get(f"/api/teams/{tid}").status_code == 404


def test_team_permissions(client, demo_source):
    register(client, "kapitaen")
    link_riot(client, demo_source.account("NLE Polaris#EUW"))
    tid = _create_team(client).json()["id"]
    _wait_for_sync(client, tid)
    scrim = next(r for r in client.get(f"/api/teams/{tid}/report").json()["history"] if r["label"] == "scrim")

    stranger = other_client(client)
    assert stranger.get(f"/api/teams/{tid}").status_code == 404          # privat -> unsichtbar
    assert stranger.get("/api/teams").json() == []
    register(stranger, "fremder")
    assert stranger.get(f"/api/teams/{tid}/report").status_code == 404
    assert stranger.get(f"/api/matches/{scrim['match_id']}").status_code == 404

    # Kader-Mitglied mit verknüpftem Account darf sehen (inkl. Scrims) und bearbeiten, aber nicht löschen
    link_riot(stranger, demo_source.account("NLE Kompass#EUW"))
    team = stranger.get(f"/api/teams/{tid}").json()
    assert team["can_edit"] and team["can_see_scrims"] and not team["can_delete"]
    assert stranger.get(f"/api/matches/{scrim['match_id']}").status_code == 200
    assert stranger.patch(f"/api/teams/{tid}/games/{scrim['match_id']}", json={"label": "official"}).status_code == 204
    assert stranger.delete(f"/api/teams/{tid}").status_code == 403

    # öffentliches Team: alle sehen die Turnierspiele, aber keine Scrims und dürfen nichts ändern
    client.put(f"/api/teams/{tid}", json={**TEAM, "public": True})
    anon = other_client(client)
    public = anon.get(f"/api/teams/{tid}/report").json()
    assert public["history"] and all(r["tournament"] for r in public["history"])
    assert public["team"]["can_see_scrims"] is False
    assert anon.get(f"/api/matches/{scrim['match_id']}").status_code == 404
    assert anon.post(f"/api/teams/{tid}/sync").status_code == 403
    assert anon.put(f"/api/teams/{tid}", json=TEAM).status_code == 403

    # Trick verhindert: fremdes Team mit denselben Riot-IDs anlegen verrät keine Scrims
    spy = other_client(client)
    register(spy, "spion")
    spy_tid = spy.post("/api/teams", json={**TEAM, "name": "Kopie"}).json()["id"]
    _wait_for_sync(spy, spy_tid)
    copied = spy.get(f"/api/teams/{spy_tid}/report").json()
    assert copied["history"] and all(r["tournament"] for r in copied["history"])
    assert spy.get(f"/api/matches/{scrim['match_id']}").status_code == 404


def test_team_validation(client):
    register(client)
    resp = _create_team(client, members=[{"riot_id": "Nobody#EUW"}])
    assert resp.status_code == 422
    assert "nicht gefunden" in resp.json()["detail"]["errors"][0]
    assert _create_team(client, name="").status_code == 422
    assert _create_team(client, min_members=9).status_code == 422


def test_csrf_header_required(client):
    from fastapi.testclient import TestClient
    bare = TestClient(client.app)
    resp = bare.post("/api/auth/register", json={"username": "x" * 5, "password": "geheim123"})
    assert resp.status_code == 403
