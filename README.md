# PrimeStats

Statistik-Tool für **Prime-League- und Custom Games** in League of Legends –
**React-Frontend**, **FastAPI-Backend** und **PostgreSQL**.

- **Spielersuche:** Riot-ID eingeben, Turnier- und Custom Games inklusive Draft (Picks & Bans) ansehen,
  Spiele auswählen und im **Zeitverlauf** analysieren (Gold, XP, CS, Schaden, KDA, Kill-Beteiligung sowie
  Gold-/XP-/CS-Differenz zum direkten Lanegegner, pro Minute über die Spiele gemittelt).
- **Scrims aus dem League Client:** Die Riot-API liefert Custom Games nur mit Turniercode. Normale
  Custom-Lobbys lädt der **PrimeStats-Uploader** (Windows-EXE) aus dem lokalen League Client hoch –
  nur Spiele, die der Server noch nicht kennt. Siehe [Uploader](#uploader-scrims-aus-dem-league-client).
- **Team-Tracking:** Ein Team mit den Riot-IDs aller Spieler (inkl. Auswechselspielern) anlegen. PrimeStats
  sucht in den Custom-Game-Historien der Mitglieder alle Spiele, in denen mindestens *N* von ihnen
  **auf derselben Seite** gespielt haben, und fasst sie zusammen:
  - Übersicht: Winrate (gesamt / blau / rot), Spieldauer, Kills & Tode, First Blood / Turm / Drache / Grubs,
    Ø Teamgold-Differenz @10 und @15
  - Ø Golddifferenz im Spielverlauf (alle Spiele, Siege, Niederlagen) und Formkurve (GD@15 je Spiel)
  - Objective-Kontrolle (Drachen, Grubs, Herald, Baron, Atakhan) inkl. Ø Zeitpunkt des ersten eigenen Kills
  - Spielertabelle (sortierbar): KDA, KP, CS/min, Gold/min, Schaden/min, Schadens- & Goldanteil, Vision/min,
    Kontrollwards, GD/CSD/XPD@15 gegen den Lanegegner; Aushilfen werden separat markiert
  - Champion-Pick-Tabelle (Picks, Siege, WR, KDA, CS/min, Schaden/min, wer spielt ihn, eigene Bans, Bans des
    Gegners, Präsenz; sortierbar, nach Rolle filterbar) – für Team-/Scrim-Ansicht und Scouting
  - Champion-Pools pro Spieler, eigene Picks & Bans, Bans gegen das Team, gegnerische Picks
  - Spielliste mit Label (*Prime League* / *Scrim* – Spiele mit Turniercode werden automatisch als Prime League
    markiert), Ausschließen einzelner Spiele und direktem Sprung in die Zeitverlaufs-Analyse
  - Gegner pro Spiel frei eintragbar (z.B. für Scrims), Filter nach Spieltyp, Seite, Patch und letzten *N* Spielen –
    die Filter stehen in der URL und lassen sich teilen

## Schnellstart mit Docker

```bash
cp .env.example .env              # LOL_API_KEY eintragen (oder PRIMESTATS_DEMO=1)
docker compose up --build         # http://localhost:8000
```

Compose startet PostgreSQL und einen App-Container, der das gebaute React-Frontend und die API ausliefert.
Das Datenbankschema wird beim Start automatisch per Alembic migriert.

Ohne API-Key lässt sich alles mit generierten Beispieldaten ausprobieren (`PRIMESTATS_DEMO=1` in `.env`;
die Demo-Scrims werden beim Start so importiert, als kämen sie vom Uploader). Im Demo-Modus gibt es das
Konto `demo` / `demo1234` (verknüpft mit `NLE Polaris#EUW`), das öffentliche Team „Nordlicht Esports“ und
ein Beispiel-Scouting ab `BSK Skalde#EUW` (weitere z.B. mit `RHW Anker#EUW`).
Im Demo-Modus z.B. nach `NLE Polaris#EUW` suchen oder ein Team mit
`NLE Frostbite#EUW`, `NLE Waldgeist#EUW`, `NLE Polaris#EUW`, `NLE Kompass#EUW`, `NLE Leuchtturm#EUW`
(und optional `NLE Treibholz#EUW`) anlegen. Alle Namen sind frei erfunden.

## Turnier-Scouting

Unter **Scouting** (oder „Team scouten“ auf einer Spielerseite) gibt man **einen oder mehrere Spieler** ein
(bis zu 5). Ausgewertet werden alle Turniercode-Spiele (Prime League), in denen **alle eingegebenen Spieler im
selben Team** standen – bei einem Spieler also alle seine Turnierspiele, bei mehreren nur die Spiele dieses
Lineups. Die übrigen Spieler dieser Spiele werden als Mitspieler angezeigt.

Der Report enthält Winrate je Seite, Objectives, Goldverlauf, Spielerwerte, Champion-Pools, die
Champion-Pick-Tabelle, Picks & Bans und die Spielliste. Scouting ist für alle offen (auch ohne Konto), nutzt
nur öffentliche Riot-API-Daten – hochgeladene Scrims fließen nie ein – und braucht deshalb einen `LOL_API_KEY`.
Ergebnisse werden je Spielerkombination gespeichert und sind über „Zuletzt gescoutet“ bzw. ihre URL erneut
abrufbar; „Neu scouten“ aktualisiert sie.

## Konten und Riot-Verknüpfung

Auf der Website legt man ein **Konto** an (Benutzername + Passwort). Ein Riot-Account wird **über den
Uploader** mit dem Konto verknüpft – nur wer im League Client mit dem Account eingeloggt ist, kann ihn
verknüpfen:

1. Konto → „Riot-Account verknüpfen“ erzeugt einen Einmal-Code (z.B. `K7QX-M2PA`, 15 Minuten gültig).
2. Uploader starten: Er erkennt den im Client eingeloggten Riot-Account, fragt nach dem Code und meldet
   sich damit beim Server. Die Website zeigt die Verknüpfung sofort an.
3. Ab dann lädt der Uploader für diesen Riot-Account ohne Rückfrage hoch. Er bekommt dafür beim
   Verknüpfen einen Geräteschlüssel, den er sich in `primestats-uploader.ini` merkt – es gibt keinen
   Token zum Abtippen. Mehrere Riot-Accounts (z.B. Smurfs) lassen sich an ein Konto hängen; wird ein
   Account mit einem neuen Code verknüpft, zieht er zum neuen Konto um.

Was Konten und Verknüpfungen steuern:

| | Anonym | Angemeldet | Riot-Account im Kader |
|---|---|---|---|
| Turniercode-Spiele (Riot-API) suchen/ansehen | ✓ | ✓ | ✓ |
| Turnier-Scouting | ✓ | ✓ | ✓ |
| Hochgeladene Scrims ansehen | – | – | nur Scrims der eigenen Teams |
| Öffentliche Teams ansehen (ohne Scrims) | ✓ | ✓ | ✓ |
| Private Teams ansehen | – | nur selbst erstellte | ✓ |
| Team anlegen | – | ✓ | ✓ |
| Team bearbeiten, synchronisieren, Spiele labeln | – | Ersteller | ✓ |
| Team löschen | – | Ersteller | – |
| Scrims hochladen | – | – | eigene Spiele (Uploader) |

Scrims sieht ausschließlich, wessen verknüpfter Riot-Account im Kader eines Teams steht, dem das Spiel
zugeordnet ist – auch bei öffentlichen Teams, für Team-Ersteller ohne eigenen Account im Kader und im
Scouting nicht. So kann niemand ein Team aus fremden Riot-IDs anlegen, um deren Scrims zu sehen.

Passwörter werden mit scrypt gehasht, Sessions laufen über ein `HttpOnly`-Cookie (`SameSite=Lax`, bei HTTPS
`Secure`); ändernde Anfragen brauchen zusätzlich den Header `X-Requested-With: PrimeStats` (CSRF-Schutz).
Login, Registrierung und Code-Eingabe sind rate-limitiert.

> Der Nachweis „im Client eingeloggt“ stammt vom Uploader auf dem Rechner des Spielers. Er schützt gut gegen
> versehentliche oder fremde Verknüpfungen, ist aber keine kryptografische Bestätigung durch Riot – das ginge
> nur über Riot Sign-On (RSO), wofür ein von Riot freigegebener Production-Key nötig ist.

## Uploader: Scrims aus dem League Client

Die Riot-API gibt Custom Games aus Datenschutzgründen nur heraus, wenn sie per **Turniercode** erstellt
wurden (Prime-League-Spiele). Normale Custom-Lobbys kennt nur der League Client selbst – über seine lokale
Schnittstelle (LCU-API). Der Uploader liest sie dort aus:

1. `PrimeStats-Uploader.exe` herunterladen (GitHub → Releases bzw. Actions-Artefakt „PrimeStats-Uploader“),
   League Client starten und einloggen, Uploader starten.
2. Beim ersten Start mit einem Riot-Account: Code von der Website eingeben (siehe oben).
3. Das Tool liest die Match-History (standardmäßig die letzten 200 Spiele), fragt den Server, welche
   Custom Games schon bekannt sind, und lädt nur neue Spiele samt Timeline hoch. Der Server nimmt nur
   Spiele an, in denen einer der verknüpften Riot-Accounts mitgespielt hat, und ordnet sie automatisch
   allen passenden Teams zu (Label „Scrim“).

Die Server-Adresse ist fest in die EXE eingebaut: Die GitHub-Action `uploader.yml` setzt dafür die
Repository-Variable `PRIMESTATS_SERVER_URL` ein (Settings → Secrets and variables → Actions → Variables).
Bei einem Tag `uploader-v*` hängt sie die EXE an ein Release.

Ein Teammitglied reicht, wenn es bei (fast) allen Scrims dabei ist – jedes Spiel enthält alle 10 Spieler.
Doppelte Uploads werden erkannt; fehlende Timelines werden bei einem späteren Upload ergänzt. Die Rohdaten
aus dem Client werden zusätzlich gespeichert (`raw_imports`), damit sie bei Verbesserungen des Konverters
neu verarbeitet werden können.

Ohne `LOL_API_KEY` läuft PrimeStats im **Upload-Modus**: Spielersuche, Teams und Statistiken basieren dann
ausschließlich auf hochgeladenen Spielen (Spieler sind über Uploads und Verknüpfungen bekannt).

> Die LCU-API ist nicht offiziell dokumentiert. Die Endpunkte (`/lol-match-history/v1/…`) entsprechen dem
> Stand der Community-Dokumentation; nach Client-Patches kann eine Anpassung nötig sein.

## Entwicklung

```bash
docker compose up -d db                       # nur PostgreSQL

# Backend (Python ≥ 3.11) – http://127.0.0.1:8000, API-Doku unter /docs
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn primestats.app:app --reload

# Frontend (Node ≥ 20) – http://localhost:5173, leitet /api an das Backend weiter
cd frontend
npm install
npm run dev
```

### Tests

```bash
# Backend: braucht eine PostgreSQL-Testdatenbank (Name muss "test" enthalten, das Schema wird geleert)
docker compose exec db createdb -U primestats primestats_test
cd backend && TEST_DATABASE_URL=postgresql://primestats:primestats@localhost:5432/primestats_test pytest

# Frontend
cd frontend && npm run typecheck && npm test
```

Die GitHub-Actions-Pipeline (`.github/workflows/ci.yml`) führt beides aus – das Backend gegen einen
PostgreSQL-Service-Container.

### Datenbank-Migrationen

```bash
cd backend
alembic upgrade head                                  # manuell migrieren (AUTO_MIGRATE=0)
alembic revision --autogenerate -m "Beschreibung"     # neue Migration nach Modelländerung
```

## Konfiguration (Umgebungsvariablen / `.env`)

| Variable | Standard | Beschreibung |
|---|---|---|
| `LOL_API_KEY` | – | Riot-API-Key von <https://developer.riotgames.com> |
| `RIOT_REGION` | `europe` | Regionales Routing für account-v1 / match-v5 |
| `DATABASE_URL` | `postgresql+psycopg://primestats:primestats@localhost:5432/primestats` | PostgreSQL-Verbindung (`postgres://…` wird ebenfalls akzeptiert) |
| `AUTO_MIGRATE` | `1` | Schema beim Start per Alembic aktualisieren |
| `SESSION_DAYS` | `30` | Wie lange eine Anmeldung gültig bleibt |
| `COOKIE_SECURE` | `auto` | Session-Cookie nur per HTTPS (`auto` = je nach Anfrage, `1`/`0` erzwingen) |
| `UPLOADER_URL` | GitHub-Releases | Download-Link für den Uploader, der im Frontend angezeigt wird |
| `PRIMESTATS_DEMO` | `0` | `1` = Beispieldaten statt Riot-API |
| `SYNC_MATCH_COUNT` | `100` | Wie viele Custom Games pro Spieler beim Team-Sync durchsucht werden |
| `DDRAGON_FETCH` | `1` | Aktuelle Championdaten von Data Dragon laden (sonst lokale Kopie) |
| `DDRAGON_LANGUAGE` | `de_DE` | Sprache der Championnamen |
| `FRONTEND_DIST` | `frontend/dist` | Gebautes Frontend, das das Backend mit ausliefert |
| `CORS_ORIGINS` | – | Kommagetrennte Origins, falls Frontend und API auf verschiedenen Hosts laufen |

## Wie der Team-Sync funktioniert

1. Bereits gespeicherte Spiele (z.B. hochgeladene Scrims), an denen Mitglieder beteiligt waren, werden geprüft.
2. Für jedes Mitglied werden über die Riot-API die Match-IDs der Turniercode-Spiele geladen (`type=tourney`).
   Nur Matches, die bei mindestens *N* Mitgliedern vorkommen, werden überhaupt abgerufen – das spart Requests.
3. In beiden Fällen wird geprüft, ob die Spieler wirklich im selben Team standen.
4. Für alle Teamspiele wird die Timeline geladen und zu kompakten Minutenreihen verdichtet.

Alle Antworten der Riot-API werden dauerhaft als JSONB in PostgreSQL gespeichert (Matchdaten ändern sich
nicht mehr). Ein eingebauter Rate-Limiter hält die Limits eines Development-Keys ein (20/s, 100/2 min) und
wiederholt Anfragen bei `429`. Der erste Sync eines Teams kann daher ein paar Minuten dauern; er läuft im
Hintergrund, das Frontend zeigt den Fortschritt an.

## Architektur

```
backend/
  primestats/
    app.py                FastAPI-App (Lifespan, Fehlerbehandlung, Auslieferung des Frontends)
    api.py                REST-Endpunkte unter /api
    schemas.py            Pydantic-Modelle der API
    db.py                 SQLAlchemy-Modelle (JSONB für Matches/Timelines)
    store.py              Datenzugriff (PostgreSQL-Upserts)
    migrate.py            Alembic beim Start ausführen
    riot.py               Riot-API-Client (Rate-Limit, Retries)
    lcu.py                League-Client-Format → match-v5 (für hochgeladene Scrims)
    accounts_api.py       Konten, Anmeldung, Riot-Verknüpfung, Uploader-Endpunkte
    access.py             Sichtbarkeit und Berechtigungen
    scout_api.py          Turnier-Scouting (Spiele, in denen alle gesuchten Spieler zusammen spielten)
    auth.py               Passwort-Hashing (scrypt), Tokens, Verknüpfungscodes
    services.py           Spielersuche, Caching, Team-Sync (Hintergrund-Jobs)
    matches.py            match-v5 → Datenobjekte (inkl. Rollenerkennung für Custom Lobbys)
    timeline.py           Timeline → Minutenreihen, Lane-Differenzen, Analyse-Daten
    team_stats.py         Team-Aggregation und Filter
    ddragon.py            Championdaten (Data Dragon, Offline-Fallback)
    demo.py               Generierte Beispieldaten im API-Format
  migrations/             Alembic-Migrationen
  tests/                  pytest (gegen PostgreSQL)
uploader/
  primestats_uploader.py  Uploader-Tool (wird per PyInstaller zur Windows-EXE)
frontend/
  src/
    api/                  Fetch-Client, TypeScript-Typen, TanStack-Query-Hooks
    pages/                Start, Spieler, Analyse, Scoreboard, Teams, Team-Formular, Team-Dashboard, Scouting, Uploader, Login, Konto
    components/           UI-Bausteine, Charts (Chart.js), Team-Dashboard-Komponenten
```

### API-Überblick

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/meta` | Demo-Status, Championdaten, Labels |
| GET | `/api/players/{name}/{tag}/games?count=20` | Custom Games eines Spielers |
| GET | `/api/matches/{match_id}` | Scoreboard eines Spiels |
| GET | `/api/analysis?m=…&m=…&focus=…&team=…` | Minutenreihen für die Zeitverlaufs-Analyse |
| GET/POST | `/api/teams` | Teams auflisten / anlegen |
| GET/PUT/DELETE | `/api/teams/{id}` | Team lesen / bearbeiten / löschen |
| GET | `/api/teams/{id}/report?label=&side=&patch=&last=` | Aggregierte Team-Statistiken |
| POST/GET | `/api/teams/{id}/sync` | Synchronisation starten / Status abfragen |
| PATCH | `/api/teams/{id}/games/{match_id}` | Label, Gegner (Freitext) ändern, Spiel ein-/ausschließen |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | Konto anlegen, an-/abmelden (Cookie) |
| GET | `/api/auth/me` | Angemeldetes Konto + verknüpfte Riot-Accounts |
| POST | `/api/me/link-code` | Einmal-Code für die Verknüpfung erzeugen |
| DELETE | `/api/me/riot/{puuid}` | Verknüpfung lösen |
| POST | `/api/uploader/status`, `/api/uploader/link` | Uploader: Verknüpfung prüfen / per Code herstellen |
| POST | `/api/uploader/known`, `/api/uploader/games` | Uploader: bekannte Match-IDs abfragen / Spiele hochladen |
| POST | `/api/scout` | Scouting starten (`riot_ids`: 1–5 Spieler, die im selben Team stehen müssen) |
| GET | `/api/scout`, `/api/scout/{key}`, `/api/scout/{key}/status` | Letzte Scoutings, Report (mit Filtern), Fortschritt |

Die vollständige, interaktive Doku gibt es unter `/docs` (OpenAPI).
