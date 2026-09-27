import time

from .conftest import other_client, register

NLE = ("Frostbite", "Waldgeist", "Polaris", "Kompass", "Leuchtturm")


def _wait(client, url):
    for _ in range(300):
        job = client.get(url).json()
        if job and job["status"] != "running":
            return
        time.sleep(0.05)


def _team(client, public=True) -> int:
    body = {"name": "Nordlicht", "tag": "NLE", "min_members": 4, "public": public,
            "members": [{"riot_id": f"NLE {n}#EUW"} for n in NLE]}
    team_id = client.post("/api/teams", json=body).json()["id"]
    client.post(f"/api/teams/{team_id}/sync")
    _wait(client, f"/api/teams/{team_id}/sync")
    return team_id


def _scout(client, riot_id="BSK Skalde#EUW") -> str:
    key = client.post("/api/scout", json={"riot_ids": [riot_id]}).json()["key"]
    _wait(client, f"/api/scout/{key}/status")
    return key


def test_group_crud_and_compare(client, imported):
    assert client.post("/api/groups", json={"name": "Liga"}).status_code == 401
    register(client, "chef")
    team_id = _team(client)
    key = _scout(client)
    entries = [{"kind": "team", "ref": str(team_id)}, {"kind": "scout", "ref": key, "name": "Berserker"},
               {"kind": "team", "ref": str(team_id)}]
    resp = client.post("/api/groups", json={"name": " Gruppe A ", "entries": entries})
    assert resp.status_code == 201, resp.text
    group = resp.json()
    assert group["name"] == "Gruppe A" and group["can_edit"]
    assert [(e["kind"], e["title"]) for e in group["entries"]] == [("team", "Nordlicht"), ("scout", "Berserker")]
    assert [g["teams"] for g in client.get("/api/groups").json()] == [["Nordlicht", "Berserker"]]

    cmp = client.get(f"/api/groups/{group['key']}/compare").json()
    nle, bsk = cmp["teams"]
    assert nle["overview"]["games"] > 0 and bsk["overview"]["games"] > 0
    assert any(p["name"] == "NLE Polaris" for p in nle["players"])
    assert all(len(p["champions"]) <= 3 for p in nle["players"])
    assert cmp["patches"]
    # nur Turnierspiele: Scrims des Teams zählen nicht
    records = imported.team_records(imported.store.get_team(team_id), with_timeline=False)
    official = [r for r in records if r.match.tournament_code]
    assert len(official) < len(records) and nle["overview"]["games"] == len(official)
    last2 = client.get(f"/api/groups/{group['key']}/compare", params={"last": 2}).json()
    assert last2["teams"][0]["overview"]["games"] == 2

    # Ungültige Einträge
    assert client.post("/api/groups", json={"name": "x", "entries": [{"kind": "team", "ref": key}]}).status_code == 422
    assert client.post("/api/groups", json={"name": "x", "entries": [{"kind": "scout", "ref": "1"}]}).status_code == 422

    # Andere sehen die Gruppe per Link, dürfen sie aber nicht ändern
    other = other_client(client)
    shared = other.get(f"/api/groups/{group['key']}").json()
    assert shared["can_edit"] is False and len(shared["entries"]) == 2
    register(other, "gast")
    assert other.get("/api/groups").json() == []
    assert other.patch(f"/api/groups/{group['key']}", json={"name": "fremd"}).status_code == 404
    assert other.delete(f"/api/groups/{group['key']}").status_code == 404

    added = client.post(f"/api/groups/{group['key']}/entries", json={"kind": "scout", "ref": key}).json()
    assert len(added["entries"]) == 2  # schon enthalten
    assert other.post(f"/api/groups/{group['key']}/entries", json={"kind": "scout", "ref": key}).status_code == 404

    changed = client.patch(f"/api/groups/{group['key']}", json={"entries": entries[1:2]}).json()
    assert [e["title"] for e in changed["entries"]] == ["Berserker"] and changed["name"] == "Gruppe A"
    assert client.delete(f"/api/groups/{group['key']}").status_code == 204
    assert client.get(f"/api/groups/{group['key']}").status_code == 404


def test_private_team_hidden_in_shared_group(client):
    register(client, "chef")
    team_id = _team(client, public=False)
    group = client.post("/api/groups", json={"name": "G", "entries": [{"kind": "team", "ref": str(team_id)}]}).json()
    other = other_client(client)
    cmp = other.get(f"/api/groups/{group['key']}/compare").json()
    (entry,) = cmp["teams"]
    assert entry["entry"]["available"] is False and entry["overview"] is None and entry["players"] == []
    assert entry["entry"]["title"] == "Team nicht verfügbar"
