"""Der League Client kennt Spieler unter anderen PUUIDs (UUID-Format) als die Riot-API."""

import uuid

from primestats import lcu
from primestats.demo import to_lcu
from primestats.services import OfflineSource, PrimeStats

from .conftest import register


def client_puuid(puuid: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, puuid))


def _client_scrims(demo_source, puuid, n=2, offset=10**9):
    """Scrims so, wie der echte Client sie liefert: neue Spiel-IDs, Client-PUUIDs."""
    ids = [mid for mid, m in demo_source.matches.items() if not m["info"].get("tournamentCode")
           and puuid in m["metadata"]["participants"]][:n]
    items = []
    for mid in ids:
        item = to_lcu(demo_source.matches[mid], demo_source.timelines[mid])
        item["game"]["gameId"] += offset
        for pi in item["game"]["participantIdentities"]:
            pi["player"]["puuid"] = client_puuid(pi["player"]["puuid"])
        items.append(item)
    return items


def _link(client, account):
    code = client.post("/api/me/link-code").json()["code"]
    resp = client.post("/api/uploader/link", json={"code": code, "puuid": client_puuid(account["puuid"]),
                                                   "game_name": account["gameName"], "tag_line": account["tagLine"]})
    assert resp.status_code == 200, resp.text
    return resp.json()["key"]


def test_is_client_puuid(demo_source):
    assert lcu.is_client_puuid("063a091d-49a7-56f8-b0ca-22d5e2a021b1")
    assert not lcu.is_client_puuid(demo_source.account("NLE Polaris#EUW")["puuid"])
    assert not lcu.is_client_puuid("unknown-1-2")


def test_link_and_upload_use_api_puuids(client, demo_source):
    polaris = demo_source.account("NLE Polaris#EUW")
    register(client)
    key = _link(client, polaris)
    service = client.app.state.service

    # gespeichert wird die PUUID der Riot-API, das Tool bleibt mit der Client-PUUID angemeldet
    assert [r["puuid"] for r in client.get("/api/auth/me").json()["riot_accounts"]] == [polaris["puuid"]]
    status = client.post("/api/uploader/status", json={"puuid": client_puuid(polaris["puuid"]), "key": key}).json()
    assert status["linked"] is True
    assert service.account("NLE Polaris#EUW")["puuid"] == polaris["puuid"]

    headers = {"X-Riot-Puuid": client_puuid(polaris["puuid"]), "X-Link-Key": key}
    items = _client_scrims(demo_source, polaris["puuid"])
    result = client.post("/api/uploader/games", json={"games": items}, headers=headers).json()
    assert len(result["imported"]) == 2 and not result["errors"]
    for mid in result["imported"]:
        participants = service.store.get_match(mid)["metadata"]["participants"]
        assert polaris["puuid"] in participants
        assert not any(lcu.is_client_puuid(p) for p in participants)
    assert service.store.linked_riot_accounts(1)[0].last_upload_at is not None


def test_repair_after_offline_upload(store, demo_source):
    polaris = demo_source.account("NLE Polaris#EUW")
    client_id = client_puuid(polaris["puuid"])
    offline = PrimeStats(store, OfflineSource())
    user_id = store.create_user("alpha", "x").id
    store.link_riot(user_id, client_id, polaris["gameName"], polaris["tagLine"], "key")
    store.put_account("NLE Polaris#EUW", {**polaris, "puuid": client_id})
    result = offline.import_lcu(_client_scrims(demo_source, polaris["puuid"]))
    assert len(result.imported) == 2
    team_id = store.create_team("T", "", 1, [m for m in offline.resolve_members([("NLE Polaris#EUW", "")])[0]])
    assert store.get_team(team_id).puuids == {client_id}

    online = PrimeStats(store, demo_source)
    assert online.account("NLE Polaris#EUW")["puuid"] == polaris["puuid"]  # Cache wird korrigiert
    assert online.repair_client_puuids() == 2
    assert [link.puuid for link in store.linked_riot_accounts(user_id)] == [polaris["puuid"]]
    assert store.get_team(team_id).puuids == {polaris["puuid"]}
    for mid in result.imported:
        assert polaris["puuid"] in store.get_match(mid)["metadata"]["participants"]
    assert set(result.imported) <= {tg.match_id for tg in store.team_games(team_id)}
    assert online.link_owner(client_id, "key") == user_id
    assert online.repair_client_puuids() == 0
