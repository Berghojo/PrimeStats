"""Gemeinsame FastAPI-Abhängigkeiten."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from .access import Viewer
from .services import PrimeStats
from .store import UserAccount

SESSION_COOKIE = "ps_session"


def get_service(request: Request) -> PrimeStats:
    return request.app.state.service


Service = Annotated[PrimeStats, Depends(get_service)]


def get_user(request: Request, service: Service) -> UserAccount | None:
    token = request.cookies.get(SESSION_COOKIE)
    return service.store.session_user(token) if token else None


def get_viewer(service: Service, user: Annotated[UserAccount | None, Depends(get_user)]) -> Viewer:
    return Viewer.load(service.store, user)


def require_user(user: Annotated[UserAccount | None, Depends(get_user)]) -> UserAccount:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bitte zuerst anmelden.")
    return user


CurrentViewer = Annotated[Viewer, Depends(get_viewer)]
CurrentUser = Annotated[UserAccount, Depends(require_user)]


class RateLimit:
    """Einfacher In-Memory-Limiter (pro Schlüssel ``limit`` Versuche je ``window`` Sekunden)."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                    "Zu viele Versuche – bitte kurz warten.")
            hits.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"
