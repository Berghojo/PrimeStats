from .conftest import link_riot, other_client, register


def test_register_login_logout(client):
    me = register(client, "Spieler_1")
    assert me["user"]["username"] == "Spieler_1" and me["riot_accounts"] == []
    assert client.get("/api/auth/me").json()["user"]["username"] == "Spieler_1"

    assert client.post("/api/auth/register", json={"username": "spieler_1", "password": "abcdefgh"}).status_code == 409
    assert client.post("/api/auth/register", json={"username": "a", "password": "abcdefgh"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "neu", "password": "kurz"}).status_code == 422

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json()["user"] is None

    assert client.post("/api/auth/login", json={"username": "spieler_1", "password": "falsch!!"}).status_code == 401
    resp = client.post("/api/auth/login", json={"username": "SPIELER_1", "password": "geheim123"})
    assert resp.status_code == 200 and resp.json()["user"]["username"] == "Spieler_1"
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_login_rate_limit(client):
    register(client, "ziel")
    client.post("/api/auth/logout")
    codes = [client.post("/api/auth/login", json={"username": "ziel", "password": "xxxxxxxx"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_change_password(client):
    register(client, "pwtest")
    assert client.post("/api/auth/password", json={"old_password": "falsch", "new_password": "neuesPasswort"}).status_code == 400
    assert client.post("/api/auth/password", json={"old_password": "geheim123", "new_password": "neuesPasswort"}).status_code == 204
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "pwtest", "password": "neuesPasswort"}).status_code == 200


def test_link_flow(client, demo_source):
    polaris = demo_source.account("NLE Polaris#EUW")
    assert client.post("/api/me/link-code").status_code == 401
    register(client, "alpha")

    status = client.post("/api/uploader/status", json={"puuid": polaris["puuid"]}).json()
    assert status == {"linked": False, "username": None}

    key = link_riot(client, polaris)
    me = client.get("/api/auth/me").json()
    assert [r["riot_id"] for r in me["riot_accounts"]] == ["NLE Polaris#EUW"]
    assert client.post("/api/uploader/status", json={"puuid": polaris["puuid"], "key": key}).json() == \
        {"linked": True, "username": "alpha"}
    assert client.post("/api/uploader/status", json={"puuid": polaris["puuid"], "key": "falsch"}).json()["linked"] is False

    # Codes sind einmalig
    code = client.post("/api/me/link-code").json()["code"]
    body = {"code": code, "puuid": polaris["puuid"], "game_name": "NLE Polaris", "tag_line": "EUW"}
    assert client.post("/api/uploader/link", json=body).status_code == 200
    assert client.post("/api/uploader/link", json=body).status_code == 400
    # kleingeschrieben / ohne Bindestrich wird akzeptiert
    code = client.post("/api/me/link-code").json()["code"]
    body["code"] = code.replace("-", "").lower()
    assert client.post("/api/uploader/link", json=body).status_code == 200

    # Wer den Client geöffnet hat, kann den Account auf ein anderes Konto umziehen
    other = other_client(client)
    register(other, "beta")
    link_riot(other, polaris)
    assert client.get("/api/auth/me").json()["riot_accounts"] == []
    assert client.post("/api/uploader/status", json={"puuid": polaris["puuid"], "key": key}).json()["linked"] is False

    # Verknüpfung lösen
    assert other.delete(f"/api/me/riot/{polaris['puuid']}").status_code == 204
    assert other.get("/api/auth/me").json()["riot_accounts"] == []
    assert other.delete(f"/api/me/riot/{polaris['puuid']}").status_code == 404


def test_link_code_brute_force_is_limited(client, demo_source):
    polaris = demo_source.account("NLE Polaris#EUW")
    body = {"code": "AAAA-AAAA", "puuid": polaris["puuid"], "game_name": "x", "tag_line": "EUW"}
    codes = [client.post("/api/uploader/link", json=body).status_code for _ in range(11)]
    assert codes[:10] == [400] * 10 and codes[10] == 429


def test_register_with_email_address(client):
    me = register(client, "berghoff.joshua@gmail.com")
    assert me["user"]["username"] == "berghoff.joshua@gmail.com"
    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": " Berghoff.Joshua@Gmail.com ", "password": "geheim123"})
    assert resp.status_code == 200
    assert client.post("/api/auth/register", json={"username": "a b@c.de", "password": "geheim123"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "x" * 65, "password": "geheim123"}).status_code == 422
