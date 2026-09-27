import time

from primestats.demo import to_lcu

from .conftest import link_riot, register

TEAM = {
    "name": "Nordlicht Esports", "tag": "NLE", "min_members": 4,
    "members": [{"riot_id": f"NLE {n}#EUW"} for n in ("Frostbite", "Waldgeist", "Polaris", "Kompass", "Leuchtturm")],
}


def _scrims(demo_source, puuid=None, n=3):
    ids = [mid for mid, m in demo_source.matches.items() if not m["info"].get("tournamentCode")
           and (puuid is None or puuid in m["metadata"]["participants"])][:n]
    return ids, [to_lcu(demo_source.matches[i], demo_source.timelines[i]) for i in ids]


def _headers(account, key):
    return {"X-Riot-Puuid": account["puuid"], "X-Link-Key": key}


def test_upload_requires_linked_account(offline_client, demo_source):
    c = offline_client
    polaris = demo_source.account("NLE Polaris#EUW")
    _, items = _scrims(demo_source, polaris["puuid"], 1)
    assert c.post("/api/uploader/games", json={"games": items}).status_code == 401
    assert c.post("/api/uploader/games", json={"games": items},
                  headers=_headers(polaris, "geraten")).status_code == 401
    register(c)
    key = link_riot(c, polaris)
    assert c.post("/api/uploader/known", json={"match_ids": []}, headers=_headers(polaris, key)).status_code == 200


def test_only_own_games_are_accepted(offline_client, demo_source):
    c = offline_client
    polaris = demo_source.account("NLE Polaris#EUW")
    register(c)
    key = link_riot(c, polaris)
    foreign = [mid for mid, m in demo_source.matches.items() if polaris["puuid"] not in m["metadata"]["participants"]][:1]
    items = [to_lcu(demo_source.matches[foreign[0]])]
    result = c.post("/api/uploader/games", json={"games": items}, headers=_headers(polaris, key)).json()
    assert result["imported"] == [] and "mitgespielt" in result["errors"][0]


def test_import_flow_offline(offline_client, demo_source):
    """Ohne Riot-API-Key: Konto + Verknüpfung -> Upload -> Team -> Sync -> Statistik."""
    c = offline_client
    assert c.get("/api/meta").json()["configured"] is False
    polaris = demo_source.account("NLE Polaris#EUW")
    register(c, "polaris")
    key = link_riot(c, polaris)
    h = _headers(polaris, key)
    ids, items = _scrims(demo_source, polaris["puuid"], 40)

    assert c.post("/api/uploader/known", json={"match_ids": ids}, headers=h).json()["known"] == []
    result = c.post("/api/uploader/games", json={"games": items[:10]}, headers=h).json()
    assert sorted(result["imported"]) == sorted(ids[:10]) and result["errors"] == []
    assert sorted(c.post("/api/uploader/known", json={"match_ids": ids}, headers=h).json()["known"]) == sorted(ids[:10])
    again = c.post("/api/uploader/games", json={"games": items[:10]}, headers=h).json()
    assert again["imported"] == [] and len(again["skipped"]) == 10
    assert c.get("/api/auth/me").json()["riot_accounts"][0]["last_upload_at"] is not None

    # Team anlegen funktioniert ohne API-Key, weil die Spieler aus den Uploads bekannt sind
    resp = c.post("/api/teams", json=TEAM)
    assert resp.status_code == 201, resp.text
    tid = resp.json()["id"]
    job = c.post(f"/api/teams/{tid}/sync").json()
    while job and job["status"] == "running":
        time.sleep(0.05)
        job = c.get(f"/api/teams/{tid}/sync").json()
    assert job["status"] == "done", job
    report = c.get(f"/api/teams/{tid}/report").json()
    n_team = len(report["history"])
    assert n_team > 0 and all(r["label"] == "scrim" for r in report["history"])
    assert report["report"]["overview"]["timeline_games"] == n_team

    # weitere Uploads werden bestehenden Teams automatisch zugeordnet
    result = c.post("/api/uploader/games", json={"games": items[10:40]}, headers=h).json()
    assert result["imported"] and result["assigned"].get("Nordlicht Esports", 0) > 0
    report = c.get(f"/api/teams/{tid}/report").json()
    assert len(report["history"]) == n_team + result["assigned"]["Nordlicht Esports"]

    games = c.get("/api/players/NLE Polaris/EUW/games").json()["games"]
    assert games and all(g["match_id"] in ids for g in games)
    assert c.get("/api/players/Unbekannt/EUW/games").status_code == 404


def test_invalid_games_are_reported(offline_client, demo_source):
    polaris = demo_source.account("NLE Polaris#EUW")
    register(offline_client)
    key = link_riot(offline_client, polaris)
    result = offline_client.post("/api/uploader/games", json={"games": [{"game": {"gameId": 5}}]},
                                 headers=_headers(polaris, key)).json()
    assert result["imported"] == [] and len(result["errors"]) == 1


def test_timeline_added_to_existing_match(service, demo_source):
    ids, items = _scrims(demo_source, n=1)
    without = [{"game": items[0]["game"], "timeline": None}]
    assert service.import_lcu(without).imported == ids
    assert service.store.get_timeline(ids[0]) is None
    assert service.import_lcu(items).updated == ids
    assert service.store.get_timeline(ids[0]) is not None
