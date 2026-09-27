"""PrimeStats-Uploader: lädt Custom Games aus dem League Client zu PrimeStats hoch.

Die Riot-API liefert Custom Games nur mit Turniercode. Der lokale League Client kennt
dagegen die komplette eigene Match-History inklusive normaler Custom-Lobbys (Scrims).
Dieses Tool liest sie über die Client-API (LCU) aus und lädt alles hoch, was der
PrimeStats-Server noch nicht kennt.

Benutzung: League Client starten und einloggen, dann ``PrimeStats-Uploader.exe`` starten.
Beim ersten Start mit einem Riot-Account fragt das Tool nach einem Verknüpfungscode, den man auf der
PrimeStats-Website (Konto → „Riot-Account verknüpfen“) erzeugt. Damit wird der im Client eingeloggte
Riot-Account dem PrimeStats-Konto zugeordnet; danach lädt das Tool ohne weitere Eingaben hoch.

Der Client gibt nur die letzten ~20 Spiele heraus. Damit keine Scrims verloren gehen, kann das Tool mit
``--watch`` im Hintergrund laufen und neue Custom Games direkt nach Spielende hochladen
(``--autostart on`` startet es dafür automatisch mit Windows).
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

VERSION = "1.2.0"
#: Feste Server-Adresse – wird beim Bauen der EXE über PRIMESTATS_SERVER_URL eingesetzt
DEFAULT_SERVER = "__PRIMESTATS_SERVER_URL__"
CONFIG_NAME = "primestats-uploader.ini"
HISTORY_PAGE = 20
#: Abfrageintervall im Watch-Modus (Sekunden)
WATCH_INTERVAL = 60
AUTOSTART_NAME = "PrimeStats-Uploader.cmd"
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


def _parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.optionxform = str  # PUUIDs sind case-sensitiv
    return parser


def default_server() -> str:
    if DEFAULT_SERVER.startswith("__"):
        return os.getenv("PRIMESTATS_SERVER_URL", "")
    return DEFAULT_SERVER


@dataclass
class Config:
    server: str = ""
    league_path: str = ""
    max_games: int = 200
    #: Geräteschlüssel je verknüpftem Riot-Account (puuid -> Schlüssel)
    keys: dict | None = None

    @classmethod
    def load(cls, path: Path) -> "Config":
        parser = _parser()
        if path.exists():
            parser.read(path, encoding="utf-8")
        s = parser["primestats"] if parser.has_section("primestats") else {}
        keys = dict(parser["accounts"]) if parser.has_section("accounts") else {}
        return cls(server=s.get("server", "") or default_server(), league_path=s.get("league_path", ""),
                   max_games=int(s.get("max_games", 200)), keys=keys)

    def save(self, path: Path) -> None:
        parser = _parser()
        parser["primestats"] = {"league_path": self.league_path, "max_games": str(self.max_games)}
        if self.server and self.server != default_server():
            parser["primestats"]["server"] = self.server
        parser["accounts"] = dict(self.keys or {})
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
        # Aktuelle Clients liefern nur die letzten ~20 Spiele und ignorieren ältere Seiten;
        # sobald eine Seite nichts Neues bringt, ist Schluss.
        seen: set = set()
        games: list[dict] = []
        start = 0
        while start < max_games:
            page = self.get("/lol-match-history/v1/products/lol/current-summoner/matches",
                            begIndex=start, endIndex=start + HISTORY_PAGE)
            batch = ((page or {}).get("games") or {}).get("games") or []
            new = [g for g in batch if g.get("gameId") not in seen]
            if not new:
                break
            seen.update(g.get("gameId") for g in new)
            games.extend(new)
            start += HISTORY_PAGE
        return games[:max_games]

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
    def __init__(self, base: str, session=None):
        self.base = base.rstrip("/")
        self.session = session or requests.Session()
        self.headers = {"User-Agent": f"PrimeStats-Uploader/{VERSION}"}

    def authenticate(self, puuid: str, key: str) -> None:
        """Uploads laufen unter dem im Client eingeloggten, verknüpften Riot-Account."""
        self.headers.update({"X-Riot-Puuid": puuid, "X-Link-Key": key})

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = self.session.post(self.base + path, json=body, headers=self.headers, timeout=120)
        except requests.RequestException as exc:
            raise UploaderError(f"Server {self.base} nicht erreichbar: {exc}") from exc
        if resp.status_code != 200:
            raise UploaderError(f"{_detail(resp)} (HTTP {resp.status_code})")
        return resp.json()

    def status(self, puuid: str, key: str | None) -> dict:
        return self._post("/api/uploader/status", {"puuid": puuid, "key": key})

    def link(self, code: str, puuid: str, game_name: str, tag_line: str) -> dict:
        return self._post("/api/uploader/link", {"code": code.strip(), "puuid": puuid, "game_name": game_name,
                                                 "tag_line": tag_line})

    def known(self, ids: list[str]) -> set[str]:
        return set(self._post("/api/uploader/known", {"match_ids": ids})["known"])

    def upload(self, items: list[dict]) -> dict:
        return self._post("/api/uploader/games", {"games": items})


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
        log=print, history: list[dict] | None = None) -> Summary:
    summary = Summary(assigned={})
    if history is None:
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


def ensure_linked(server: Server, cfg: Config, path: Path, me: dict, code: str | None = None,
                  ask=input, log=print) -> str:
    """Stellt sicher, dass der eingeloggte Riot-Account verknüpft ist; liefert den Kontonamen."""
    puuid = me["puuid"]
    riot_id = f"{me.get('gameName', '')}#{me.get('tagLine', '')}"
    keys = cfg.keys if cfg.keys is not None else {}
    status = server.status(puuid, keys.get(puuid))
    if status["linked"]:
        server.authenticate(puuid, keys[puuid])
        return status["username"]

    log(f"Der Riot-Account {riot_id} ist noch nicht mit PrimeStats verknüpft.")
    log(f"  1. Öffne {server.base}/account und melde dich an (oder registriere dich).")
    log("  2. Klicke auf „Riot-Account verknüpfen“ und gib den angezeigten Code hier ein.")
    for attempt in range(3):
        entered = code if (code and attempt == 0) else ask("Code: ")
        try:
            result = server.link(entered, puuid, me.get("gameName", ""), me.get("tagLine", ""))
        except UploaderError as exc:
            log(f"  {exc}")
            continue
        keys[puuid] = result["key"]
        cfg.keys = keys
        cfg.save(path)
        server.authenticate(puuid, result["key"])
        log(f"Verknüpft: {riot_id} gehört jetzt zum PrimeStats-Konto {result['username']}.\n")
        return result["username"]
    raise UploaderError("Verknüpfung fehlgeschlagen.")


def print_summary(s: Summary, started: float, log=print) -> None:
    log(f"Fertig in {time.time() - started:.0f}s: {s.uploaded} neue Spiele hochgeladen"
        f"{f', {s.timelines} Timelines ergänzt' if s.timelines else ''}"
        f"{f', {s.errors} Fehler' if s.errors else ''}.")
    for team, n in (s.assigned or {}).items():
        log(f"  → {n} Spiel(e) dem Team {team} zugeordnet")


# ------------------------------------------------------------------ Watch-Modus
class Watcher:
    """Läuft im Hintergrund, wartet auf den Client und lädt neue Custom Games nach jedem Spiel hoch.

    Nicht verknüpfte Riot-Accounts werden übersprungen (verknüpfen: Tool einmal normal starten).
    """

    def __init__(self, cfg: Config, server_factory=None, connect=None, log=print):
        self.cfg = cfg
        self.server_factory = server_factory or (lambda: Server(cfg.server))
        self.connect = connect or (lambda: LeagueClient(find_credentials(cfg.league_path)))
        self.log = log
        self.client: LeagueClient | None = None
        self.server: Server | None = None
        self.puuid: str | None = None
        self.linked = False
        self.handled: set[str] = set()
        self._waiting = False

    def tick(self) -> Summary | None:
        try:
            return self._tick()
        except (UploaderError, requests.RequestException) as exc:
            if self.client is not None:
                self.log(f"Verbindung unterbrochen: {exc}")
            self.client = None  # beim nächsten Durchlauf neu verbinden
            return None

    def _tick(self) -> Summary | None:
        if self.client is None:
            try:
                self.client = self.connect()
                self.client.current_summoner()
            except (UploaderError, requests.RequestException):
                self.client = None
                if not self._waiting:
                    self.log("Warte auf den League Client …")
                    self._waiting = True
                return None
            self._waiting = False
        me = self.client.current_summoner()
        if me.get("puuid") != self.puuid:
            self._switch_account(me)
        if not self.linked:
            return None
        history = self.client.history(self.cfg.max_games)
        new = [g for g in history if is_custom(g) and match_id(g) not in self.handled]
        if not new:
            return None
        started = time.time()
        summary = run(self.client, self.server, self.cfg.max_games, log=self.log, history=history)
        self.handled.update(match_id(g) for g in history if is_custom(g))
        if summary.uploaded or summary.timelines or summary.errors:
            print_summary(summary, started, self.log)
        return summary

    def _switch_account(self, me: dict) -> None:
        self.puuid, self.linked, self.handled = me.get("puuid"), False, set()
        riot_id = f"{me.get('gameName', '')}#{me.get('tagLine', '')}"
        key = (self.cfg.keys or {}).get(self.puuid)
        server = self.server_factory()
        status = server.status(self.puuid, key) if key else {"linked": False}
        if not status["linked"]:
            self.log(f"{riot_id} ist nicht mit PrimeStats verknüpft – wird übersprungen. "
                     "Zum Verknüpfen das Tool einmal ohne --watch starten.")
            return
        server.authenticate(self.puuid, key)
        self.server, self.linked = server, True
        self.log(f"{riot_id} erkannt – lade neue Custom Games für PrimeStats-Konto {status['username']} hoch.")

    def run_forever(self, interval: int = WATCH_INTERVAL, sleep=time.sleep) -> None:
        self.log(f"Watch-Modus: prüfe alle {interval}s auf neue Custom Games (Beenden mit Strg+C).")
        while True:
            self.tick()
            sleep(interval)


def _timestamped(message: str = "") -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}" if message else "", flush=True)


# -------------------------------------------------------------------- Autostart
def startup_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if platform.system() != "Windows" or not appdata:
        raise UploaderError("Autostart gibt es nur unter Windows.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        target = f'"{sys.executable}"'
    else:
        target = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    return f'@echo off\r\nstart "PrimeStats-Uploader" /min {target} --watch\r\n'


def set_autostart(enabled: bool, directory: Path | None = None) -> Path:
    path = (directory or startup_dir()) / AUTOSTART_NAME
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(autostart_command(), encoding="utf-8", newline="")
    elif path.exists():
        path.unlink()
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lädt Custom Games aus dem League Client zu PrimeStats hoch.")
    parser.add_argument("--code", help="Verknüpfungscode von der Website (nur beim ersten Mal nötig)")
    parser.add_argument("--server", help=argparse.SUPPRESS)  # nur für Entwicklung/Tests
    parser.add_argument("--max-games", type=int, help="Wie weit die Match-History durchsucht wird")
    parser.add_argument("--out", type=Path, help="Spiele zusätzlich als JSON-Datei speichern")
    parser.add_argument("--offline", action="store_true", help="Nichts hochladen (nur mit --out sinnvoll)")
    parser.add_argument("--no-pause", action="store_true", help="Am Ende nicht auf Enter warten")
    parser.add_argument("--watch", action="store_true",
                        help="Im Hintergrund laufen und neue Custom Games nach jedem Spiel hochladen")
    parser.add_argument("--interval", type=int, default=WATCH_INTERVAL, help=argparse.SUPPRESS)
    parser.add_argument("--autostart", choices=["on", "off"],
                        help="Watch-Modus beim Windows-Start automatisch starten (on) oder nicht mehr (off)")
    parser.add_argument("--version", action="version", version=f"PrimeStats-Uploader {VERSION}")
    args = parser.parse_args(argv)

    print(f"PrimeStats-Uploader {VERSION}\n")
    path = config_path()
    cfg = Config.load(path)
    if args.server:
        cfg.server = args.server.rstrip("/")
    if args.max_games:
        cfg.max_games = args.max_games

    code = 0
    try:
        if args.autostart:
            if args.server:
                cfg.save(path)  # der Autostart liest die Server-Adresse aus der Konfiguration
            target = set_autostart(args.autostart == "on")
            print(f"Autostart {'eingerichtet' if args.autostart == 'on' else 'entfernt'}: {target}")
            args.no_pause = True
        elif args.watch:
            if not cfg.server:
                raise UploaderError("Keine Server-Adresse eingebaut – bitte mit --server starten.")
            if args.code:  # Verknüpfen und dann direkt weiter beobachten
                me = LeagueClient(find_credentials(cfg.league_path)).current_summoner()
                ensure_linked(Server(cfg.server), cfg, path, me, args.code)
            Watcher(cfg, log=_timestamped).run_forever(max(10, args.interval))
        else:
            if not args.offline and not cfg.server:
                raise UploaderError("Keine Server-Adresse eingebaut – bitte mit --server starten.")
            client = LeagueClient(find_credentials(cfg.league_path))
            me = client.current_summoner()
            server = None
            if not args.offline:
                server = Server(cfg.server)
                account = ensure_linked(server, cfg, path, me, args.code)
                print(f"Lade hoch für PrimeStats-Konto {account}.")
            started = time.time()
            s = run(client, server, cfg.max_games, args.out)
            print()
            if server:
                print_summary(s, started)
                print("\nTipp: Der Client zeigt nur die letzten ~20 Spiele. Mit --watch (oder --autostart on) "
                      "lädt das Tool Scrims automatisch direkt nach Spielende hoch.")
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
