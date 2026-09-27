# PrimeStats

Statistik-Tool für **Prime-League- und Custom Games** in League of Legends –
**React-Frontend**, **FastAPI-Backend** und **PostgreSQL**.

- **Spielersuche:** Riot-ID eingeben, Turnier- und Custom Games inklusive Draft (Picks & Bans) ansehen,
  Spiele auswählen und im **Zeitverlauf** analysieren (Gold, XP, CS, Schaden, KDA, Kill-Beteiligung sowie
  Gold-/XP-/CS-Differenz zum direkten Lanegegner, pro Minute über die Spiele gemittelt).
- **Team-Tracking:** Ein Team mit den Riot-IDs aller Spieler (inkl. Auswechselspielern) anlegen. PrimeStats
  sucht in den Custom-Game-Historien der Mitglieder alle Spiele, in denen mindestens *N* von ihnen
  **auf derselben Seite** gespielt haben, und fasst sie zusammen:
  - Übersicht: Winrate (gesamt / blau / rot), Spieldauer, Kills & Tode, First Blood / Turm / Drache / Grubs,
    Ø Teamgold-Differenz @10 und @15
  - Ø Golddifferenz im Spielverlauf (alle Spiele, Siege, Niederlagen) und Formkurve (GD@15 je Spiel)
  - Objective-Kontrolle (Drachen, Grubs, Herald, Baron, Atakhan) inkl. Ø Zeitpunkt des ersten eigenen Kills
  - Spielertabelle (sortierbar): KDA, KP, CS/min, Gold/min, Schaden/min, Schadens- & Goldanteil, Vision/min,
    Kontrollwards, GD/CSD/XPD@15 gegen den Lanegegner; Aushilfen werden separat markiert
  - Champion-Pools pro Spieler, eigene Picks & Bans, Bans gegen das Team, gegnerische Picks
  - Spielliste mit Label (*Prime League* / *Scrim* – Spiele mit Turniercode werden automatisch als Prime League
    markiert), Ausschließen einzelner Spiele und direktem Sprung in die Zeitverlaufs-Analyse
  - Filter nach Spieltyp, Seite, Patch, Gegner (aus Namenskürzeln erkannt) und letzten *N* Spielen –
    die Filter stehen in der URL und lassen sich teilen

## Schnellstart mit Docker

```bash
cp .env.example .env              # LOL_API_KEY eintragen (oder PRIMESTATS_DEMO=1)
docker compose up --build         # http://localhost:8000
```

Compose startet PostgreSQL und einen App-Container, der das gebaute React-Frontend und die API ausliefert.
Das Datenbankschema wird beim Start automatisch per Alembic migriert.

Ohne API-Key lässt sich alles mit generierten Beispieldaten ausprobieren (`PRIMESTATS_DEMO=1` in `.env`).
Im Demo-Modus z.B. nach `NLE Polaris#EUW` suchen oder ein Team mit
`NLE Frostbite#EUW`, `NLE Waldgeist#EUW`, `NLE Polaris#EUW`, `NLE Kompass#EUW`, `NLE Leuchtturm#EUW`
(und optional `NLE Treibholz#EUW`) anlegen. Alle Namen sind frei erfunden.

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
| `PRIMESTATS_DEMO` | `0` | `1` = Beispieldaten statt Riot-API |
| `SYNC_MATCH_COUNT` | `100` | Wie viele Custom Games pro Spieler beim Team-Sync durchsucht werden |
| `DDRAGON_FETCH` | `1` | Aktuelle Championdaten von Data Dragon laden (sonst lokale Kopie) |
| `DDRAGON_LANGUAGE` | `de_DE` | Sprache der Championnamen |
| `FRONTEND_DIST` | `frontend/dist` | Gebautes Frontend, das das Backend mit ausliefert |
| `CORS_ORIGINS` | – | Kommagetrennte Origins, falls Frontend und API auf verschiedenen Hosts laufen |

## Wie der Team-Sync funktioniert

1. Für jedes Mitglied werden die Match-IDs der Custom Games geladen (`queue=0` und `type=tourney`).
2. Nur Matches, die bei mindestens *N* Mitgliedern vorkommen, werden überhaupt abgerufen – das spart
   Requests. Anschließend wird geprüft, ob die Spieler wirklich im selben Team standen.
3. Für alle Teamspiele wird die Timeline geladen und zu kompakten Minutenreihen verdichtet.

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
    services.py           Spielersuche, Caching, Team-Sync (Hintergrund-Jobs)
    matches.py            match-v5 → Datenobjekte (inkl. Rollenerkennung für Custom Lobbys)
    timeline.py           Timeline → Minutenreihen, Lane-Differenzen, Analyse-Daten
    team_stats.py         Team-Aggregation und Filter
    ddragon.py            Championdaten (Data Dragon, Offline-Fallback)
    demo.py               Generierte Beispieldaten im API-Format
  migrations/             Alembic-Migrationen
  tests/                  pytest (gegen PostgreSQL)
frontend/
  src/
    api/                  Fetch-Client, TypeScript-Typen, TanStack-Query-Hooks
    pages/                Start, Spieler, Analyse, Scoreboard, Teams, Team-Formular, Team-Dashboard
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
| GET | `/api/teams/{id}/report?label=&side=&patch=&opponent=&last=` | Aggregierte Team-Statistiken |
| POST/GET | `/api/teams/{id}/sync` | Synchronisation starten / Status abfragen |
| PATCH | `/api/teams/{id}/games/{match_id}` | Label ändern, Spiel ein-/ausschließen |

Die vollständige, interaktive Doku gibt es unter `/docs` (OpenAPI).
