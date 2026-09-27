"""Champion-Stammdaten aus Data Dragon (mit Offline-Fallback)."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CDN = "https://ddragon.leagueoflegends.com"
FALLBACK_FILE = Path(__file__).parent / "resources" / "champion.json"


@dataclass(frozen=True)
class Champion:
    key: int      # numerische ID aus der Match-API (championId)
    id: str       # Data-Dragon-ID, z.B. "MonkeyKing" (für Bild-URLs)
    name: str     # Anzeigename, z.B. "Wukong"


class DataDragon:
    def __init__(self, cache_dir: Path | None = None, fetch: bool = True, language: str = "de_DE"):
        self.cache_dir = cache_dir
        self.fetch = fetch
        self.language = language
        self._lock = threading.Lock()
        self._loaded = False
        self.version = ""
        self._by_key: dict[int, Champion] = {}

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            data = self._load_remote() if self.fetch else None
            if data is None:
                data = json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
            self.version = data["version"]
            self._by_key = {
                int(c["key"]): Champion(int(c["key"]), c["id"], c["name"]) for c in data["data"].values()
            }
            self._loaded = True

    def _load_remote(self) -> dict | None:
        try:
            version = requests.get(f"{CDN}/api/versions.json", timeout=4).json()[0]
            cache = None
            if self.cache_dir:
                cache = self.cache_dir / f"champion_{version}_{self.language}.json"
                if cache.exists():
                    return json.loads(cache.read_text(encoding="utf-8"))
            resp = requests.get(f"{CDN}/cdn/{version}/data/{self.language}/champion.json", timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # Netzwerkfehler etc. -> lokale Daten
            log.warning("Data Dragon nicht erreichbar, nutze lokale Championdaten: %s", exc)
            return None

    def champion(self, key: int | str | None) -> Champion:
        self._ensure_loaded()
        try:
            key = int(key)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return Champion(-1, "", "–")
        return self._by_key.get(key) or Champion(key, "", f"#{key}")

    def icon_url(self, key: int | str | None) -> str:
        champ = self.champion(key)
        if not champ.id:
            return ""
        return f"{CDN}/cdn/{self.version}/img/champion/{champ.id}.png"

    def all(self) -> list[Champion]:
        self._ensure_loaded()
        return sorted(self._by_key.values(), key=lambda c: c.name)
