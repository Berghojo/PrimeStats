"""Konfiguration aus Umgebungsvariablen (bzw. einer ``.env``-Datei)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATABASE_URL = "postgresql+psycopg://primestats:primestats@localhost:5432/primestats"


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


def normalize_database_url(url: str) -> str:
    """Erlaubt auch ``postgres://``/``postgresql://``-URLs (z.B. von Hostern) und nutzt psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@dataclass
class Settings:
    api_key: str | None = None
    #: Regional routing value für account-v1 / match-v5 (europe, americas, asia, sea)
    region: str = "europe"
    database_url: str = DEFAULT_DATABASE_URL
    #: Datenbankschema beim Start per Alembic auf den neuesten Stand bringen
    auto_migrate: bool = True
    #: Verzeichnis für Data-Dragon-Cache
    cache_dir: Path = Path(".cache")
    #: Demo-Modus: statt der Riot-API werden generierte Beispieldaten verwendet
    demo: bool = False
    #: Aktuelle Data-Dragon-Version/Championdaten beim Start aus dem Netz laden
    ddragon_fetch: bool = True
    ddragon_language: str = "de_DE"
    #: Wie viele Match-IDs pro Spieler beim Team-Sync maximal abgefragt werden
    sync_match_count: int = 100
    #: Gebautes React-Frontend, das vom Backend mit ausgeliefert wird (optional)
    frontend_dist: Path | None = None
    #: Gültigkeit einer Anmeldung in Tagen
    session_days: int = 30
    #: Session-Cookie nur über HTTPS senden (auto = abhängig von der Anfrage)
    cookie_secure: str = "auto"
    #: Wo sich Spieler den Uploader herunterladen können (wird im Frontend verlinkt)
    uploader_url: str = "https://github.com/Berghojo/PrimeStats/releases/latest"
    cors_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        dist = os.getenv("FRONTEND_DIST")
        default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        return cls(
            api_key=os.getenv("LOL_API_KEY") or None,
            region=os.getenv("RIOT_REGION", "europe"),
            database_url=normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)),
            auto_migrate=_flag("AUTO_MIGRATE", True),
            cache_dir=Path(os.getenv("PRIMESTATS_CACHE_DIR", ".cache")),
            demo=_flag("PRIMESTATS_DEMO"),
            ddragon_fetch=_flag("DDRAGON_FETCH", True),
            ddragon_language=os.getenv("DDRAGON_LANGUAGE", "de_DE"),
            sync_match_count=int(os.getenv("SYNC_MATCH_COUNT", "100")),
            frontend_dist=Path(dist) if dist else (default_dist if default_dist.exists() else None),
            session_days=int(os.getenv("SESSION_DAYS", "30")),
            cookie_secure=os.getenv("COOKIE_SECURE", "auto"),
            uploader_url=os.getenv("UPLOADER_URL", "https://github.com/Berghojo/PrimeStats/releases/latest"),
            cors_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()],
        )
