# PrimeStats

Statistik-Tool für **Prime-League- und Custom Games** in League of Legends.

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
  - Spielertabelle: KDA, KP, CS/min, Gold/min, Schaden/min, Schadens- & Goldanteil, Vision/min, Kontrollwards,
    GD/CSD/XPD@15 gegen den Lanegegner (sortierbar); Aushilfen werden separat markiert
  - Champion-Pools pro Spieler, eigene Picks & Bans, Bans gegen das Team, gegnerische Picks
  - Spielliste mit Label (*Prime League* / *Scrim* – Spiele mit Turniercode werden automatisch als Prime League
    markiert), Ausschließen einzelner Spiele und direktem Sprung in die Zeitverlaufs-Analyse
  - Filter nach Spieltyp, Seite, Patch, Gegner (aus Namenskürzeln erkannt) und letzten *N* Spielen

## Schnellstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # LOL_API_KEY eintragen
python main_page.py           # http://127.0.0.1:5000
```

Ohne API-Key lässt sich alles mit generierten Beispieldaten ausprobieren:

```bash
PRIMESTATS_DEMO=1 python main_page.py
```

Im Demo-Modus z.B. nach `NLE Polaris#EUW` suchen oder ein Team mit
`NLE Frostbite#EUW`, `NLE Waldgeist#EUW`, `NLE Polaris#EUW`, `NLE Kompass#EUW`, `NLE Leuchtturm#EUW`
(und optional `NLE Treibholz#EUW`) anlegen. Alle Namen sind frei erfunden.

## Konfiguration (`.env`)

| Variable | Standard | Beschreibung |
|---|---|---|
| `LOL_API_KEY` | – | Riot-API-Key von <https://developer.riotgames.com> |
| `RIOT_REGION` | `europe` | Regionales Routing für account-v1 / match-v5 |
| `SECRET_KEY` | zufällig | Flask-Secret (für Hinweis-Meldungen) |
| `PRIMESTATS_DATA_DIR` | `data` | Ablage für SQLite-Datenbank (Cache + Teams) |
| `PRIMESTATS_DEMO` | `0` | `1` = Beispieldaten statt Riot-API |
| `DDRAGON_FETCH` | `1` | Aktuelle Championdaten von Data Dragon laden (sonst lokale Kopie) |
| `DDRAGON_LANGUAGE` | `de_DE` | Sprache der Championnamen |
| `SYNC_MATCH_COUNT` | `100` | Wie viele Custom Games pro Spieler beim Team-Sync durchsucht werden |

## Wie der Team-Sync funktioniert

1. Für jedes Mitglied werden die Match-IDs der Custom Games geladen (`queue=0` und `type=tourney`).
2. Nur Matches, die bei mindestens *N* Mitgliedern vorkommen, werden überhaupt abgerufen – das spart
   Requests. Anschließend wird geprüft, ob die Spieler wirklich im selben Team standen.
3. Für alle Teamspiele wird die Timeline geladen und zu kompakten Minutenreihen verdichtet.

Alle Antworten der Riot-API werden dauerhaft in SQLite gecacht (Matchdaten ändern sich nicht mehr).
Ein eingebauter Rate-Limiter hält die Limits eines Development-Keys ein (20/s, 100/2 min) und wiederholt
Anfragen bei `429`. Der erste Sync eines Teams kann daher ein paar Minuten dauern, danach geht es schnell.
Der Sync läuft im Hintergrund; die Seite zeigt den Fortschritt an.

## Projektstruktur

```
main_page.py              Einstiegspunkt
primestats/
  config.py               Einstellungen aus Umgebungsvariablen
  riot.py                 Riot-API-Client (Rate-Limit, Retries, Cache)
  store.py                SQLite: API-Cache, Teams, Teamspiele
  ddragon.py              Championdaten (Data Dragon, Offline-Fallback)
  matches.py              match-v5 → Datenobjekte (inkl. Rollenerkennung für Custom Lobbys)
  timeline.py             Timeline → Minutenreihen, Lane-Differenzen, Analyse-Daten
  team_stats.py           Team-Aggregation und Filter
  services.py             Spielersuche, Team-Sync (Hintergrund-Jobs)
  demo.py                 Generierte Beispieldaten im API-Format
  views.py                Flask-Routen
  templates/, static/     Oberfläche (htmx + Chart.js, lokal eingebunden)
tests/                    pytest-Suite (läuft komplett offline mit Demo-Daten)
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
