# PrimeStats-Uploader

Lädt Custom Games (Scrims) aus dem lokalen League Client zu PrimeStats hoch – nur Spiele, die der Server
noch nicht kennt. Hintergrund: siehe [README im Hauptverzeichnis](../README.md#uploader-scrims-aus-dem-league-client).

Beim ersten Start mit einem Riot-Account fragt das Tool nach einem Verknüpfungscode. Den erzeugt man auf der
PrimeStats-Website unter **Konto → „Riot-Account verknüpfen“**. Danach lädt das Tool bei jedem Start ohne
Rückfrage hoch.

Der Client gibt nur die **letzten ~20 Spiele** heraus. Damit keine Scrims verloren gehen, am besten den
Watch-Modus nutzen (`--watch`, per `--autostart on` automatisch beim Windows-Start).

```text
PrimeStats-Uploader.exe                    # normaler Start
PrimeStats-Uploader.exe --code K7QX-M2PA   # Code direkt übergeben
PrimeStats-Uploader.exe --watch            # im Hintergrund laufen, nach jedem Spiel hochladen
PrimeStats-Uploader.exe --autostart on     # Watch-Modus mit Windows starten (off = entfernen)
PrimeStats-Uploader.exe --out scrims.json  # zusätzlich als Datei speichern
PrimeStats-Uploader.exe --offline --out scrims.json   # nur exportieren, nichts hochladen
```

`primestats-uploader.ini` neben der EXE (wird automatisch angelegt):

```ini
[primestats]
league_path =          ; nur nötig, wenn der Client nicht automatisch gefunden wird
max_games = 200

[accounts]
; <PUUID> = <Geräteschlüssel>  – wird beim Verknüpfen gespeichert, nicht weitergeben
```

Die Server-Adresse ist in die EXE eingebaut (beim Bauen aus `PRIMESTATS_SERVER_URL`). Ohne EXE
(Python ≥ 3.10): `pip install -r requirements.txt && PRIMESTATS_SERVER_URL=https://… python primestats_uploader.py`
