import re


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Spieler suchen" in resp.get_data(as_text=True)


def test_player_search_and_analysis(client):
    resp = client.get("/player", query_string={"riot_id": "NLE Polaris#EUW"})
    assert resp.status_code == 200
    ids = re.findall(r'name="m" value="([^"]+)"', resp.get_data(as_text=True))
    assert len(ids) == 20
    resp = client.get("/analysis", query_string={"m": ids[:3]})
    assert resp.status_code == 200
    assert 'id="analysis-data"' in resp.get_data(as_text=True)


def test_unknown_player_redirects_with_message(client):
    resp = client.get("/player", query_string={"riot_id": "Nobody#EUW"}, follow_redirects=True)
    assert "nicht gefunden" in resp.get_data(as_text=True)


def test_analysis_requires_games(client):
    assert client.get("/analysis").status_code == 302


def test_team_lifecycle(client, app):
    resp = client.post("/teams", data={
        "name": "Nordlicht Esports", "tag": "NLE", "min_members": "4",
        "riot_id": ["NLE Frostbite#EUW", "NLE Waldgeist#EUW", "NLE Polaris#EUW", "NLE Kompass#EUW",
                    "NLE Leuchtturm#EUW", "NLE Treibholz#EUW", ""],
        "role": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY", "", ""],
    })
    assert resp.status_code == 302
    url = resp.headers["Location"]
    team_id = int(url.rsplit("/", 1)[-1])
    assert "Noch keine Spiele" in client.get(url).get_data(as_text=True)

    service = app.extensions["primestats"]
    service.jobs.start(service.store.get_team(team_id), background=False)
    html = client.get(url).get_data(as_text=True)
    assert 'id="team-data"' in html and "Champion-Pools" in html

    assert client.get(url, query_string={"label": "official", "side": "red", "last": 5}).status_code == 200
    status = client.get(f"/teams/{team_id}/sync", headers={"HX-Request": "true"})
    assert status.headers.get("HX-Refresh") == "true"

    mid = service.store.team_games(team_id)[0].match_id
    resp = client.post(f"/teams/{team_id}/games/{mid}", data={"label": "scrim", "included": "0"},
                       headers={"HX-Request": "true"})
    assert resp.status_code == 200
    tg = next(g for g in service.store.team_games(team_id) if g.match_id == mid)
    assert tg.label == "scrim" and not tg.included

    assert client.get(f"/match/{mid}", query_string={"team": team_id}).status_code == 200
    assert client.get(f"/teams/{team_id}/edit").status_code == 200
    assert client.post(f"/teams/{team_id}/delete").status_code == 302
    assert client.get(url).status_code == 404


def test_team_create_reports_unknown_players(client):
    resp = client.post("/teams", data={"name": "X", "riot_id": ["Nobody#EUW"], "role": [""]})
    assert resp.status_code == 400
    assert "nicht gefunden" in resp.get_data(as_text=True)


def test_without_api_key_shows_hint(tmp_path):
    from primestats import create_app
    from primestats.config import Settings
    app = create_app(Settings(api_key=None, demo=False, ddragon_fetch=False, data_dir=tmp_path))
    client = app.test_client()
    assert "Kein Riot-API-Key" in client.get("/").get_data(as_text=True)
    assert client.get("/teams").status_code == 503
