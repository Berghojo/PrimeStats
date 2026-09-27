# PrimeStats-Uploader

Lädt Custom Games (Scrims) aus dem lokalen League Client zu PrimeStats hoch – nur Spiele, die der Server
noch nicht kennt. Hintergrund und Server-Einrichtung: siehe [README im Hauptverzeichnis](../README.md#uploader-scrims-aus-dem-league-client).

```text
PrimeStats-Uploader.exe                    # normaler Start (fragt beim ersten Mal nach Server + Token)
PrimeStats-Uploader.exe --max-games 400    # tiefer in der History suchen
PrimeStats-Uploader.exe --out scrims.json  # zusätzlich als Datei speichern
PrimeStats-Uploader.exe --offline --out scrims.json   # nur exportieren, nichts hochladen
```

Konfiguration (`primestats-uploader.ini` neben der EXE):

```ini
[primestats]
server = https://primestats.example.de
token = <UPLOAD_TOKEN des Servers>
league_path =          ; nur nötig, wenn der Client nicht automatisch gefunden wird
max_games = 200
```

Ohne EXE (Python ≥ 3.10): `pip install -r requirements.txt && python primestats_uploader.py`
