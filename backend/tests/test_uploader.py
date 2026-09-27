"""End-to-End: Uploader liest aus einem simulierten League Client und lädt zum echten API-Server hoch."""

import sys
from pathlib import Path

import pytest

from primestats.demo import to_lcu

from .conftest import other_client, register

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "uploader"))
import primestats_uploader as up  # noqa: E402


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeLcuSession:
    """Bildet die LCU-Endpunkte für einen eingeloggten Spieler nach."""

    def __init__(self, demo_source, riot_id, with_timelines=True):
        self.headers = {}
        self.verify = True
        self.account = demo_source.account(riot_id)
        ids = sorted(demo_source.by_puuid[self.account["puuid"]], reverse=True)
        self.games = {int(mid.split("_")[1]): to_lcu(demo_source.matches[mid], demo_source.timelines[mid])
                      for mid in ids}
        self.order = list(self.games)
        self.with_timelines = with_timelines
        self.calls = []

    def get(self, url, params=None, timeout=None):
        path = url.split("127.0.0.1:1234", 1)[1]
        self.calls.append(path)
        if path == "/lol-summoner/v1/current-summoner":
            return FakeResponse(200, {"gameName": self.account["gameName"], "tagLine": self.account["tagLine"],
                                      "puuid": self.account["puuid"]})
        if path.endswith("/current-summoner/matches"):
            begin, end = params["begIndex"], params["endIndex"]
            # Listeneinträge enthalten im Client nur den eigenen Teilnehmer
            page = []
            for gid in self.order[begin:end]:
                g = dict(self.games[gid]["game"])
                g["participants"] = g["participants"][:1]
                g["participantIdentities"] = g["participantIdentities"][:1]
                page.append(g)
            return FakeResponse(200, {"games": {"games": page, "gameCount": len(page)}})
        if path.startswith("/lol-match-history/v1/games/"):
            return FakeResponse(200, self.games[int(path.rsplit("/", 1)[1])]["game"])
        if path.startswith("/lol-match-history/v1/game-timelines/"):
            if not self.with_timelines:
                return FakeResponse(404)
            return FakeResponse(200, self.games[int(path.rsplit("/", 1)[1])]["timeline"])
        return FakeResponse(404)


def _client_for(demo_source, riot_id="NLE Polaris#EUW", **kw):
    session = FakeLcuSession(demo_source, riot_id, **kw)
    return up.LeagueClient(up.Credentials(1234, "pw"), session=session), session


def _linked_tool(web, lcu, tmp_path, username="polaris"):
    """Konto auf der Website anlegen, Code erzeugen und im Tool eingeben (wie ein echter Nutzer)."""
    register(web, username)
    code = web.post("/api/me/link-code").json()["code"]
    server = up.Server("http://testserver", session=other_client(web))
    cfg, path = up.Config(server="http://testserver", keys={}), tmp_path / "tool.ini"
    logs = []
    assert up.ensure_linked(server, cfg, path, lcu.current_summoner(), ask=lambda _: code,
                            log=logs.append) == username
    return server, cfg, path, logs


def test_first_start_links_account_then_uploads_only_new_games(offline_client, demo_source, tmp_path):
    lcu, session = _client_for(demo_source)
    server, cfg, path, logs = _linked_tool(offline_client, lcu, tmp_path)
    assert any("noch nicht" in line for line in logs) and "Verknüpft" in logs[-1]
    # Geräteschlüssel wurde gespeichert (PUUID-Groß-/Kleinschreibung bleibt erhalten)
    assert up.Config.load(path).keys == {session.account["puuid"]: cfg.keys[session.account["puuid"]]}

    s = up.run(lcu, server, max_games=200, log=lambda *_: None)
    all_ids = demo_source.by_puuid[session.account["puuid"]]
    assert s.customs == len(all_ids) and s.uploaded == len(all_ids) and s.errors == 0

    # zweiter Start: keine Code-Abfrage mehr, nichts Neues
    server2 = up.Server("http://testserver", session=other_client(offline_client))
    asked = []
    up.ensure_linked(server2, up.Config.load(path), path, lcu.current_summoner(), ask=asked.append,
                     log=lambda *_: None)
    assert asked == []
    session.calls.clear()
    s2 = up.run(lcu, server2, max_games=200, log=lambda *_: None)
    assert s2.uploaded == 0 and s2.known == len(all_ids)
    assert not any("/games/" in c or "timelines" in c for c in session.calls)

    service = offline_client.app.state.service
    assert service.store.get_timeline(all_ids[0]) is not None


def test_wrong_code_is_retried(offline_client, demo_source, tmp_path):
    lcu, _ = _client_for(demo_source)
    register(offline_client, "polaris")
    good = offline_client.post("/api/me/link-code").json()["code"]
    answers = iter(["FALSCH-12", good])
    server = up.Server("http://testserver", session=other_client(offline_client))
    logs = []
    user = up.ensure_linked(server, up.Config(keys={}), tmp_path / "t.ini", lcu.current_summoner(),
                            ask=lambda _: next(answers), log=logs.append)
    assert user == "polaris" and any("ungültig" in line for line in logs)


def test_unlinked_key_is_rejected(offline_client, demo_source, tmp_path):
    lcu, session = _client_for(demo_source)
    server, cfg, path, _ = _linked_tool(offline_client, lcu, tmp_path)
    offline_client.delete(f"/api/me/riot/{session.account['puuid']}")
    with pytest.raises(up.UploaderError, match="nicht"):
        up.run(lcu, server, max_games=20, log=lambda *_: None)


def test_upload_assigns_to_existing_team(offline_client, demo_source, tmp_path):
    lcu, _ = _client_for(demo_source, "NLE Kompass#EUW")
    server, *_ = _linked_tool(offline_client, lcu, tmp_path, "kompass")
    up.run(lcu, server, max_games=10, log=lambda *_: None)
    team = {"name": "NLE", "min_members": 4, "members": [{"riot_id": f"NLE {n}#EUW"} for n in
                                                         ("Frostbite", "Waldgeist", "Polaris", "Kompass", "Leuchtturm")]}
    assert offline_client.post("/api/teams", json=team).status_code == 201
    s = up.run(lcu, server, max_games=200, log=lambda *_: None)
    assert s.uploaded > 0 and s.assigned.get("NLE", 0) > 0


def test_export_to_file_without_timelines(tmp_path, demo_source):
    lcu, _ = _client_for(demo_source, with_timelines=False)
    out = tmp_path / "export.json"
    s = up.run(lcu, None, max_games=20, out=out, log=lambda *_: None)
    import json
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["games"]) == s.customs == 20
    assert all(item["timeline"] is None for item in data["games"])


def test_credentials_parsing(tmp_path):
    assert up.parse_lockfile("LeagueClient:1234:54321:s3cr3t:https") == up.Credentials(54321, "s3cr3t")
    cmd = '"C:/Riot Games/League of Legends/LeagueClientUx.exe" --riotclient-app-port=1 --app-port=50123 --remoting-auth-token=AbC-12_x'
    assert up.parse_command_line(cmd) == up.Credentials(50123, "AbC-12_x")
    assert up.parse_command_line("irgendwas") is None
    lock = tmp_path / "lockfile"
    lock.write_text("LeagueClient:1:4444:pw:https")
    import unittest.mock as mock
    with mock.patch.object(up, "_process_command_lines", return_value=[]):
        assert up.find_credentials(str(tmp_path)) == up.Credentials(4444, "pw")


def test_config_roundtrip(tmp_path):
    path = tmp_path / "cfg.ini"
    up.Config(server="https://x.de", max_games=50, keys={"AbC-xyz": "k"}).save(path)
    cfg = up.Config.load(path)
    assert (cfg.server, cfg.max_games, cfg.keys) == ("https://x.de", 50, {"AbC-xyz": "k"})


def test_baked_server_url(monkeypatch):
    monkeypatch.setattr(up, "DEFAULT_SERVER", "https://primestats.example.de")
    assert up.Config.load(Path("/nicht/vorhanden.ini")).server == "https://primestats.example.de"
