"""Schlanker Riot-API-Client mit Rate-Limiting, Retries und persistentem Cache."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Protocol
from urllib.parse import quote

import requests

from .store import Store

#: Limits eines Development-Keys: 20 Requests/Sekunde und 100 Requests/2 Minuten
DEV_KEY_LIMITS = ((20, 1.0), (100, 120.0))


class RiotAPIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class NotFound(RiotAPIError):
    pass


class MatchSource(Protocol):
    """Schnittstelle, die sowohl der echte Client als auch der Demo-Client erfüllen."""

    def account(self, riot_id: str) -> dict: ...

    def match_ids(self, puuid: str, count: int = 20, *, queue: int | None = None,
                  type: str | None = None, start: int = 0) -> list[str]: ...

    def match(self, match_id: str) -> dict: ...

    def timeline(self, match_id: str) -> dict: ...


def split_riot_id(riot_id: str) -> tuple[str, str]:
    riot_id = riot_id.strip()
    if "#" not in riot_id:
        raise ValueError("Riot-ID muss das Format Name#TAG haben.")
    name, _, tag = riot_id.rpartition("#")
    name, tag = name.strip(), tag.strip()
    if not name or not tag or len(name) > 16 or len(tag) > 5:
        raise ValueError(f"Ungültige Riot-ID: {riot_id!r}")
    return name, tag


class RateLimiter:
    """Sliding-Window-Limiter für mehrere gleichzeitige Limits (thread-safe)."""

    def __init__(self, limits=DEV_KEY_LIMITS, clock=time.monotonic, sleep=time.sleep):
        self.limits = tuple(limits)
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()
        self._horizon = max(window for _, window in self.limits)

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = self._clock()
                while self._calls and now - self._calls[0] >= self._horizon:
                    self._calls.popleft()
                wait = 0.0
                for count, window in self.limits:
                    recent = [t for t in self._calls if now - t < window]
                    if len(recent) >= count:
                        wait = max(wait, recent[-count] + window - now)
                if wait <= 0:
                    self._calls.append(now)
                    return
            self._sleep(wait + 0.01)


class RiotClient:
    def __init__(self, api_key: str, store: Store, region: str = "europe",
                 limiter: RateLimiter | None = None, session: requests.Session | None = None):
        if not api_key:
            raise ValueError("Kein Riot-API-Key konfiguriert (LOL_API_KEY).")
        self.store = store
        self.base = f"https://{region}.api.riotgames.com"
        self.limiter = limiter or RateLimiter()
        self.session = session or requests.Session()
        self.session.headers.update({"X-Riot-Token": api_key})

    # ----------------------------------------------------------------- http
    def _get(self, path: str, params: dict | None = None, retries: int = 3):
        for attempt in range(retries + 1):
            self.limiter.acquire()
            try:
                resp = self.session.get(self.base + path, params=params, timeout=15)
            except requests.RequestException as exc:
                if attempt == retries:
                    raise RiotAPIError(0, f"Riot-API nicht erreichbar: {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 and attempt < retries:
                time.sleep(float(resp.headers.get("Retry-After", 5)))
                continue
            if resp.status_code >= 500 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 404:
                raise NotFound(404, "Nicht gefunden.")
            if resp.status_code in (401, 403):
                raise RiotAPIError(resp.status_code,
                                   "API-Key ungültig oder abgelaufen (Development-Keys laufen nach 24h ab).")
            raise RiotAPIError(resp.status_code, f"Riot-API-Fehler {resp.status_code}: {resp.text[:200]}")
        raise RiotAPIError(429, "Rate-Limit überschritten.")

    # ------------------------------------------------------------ endpoints
    def account(self, riot_id: str) -> dict:
        name, tag = split_riot_id(riot_id)
        cached = self.store.get_account(f"{name}#{tag}")
        if cached:
            return cached
        try:
            data = self._get(f"/riot/account/v1/accounts/by-riot-id/{quote(name)}/{quote(tag)}")
        except NotFound:
            raise NotFound(404, f"Spieler {name}#{tag} wurde nicht gefunden.") from None
        self.store.put_account(f"{name}#{tag}", data)
        return data

    def match_ids(self, puuid: str, count: int = 20, *, queue: int | None = None,
                  type: str | None = None, start: int = 0) -> list[str]:
        """Match-IDs (neueste zuerst). Nicht gecacht, da sich die Liste ändert."""
        ids: list[str] = []
        while count > 0:
            batch = min(count, 100)
            params: dict = {"start": start, "count": batch}
            if queue is not None:
                params["queue"] = queue
            if type:
                params["type"] = type
            page = self._get(f"/lol/match/v5/matches/by-puuid/{puuid}/ids", params)
            ids.extend(page)
            if len(page) < batch:
                break
            start += batch
            count -= batch
        return ids

    def match(self, match_id: str) -> dict:
        cached = self.store.get_match(match_id)
        if cached:
            return cached
        data = self._get(f"/lol/match/v5/matches/{match_id}")
        self.store.put_match(match_id, data)
        return data

    def timeline(self, match_id: str) -> dict:
        cached = self.store.get_timeline(match_id)
        if cached:
            return cached
        data = self._get(f"/lol/match/v5/matches/{match_id}/timeline")
        self.store.put_timeline(match_id, data)
        return data
