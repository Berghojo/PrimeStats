from primestats.demo import to_lcu

from .conftest import UPLOAD_TOKEN

AUTH = {"Authorization": f"Bearer {UPLOAD_TOKEN}", "X-Uploader": "NLE Polaris"}
TEAM = {
    "name": "Nordlicht Esports", "tag": "NLE", "min_members": 4,
    "members": [{"riot_id": f"NLE {n}#EUW"} for n in ("Frostbite", "Waldgeist", "Polaris", "Kompass", "Leuchtturm")],
}


def _scrims(demo_source, n=3):
    ids = [mid for mid, m in demo_source.matches.items() if not m["info"].get("tournamentCode")][:n]
    return ids, [to_lcu(demo_source.matches[i], demo_source.timelines[i]) for i in ids]


def test_upload_requires_token(client, demo_source):
    _, items = _scrims(demo_source, 1)
    assert client.post("/api/import/lcu", json={"games": items}).status_code == 401
    assert client.post("/api/import/lcu", json={"games": items},
                       headers={"Authorization": "Bearer falsch"}).status_code == 401
    assert client.post("/api/import/known", json={"match_ids": []}, headers=AUTH).status_code == 200


def test_uploads_disabled_without_token(offline_client):
    offline_client.app.state.settings.upload_token = ""
    resp = offline_client.post("/api/import/known", json={"match_ids": []}, headers=AUTH)
    assert resp.status_code == 403


def test_import_flow_offline(offline_client, demo_source):
    """Ohne Riot-API-Key: Upload -> Team anlegen (Spieler aus Uploads bekannt) -> Sync -> Statistik."""
    c = offline_client
    assert c.get("/api/meta").json()["configured"] is False
    ids, items = _scrims(demo_source, 40)

    assert c.post("/api/import/known", json={"match_ids": ids}, headers=AUTH).json()["known"] == []
    result = c.post("/api/import/lcu", json={"games": items[:10]}, headers=AUTH).json()
    assert sorted(result["imported"]) == sorted(ids[:10]) and result["errors"] == []
    assert sorted(c.post("/api/import/known", json={"match_ids": ids}, headers=AUTH).json()["known"]) == sorted(ids[:10])

    # erneuter Upload: nichts Neues
    again = c.post("/api/import/lcu", json={"games": items[:10]}, headers=AUTH).json()
    assert again["imported"] == [] and len(again["skipped"]) == 10

    # Team anlegen funktioniert ohne API-Key, weil die Spieler aus den Uploads bekannt sind
    resp = c.post("/api/teams", json=TEAM)
    assert resp.status_code == 201, resp.text
    tid = resp.json()["id"]
    job = c.post(f"/api/teams/{tid}/sync").json()
    import time
    while job and job["status"] == "running":
        time.sleep(0.05)
        job = c.get(f"/api/teams/{tid}/sync").json()
    assert job["status"] == "done", job
    report = c.get(f"/api/teams/{tid}/report").json()
    n_team = len(report["history"])
    assert n_team > 0 and all(r["label"] == "scrim" for r in report["history"])
    assert report["report"]["overview"]["timeline_games"] == n_team

    # weitere Uploads werden bestehenden Teams automatisch zugeordnet
    result = c.post("/api/import/lcu", json={"games": items[10:40]}, headers=AUTH).json()
    assert result["imported"]
    assert result["assigned"].get("Nordlicht Esports", 0) > 0
    report = c.get(f"/api/teams/{tid}/report").json()
    assert len(report["history"]) == n_team + result["assigned"]["Nordlicht Esports"]

    # Spielersuche liefert hochgeladene Spiele
    games = c.get("/api/players/NLE Polaris/EUW/games").json()["games"]
    assert games and all(g["match_id"] in ids for g in games)
    assert c.get("/api/players/Unbekannt/EUW/games").status_code == 404


def test_timeline_can_be_added_later(client, demo_source):
    ids, items = _scrims(demo_source, 1)
    # Die Demo-Scrims sind im client-Fixture schon importiert -> vorhandenes Spiel wird übersprungen
    result = client.post("/api/import/lcu", json={"games": items}, headers=AUTH).json()
    assert result["skipped"] == ids


def test_invalid_games_are_reported(client):
    result = client.post("/api/import/lcu", json={"games": [{"game": {"gameId": 5}}]}, headers=AUTH).json()
    assert result["imported"] == [] and len(result["errors"]) == 1


def test_timeline_added_to_existing_match(service, demo_source):
    ids, items = _scrims(demo_source, 1)
    without = [{"game": items[0]["game"], "timeline": None}]
    assert service.import_lcu(without).imported == ids
    assert service.store.get_timeline(ids[0]) is None
    assert service.import_lcu(items).updated == ids
    assert service.store.get_timeline(ids[0]) is not None
