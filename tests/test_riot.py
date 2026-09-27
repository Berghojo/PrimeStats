import pytest

from primestats.riot import NotFound, RateLimiter, RiotAPIError, RiotClient, split_riot_id
from primestats.store import Store


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_rate_limiter_waits_when_window_full():
    clock = FakeClock()
    limiter = RateLimiter(limits=((2, 1.0), (3, 10.0)), clock=clock, sleep=clock.sleep)
    for _ in range(3):
        limiter.acquire()
    assert clock.now == pytest.approx(1.01, abs=0.02)  # 3. Aufruf wartet auf das 1-s-Fenster
    limiter.acquire()
    assert clock.now >= 10.0  # 4. Aufruf wartet auf das 10-s-Fenster


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def _client(responses):
    session = FakeSession(responses)
    limiter = RateLimiter(limits=((1000, 1.0),))
    return RiotClient("key", Store(":memory:"), limiter=limiter, session=session), session


def test_match_is_cached():
    client, session = _client([FakeResponse(200, {"metadata": {"matchId": "EUW1_1"}, "info": {}})])
    assert client.match("EUW1_1")["metadata"]["matchId"] == "EUW1_1"
    assert client.match("EUW1_1")["metadata"]["matchId"] == "EUW1_1"
    assert len(session.calls) == 1


def test_retry_on_429(monkeypatch):
    monkeypatch.setattr("primestats.riot.time.sleep", lambda s: None)
    client, session = _client([FakeResponse(429, headers={"Retry-After": "1"}),
                               FakeResponse(200, {"puuid": "p", "gameName": "A", "tagLine": "EUW"})])
    assert client.account("A#EUW")["puuid"] == "p"
    assert len(session.calls) == 2


def test_not_found_and_forbidden():
    client, _ = _client([FakeResponse(404)])
    with pytest.raises(NotFound):
        client.account("Nobody#EUW")
    client, _ = _client([FakeResponse(403)])
    with pytest.raises(RiotAPIError) as exc:
        client.match("EUW1_2")
    assert exc.value.status == 403


def test_match_ids_pagination():
    client, session = _client([FakeResponse(200, [str(i) for i in range(100)]),
                               FakeResponse(200, ["100", "101"])])
    ids = client.match_ids("puuid", 150, queue=0)
    assert len(ids) == 102
    assert session.calls[1][1] == {"start": 100, "count": 50, "queue": 0}


@pytest.mark.parametrize("riot_id,expected", [
    ("Herr Grey#6781", ("Herr Grey", "6781")),
    ("  Name # EUW ", ("Name", "EUW")),
    ("a#b#EUW", ("a#b", "EUW")),
])
def test_split_riot_id(riot_id, expected):
    assert split_riot_id(riot_id) == expected


@pytest.mark.parametrize("riot_id", ["NoTag", "#EUW", "Name#", "Name#TOOLONG"])
def test_split_riot_id_invalid(riot_id):
    with pytest.raises(ValueError):
        split_riot_id(riot_id)
