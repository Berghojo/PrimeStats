from .conftest import other_client, register


def test_saved_views_per_account(client):
    assert client.get("/api/me/views").status_code == 401
    register(client, "alpha")
    first = client.post("/api/me/views", json={"name": " Draft-Fokus ", "panels": ["champions", "draft", "champions"],
                                                "is_default": True})
    assert first.status_code == 201, first.text
    view = first.json()
    assert view["name"] == "Draft-Fokus" and view["panels"] == ["champions", "draft"] and view["is_default"]

    # neue Standard-Ansicht löst die alte ab
    second = client.post("/api/me/views", json={"name": "Alles", "panels": ["overview"], "is_default": True}).json()
    views = {v["id"]: v for v in client.get("/api/me/views").json()}
    assert not views[view["id"]]["is_default"] and views[second["id"]]["is_default"]

    changed = client.patch(f"/api/me/views/{view['id']}", json={"panels": ["games"], "is_default": True}).json()
    assert changed["panels"] == ["games"] and changed["name"] == "Draft-Fokus"
    assert [v["is_default"] for v in client.get("/api/me/views").json()] == [True, False]

    # ungültige Panels und fremde Ansichten
    assert client.post("/api/me/views", json={"name": "x", "panels": ["<script>"]}).status_code == 422
    other = other_client(client)
    register(other, "beta")
    assert other.get("/api/me/views").json() == []
    assert other.patch(f"/api/me/views/{view['id']}", json={"name": "fremd"}).status_code == 404
    assert other.delete(f"/api/me/views/{view['id']}").status_code == 404

    assert client.delete(f"/api/me/views/{view['id']}").status_code == 204
    assert [v["name"] for v in client.get("/api/me/views").json()] == ["Alles"]


def test_team_views_are_separate_from_scouting_views(client):
    register(client, "gamma")
    client.post("/api/me/views", json={"name": "Scout", "panels": ["draft"], "is_default": True})
    team = client.post("/api/me/views?kind=team", json={"name": "Team", "panels": ["jungle", "players"],
                                                          "is_default": True})
    assert team.status_code == 201, team.text
    assert [v["name"] for v in client.get("/api/me/views").json()] == ["Scout"]
    teams = client.get("/api/me/views", params={"kind": "team"}).json()
    assert [(v["name"], v["is_default"]) for v in teams] == [("Team", True)]
    # Standard-Ansicht gilt je Art: die Scouting-Ansicht bleibt Standard
    assert client.get("/api/me/views").json()[0]["is_default"]
    assert client.get("/api/me/views", params={"kind": "andere"}).status_code == 422
