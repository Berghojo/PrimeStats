"""Konfiguration aus Umgebungsvariablen (bzw. einer ``.env``-Datei)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


def _flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


@dataclass
class Settings:
    api_key: str | None = None
    #: Regional routing value für account-v1 / match-v5 (europe, americas, asia, sea)
    region: str = "europe"
    data_dir: Path = Path("data")
    secret_key: str = field(default_factory=lambda: secrets.token_hex(16))
    #: Demo-Modus: statt der Riot-API werden generierte Beispieldaten verwendet
    demo: bool = False
    #: Aktuelle Data-Dragon-Version/Championdaten beim Start aus dem Netz laden
    ddragon_fetch: bool = True
    ddragon_language: str = "de_DE"
    #: Wie viele Match-IDs pro Spieler beim Team-Sync maximal abgefragt werden
    sync_match_count: int = 100

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.getenv("LOL_API_KEY") or None,
            region=os.getenv("RIOT_REGION", "europe"),
            data_dir=Path(os.getenv("PRIMESTATS_DATA_DIR", "data")),
            secret_key=os.getenv("SECRET_KEY") or secrets.token_hex(16),
            demo=_flag("PRIMESTATS_DEMO"),
            ddragon_fetch=_flag("DDRAGON_FETCH", True),
            ddragon_language=os.getenv("DDRAGON_LANGUAGE", "de_DE"),
            sync_match_count=int(os.getenv("SYNC_MATCH_COUNT", "100")),
        )
