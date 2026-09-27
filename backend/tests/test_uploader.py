"""End-to-End: Uploader liest aus einem simulierten League Client und lädt zum echten API-Server hoch."""

import sys
from pathlib import Path

import pytest

from primestats.demo import to_lcu

from .conftest import UPLOAD_TOKEN

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


@pytest.fixture
def server_client(offline_client):
    return offline_client


def test_uploads_only_new_custom_games(server_client, demo_source):
    lcu, session = _client_for(demo_source)
    server = up.Server("http://testserver", UPLOAD_TOKEN, "NLE Polaris#EUW", session=server_client)
    logs = []
    s = up.run(lcu, server, max_games=200, log=logs.append)

    all_ids = demo_source.by_puuid[session.account["puuid"]]
    assert s.customs == len(all_ids)            # auch Turnierspiele sind Custom Games
    assert s.uploaded == len(all_ids) and s.errors == 0 and s.known == 0
    assert session.account["gameName"] in logs[0]

    # zweiter Lauf: alles bekannt, keine Details/Timelines werden mehr gelesen
    session.calls.clear()
    s2 = up.run(lcu, server, max_games=200, log=lambda *_: None)
    assert s2.uploaded == 0 and s2.known == len(all_ids)
    assert not any("/games/" in c or "timelines" in c for c in session.calls)

    # Spiele sind auf dem Server inkl. Timeline angekommen
    service = server_client.app.state.service
    mid = all_ids[0]
    assert service.store.get_timeline(mid) is not None
    assert service.match(mid).participants[0].name


def test_upload_assigns_to_existing_team(server_client, demo_source):
    # Erst ein Spieler lädt hoch, damit die Riot-IDs bekannt sind; dann Team anlegen; dann ein zweiter Upload
    lcu, _ = _client_for(demo_source, "NLE Kompass#EUW")
    server = up.Server("http://testserver", UPLOAD_TOKEN, session=server_client)
    up.run(lcu, server, max_games=10, log=lambda *_: None)
    team = {"name": "NLE", "min_members": 4, "members": [{"riot_id": f"NLE {n}#EUW"} for n in
                                                         ("Frostbite", "Waldgeist", "Polaris", "Kompass", "Leuchtturm")]}
    assert server_client.post("/api/teams", json=team).status_code == 201
    s = up.run(lcu, server, max_games=200, log=lambda *_: None)
    assert s.uploaded > 0 and s.assigned.get("NLE", 0) > 0


def test_wrong_token_is_reported(server_client, demo_source):
    lcu, _ = _client_for(demo_source)
    server = up.Server("http://testserver", "falsch", session=server_client)
    with pytest.raises(up.UploaderError, match="401"):
        up.run(lcu, server, max_games=20, log=lambda *_: None)


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
    up.Config(server="https://x.de", token="t", max_games=50).save(path)
    cfg = up.Config.load(path)
    assert (cfg.server, cfg.token, cfg.max_games) == ("https://x.de", "t", 50)
