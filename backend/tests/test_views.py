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
