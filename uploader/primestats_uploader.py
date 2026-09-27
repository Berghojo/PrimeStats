"""PrimeStats-Uploader: lädt Custom Games aus dem League Client zu PrimeStats hoch.

Die Riot-API liefert Custom Games nur mit Turniercode. Der lokale League Client kennt
dagegen die komplette eigene Match-History inklusive normaler Custom-Lobbys (Scrims).
Dieses Tool liest sie über die Client-API (LCU) aus und lädt alles hoch, was der
PrimeStats-Server noch nicht kennt.

Benutzung: League Client starten und einloggen, dann ``PrimeStats-Uploader.exe`` starten.
Beim ersten Start werden Server-Adresse und Upload-Token abgefragt und gespeichert.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import urllib3

VERSION = "1.0.0"
CONFIG_NAME = "primestats-uploader.ini"
HISTORY_PAGE = 20
UPLOAD_BATCH = 5

DEFAULT_LOCKFILES = [
    r"C:\Riot Games\League of Legends\lockfile",
    r"D:\Riot Games\League of Legends\lockfile",
    r"E:\Riot Games\League of Legends\lockfile",
    r"C:\Program Files\Riot Games\League of Legends\lockfile",
    "/Applications/League of Legends.app/Contents/LoL/lockfile",
]

# Der Client nutzt ein selbstsigniertes Zertifikat auf 127.0.0.1
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UploaderError(Exception):
    pass


# ------------------------------------------------------------------ Konfiguration
def app_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller-EXE
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    local = app_dir() / CONFIG_NAME
    if local.exists() or os.access(local.parent, os.W_OK):
        return local
    base = Path(os.getenv("APPDATA") or Path.home())
    return base / "PrimeStats" / CONFIG_NAME


@dataclass
class Config:
    server: str = ""
    token: str = ""
    league_path: str = ""
    max_games: int = 200

    @classmethod
    def load(cls, path: Path) -> "Config":
        parser = configparser.ConfigParser()
        if path.exists():
            parser.read(path, encoding="utf-8")
        s = parser["primestats"] if parser.has_section("primestats") else {}
        return cls(server=s.get("server", ""), token=s.get("token", ""),
                   league_path=s.get("league_path", ""), max_games=int(s.get("max_games", 200)))

    def save(self, path: Path) -> None:
        parser = configparser.ConfigParser()
        parser["primestats"] = {"server": self.server, "token": self.token, "league_path": self.league_path,
                                "max_games": str(self.max_games)}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            parser.write(fh)


# -------------------------------------------------------------- League Client
@dataclass
class Credentials:
    port: int
    password: str


def parse_lockfile(text: str) -> Credentials:
    # Format: LeagueClient:<pid>:<port>:<password>:<protocol>
    parts = text.strip().split(":")
    if len(parts) < 5:
        raise UploaderError("Lockfile hat ein unbekanntes Format.")
    return Credentials(port=int(parts[2]), password=parts[3])


def parse_command_line(cmdline: str) -> Credentials | None:
    port = re.search(r"--app-port=(\d+)", cmdline)
    token = re.search(r"--remoting-auth-token=([\w-]+)", cmdline)
    if port and token:
        return Credentials(int(port.group(1)), token.group(1))
    return None


def _process_command_lines() -> list[str]:
    try:
        if platform.system() == "Windows":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='LeagueClientUx.exe'\" | "
                 "Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
        else:
            out = subprocess.run(["ps", "-A", "-o", "args"], capture_output=True, text=True, timeout=15).stdout
        return [line for line in out.splitlines() if "LeagueClientUx" in line]
    except (OSError, subprocess.SubprocessError):
        return []


def find_credentials(league_path: str = "") -> Credentials:
    """Port und Passwort des laufenden Clients (Prozess-Kommandozeile oder lockfile)."""
    for line in _process_command_lines():
        creds = parse_command_line(line)
        if creds:
            return creds
    candidates = []
    if league_path:
        p = Path(league_path)
        candidates.append(p if p.name == "lockfile" else p / "lockfile")
    candidates += [Path(p) for p in DEFAULT_LOCKFILES]
    for path in candidates:
        if path.is_file():
            return parse_lockfile(path.read_text(encoding="utf-8"))
    raise UploaderError("League Client nicht gefunden. Bitte den Client starten und einloggen "
                        "(oder league_path in der Konfiguration setzen).")


class LeagueClient:
    def __init__(self, creds: Credentials, session: requests.Session | None = None):
        self.base = f"https://127.0.0.1:{creds.port}"
        self.session = session or requests.Session()
        self.session.verify = False
        auth = base64.b64encode(f"riot:{creds.password}".encode()).decode()
        self.session.headers.update({"Authorization": f"Basic {auth}", "Accept": "application/json"})

    def get(self, path: str, **params):
        resp = self.session.get(self.base + path, params=params or None, timeout=30)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise UploaderError(f"League Client antwortet mit {resp.status_code} auf {path}")
        return resp.json()

    def current_summoner(self) -> dict:
        me = self.get("/lol-summoner/v1/current-summoner")
        if not me:
            raise UploaderError("Im League Client ist niemand eingeloggt.")
        return me

    def history(self, max_games: int) -> list[dict]:
        """Einträge der eigenen Match-History (neueste zuerst)."""
        games: list[dict] = []
        start = 0
        while start < max_games:
            page = self.get("/lol-match-history/v1/products/lol/current-summoner/matches",
                            begIndex=start, endIndex=start + HISTORY_PAGE)
            batch = ((page or {}).get("games") or {}).get("games") or []
            if not batch:
                break
            games.extend(batch)
            start += HISTORY_PAGE
        seen, unique = set(), []
        for g in games:
            if g.get("gameId") not in seen:
                seen.add(g.get("gameId"))
                unique.append(g)
        return unique[:max_games]

    def game(self, game_id: int) -> dict | None:
        return self.get(f"/lol-match-history/v1/games/{game_id}")

    def timeline(self, game_id: int) -> dict | None:
        try:
            return self.get(f"/lol-match-history/v1/game-timelines/{game_id}")
        except UploaderError:
            return None  # Timeline ist optional


def is_custom(game: dict) -> bool:
    return game.get("gameType") == "CUSTOM_GAME" and game.get("mapId", 11) == 11


def match_id(game: dict) -> str:
    return f"{game.get('platformId') or 'EUW1'}_{game['gameId']}"


# ------------------------------------------------------------------ Server
class Server:
    def __init__(self, base: str, token: str, uploader: str = "", session=None):
        self.base = base.rstrip("/")
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {token}", "X-Uploader": uploader,
                        "User-Agent": f"PrimeStats-Uploader/{VERSION}"}

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = self.session.post(self.base + path, json=body, headers=self.headers, timeout=120)
        except requests.RequestException as exc:
            raise UploaderError(f"Server {self.base} nicht erreichbar: {exc}") from exc
        if resp.status_code in (401, 403):
            detail = _detail(resp)
            raise UploaderError(f"Zugriff verweigert ({resp.status_code}): {detail}")
        if resp.status_code != 200:
            raise UploaderError(f"Server-Fehler {resp.status_code}: {_detail(resp)}")
        return resp.json()

    def known(self, ids: list[str]) -> set[str]:
        return set(self._post("/api/import/known", {"match_ids": ids})["known"])

    def upload(self, items: list[dict]) -> dict:
        return self._post("/api/import/lcu", {"games": items})


def _detail(resp) -> str:
    try:
        return str(resp.json().get("detail"))
    except ValueError:
        return resp.text[:200]


# -------------------------------------------------------------------- Ablauf
@dataclass
class Summary:
    customs: int = 0
    known: int = 0
    uploaded: int = 0
    timelines: int = 0
    errors: int = 0
    assigned: dict | None = None


def run(client: LeagueClient, server: Server | None, max_games: int, out: Path | None = None,
        log=print) -> Summary:
    summary = Summary(assigned={})
    me = client.current_summoner()
    log(f"Eingeloggt als {me.get('gameName') or me.get('displayName')}#{me.get('tagLine', '')}")

    history = client.history(max_games)
    customs = [g for g in history if is_custom(g)]
    summary.customs = len(customs)
    log(f"{len(history)} Spiele in der Match-History, davon {len(customs)} Custom Games.")
    if not customs:
        return summary

    ids = [match_id(g) for g in customs]
    known = server.known(ids) if server else set()
    summary.known = len(known)
    todo = [g for g in customs if match_id(g) not in known]
    log(f"{len(known)} bereits auf dem Server, {len(todo)} neu.")

    exported: list[dict] = []
    batch: list[dict] = []

    def flush():
        if not batch:
            return
        if server:
            result = server.upload(batch)
            summary.uploaded += len(result["imported"])
            summary.timelines += len(result["updated"])
            summary.errors += len(result["errors"])
            for err in result["errors"]:
                log(f"  Fehler: {err}")
            for team, n in result["assigned"].items():
                summary.assigned[team] = summary.assigned.get(team, 0) + n
        exported.extend(batch)
        batch.clear()

    for i, entry in enumerate(todo, 1):
        game_id = entry["gameId"]
        details = client.game(game_id) or entry
        timeline = client.timeline(game_id)
        batch.append({"game": details, "timeline": timeline})
        log(f"  [{i}/{len(todo)}] {match_id(entry)} gelesen{'' if timeline else ' (ohne Timeline)'}")
        if len(batch) >= UPLOAD_BATCH:
            flush()
    flush()

    if out:
        out.write_text(json.dumps({"games": exported}, ensure_ascii=False), encoding="utf-8")
        log(f"{len(exported)} Spiele nach {out} geschrieben.")
    return summary


def ask_config(cfg: Config, path: Path) -> Config:
    print("Erster Start – bitte die Verbindung zu PrimeStats einrichten.")
    while not cfg.server:
        cfg.server = input("Server-Adresse (z.B. https://primestats.example.de): ").strip().rstrip("/")
    while not cfg.token:
        cfg.token = input("Upload-Token (vom Server-Admin): ").strip()
    cfg.save(path)
    print(f"Gespeichert in {path}\n")
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lädt Custom Games aus dem League Client zu PrimeStats hoch.")
    parser.add_argument("--server", help="Adresse des PrimeStats-Servers")
    parser.add_argument("--token", help="Upload-Token")
    parser.add_argument("--max-games", type=int, help="Wie weit die Match-History durchsucht wird")
    parser.add_argument("--out", type=Path, help="Spiele zusätzlich/stattdessen als JSON-Datei speichern")
    parser.add_argument("--offline", action="store_true", help="Nichts hochladen (nur mit --out sinnvoll)")
    parser.add_argument("--no-pause", action="store_true", help="Am Ende nicht auf Enter warten")
    parser.add_argument("--version", action="version", version=f"PrimeStats-Uploader {VERSION}")
    args = parser.parse_args(argv)

    print(f"PrimeStats-Uploader {VERSION}\n")
    path = config_path()
    cfg = Config.load(path)
    if args.server:
        cfg.server = args.server.rstrip("/")
    if args.token:
        cfg.token = args.token
    if args.max_games:
        cfg.max_games = args.max_games

    code = 0
    try:
        if not args.offline and (not cfg.server or not cfg.token):
            cfg = ask_config(cfg, path)
        client = LeagueClient(find_credentials(cfg.league_path))
        uploader_name = ""
        try:
            me = client.current_summoner()
            uploader_name = f"{me.get('gameName', '')}#{me.get('tagLine', '')}"
        except UploaderError:
            pass
        server = None if args.offline else Server(cfg.server, cfg.token, uploader_name)
        started = time.time()
        s = run(client, server, cfg.max_games, args.out)
        print()
        if server:
            print(f"Fertig in {time.time() - started:.0f}s: {s.uploaded} neue Spiele hochgeladen"
                  f"{f', {s.timelines} Timelines ergänzt' if s.timelines else ''}"
                  f"{f', {s.errors} Fehler' if s.errors else ''}.")
            for team, n in (s.assigned or {}).items():
                print(f"  → {n} Spiel(e) dem Team {team} zugeordnet")
    except UploaderError as exc:
        print(f"\nFehler: {exc}")
        code = 1
    except KeyboardInterrupt:
        code = 130
    if not args.no_pause and getattr(sys, "frozen", False):
        input("\nEnter drücken zum Beenden …")
    return code


if __name__ == "__main__":
    sys.exit(main())
