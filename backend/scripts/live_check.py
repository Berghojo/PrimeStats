"""Live-Check gegen die echte Riot-API (für CI/Handtests).

    LOL_API_KEY=… DATABASE_URL=… python scripts/live_check.py "Herr Grey#6781"

Prüft Spielersuche, Scouting (ein Spieler sowie zwei Spieler in beiden Modi) und Team-Sync
und schreibt eine Markdown-Zusammenfassung nach stdout bzw. $GITHUB_STEP_SUMMARY.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from primestats.ddragon import DataDragon  # noqa: E402
from primestats.migrate import upgrade  # noqa: E402
from primestats.riot import RiotAPIError, RiotClient  # noqa: E402
from primestats.services import PrimeStats, SyncJob  # noqa: E402
from primestats.store import Member, Store, Team  # noqa: E402
from primestats.team_stats import build_report  # noqa: E402

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def pct(v):
    return "–" if v is None else f"{v:.0%}"


def num(v, d=1):
    return "–" if v is None else f"{v:,.{d}f}"


def report_block(title: str, rep: dict, dd: DataDragon) -> None:
    ov = rep["overview"]
    say(f"**{title}:** {ov['games']} Spiele, {ov['wins']} Siege ({pct(ov['winrate'])}), "
        f"Blau {ov['blue_wins']}/{ov['blue_games']}, Rot {ov['red_wins']}/{ov['red_games']}, "
        f"Ø {num((ov['duration'] or 0) / 60)} min, First Blood {pct(ov['first_blood'])}, "
        f"GD@10 {num(ov['gd10'], 0)}, GD@15 {num(ov['gd15'], 0)} (Timelines: {ov['timeline_games']})")
    say()
    say("| Spieler | Rolle | Spiele | WR | KDA | CS/min | KP | GD@15 |")
    say("|---|---|---|---|---|---|---|---|")
    for p in rep["players"][:10]:
        say(f"| {p['name']} | {p['position']} | {p['games']} | {pct(p['winrate'])} | {num(p['kda'], 2)} | "
            f"{num(p['cspm'])} | {pct(p['kp'])} | {num(p['gd15'], 0)} |")
    say()
    say("| Champion | Rollen | Spieler | Picks | WR | KDA | Bans eigene | Bans Gegner | Präsenz |")
    say("|---|---|---|---|---|---|---|---|---|")
    for r in rep["champion_table"][:12]:
        roles = ", ".join(f"{x['position']}({x['games']})" for x in r["positions"]) or "–"
        players = ", ".join(f"{x['name']}({x['games']})" for x in r["players"]) or "nur gebannt"
        say(f"| {dd.champion(r['champion_id']).name} | {roles} | {players} | {r['picks']} | {pct(r['winrate'])} | "
            f"{num(r['kda'], 2)} | {r['bans_by_us']} | {r['bans_against']} | {pct(r['presence'])} |")
    say()


def main() -> int:
    riot_id = sys.argv[1] if len(sys.argv) > 1 else "Herr Grey#6781"
    key = os.environ["LOL_API_KEY"]
    store = Store.from_url(os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost/primestats"))
    upgrade(store.engine)
    svc = PrimeStats(store, RiotClient(key))
    dd = DataDragon(fetch=True)
    started = time.time()

    say(f"# PrimeStats Live-Check: {riot_id}")
    acc = svc.account(riot_id)
    say(f"Account gefunden: `{acc['gameName']}#{acc['tagLine']}`")
    say()

    # 0) Was steckt in der Turnier-Liste der Riot-API?
    from collections import Counter
    ids = svc.custom_match_ids(acc["puuid"], 100)
    kinds = Counter((svc.match(m).game_type, svc.match(m).queue_id) for m in ids)
    say(f"Turnier-Liste (type=tourney): {len(ids)} Einträge – " +
        ", ".join(f"{gt} / Queue {q}: {n}" for (gt, q), n in kinds.most_common()))
    say()

    # 1) Spielersuche
    _, games = svc.player_games(riot_id, 20)
    say(f"## Spielersuche – {len(games)} Turnierspiele (von max. 20)")
    say("| Datum | Match | Ergebnis | Rolle | Champion | K/D/A | Turniercode |")
    say("|---|---|---|---|---|---|---|")
    for g in games:
        me = g.player(acc["puuid"])
        say(f"| {g.created:%d.%m.%Y} | {g.match_id} | {'Sieg' if me.win else 'Niederlage'} | {me.position} | "
            f"{dd.champion(me.champion_id).name} | {me.kills}/{me.deaths}/{me.assists} | {'ja' if g.tournament_code else 'nein'} |")
    say()
    if not games:
        say("Keine Turnierspiele gefunden – Scouting/Team-Test übersprungen.")
        return finish(started)

    def scout(accounts, mode="all", title=""):
        job = SyncJob("live")
        try:
            k = svc.scout(accounts, job, mode=mode, timelines=15)
        except RiotAPIError as exc:
            say(f"**{title} [{mode}]:** {exc.message}")
            say()
            return None
        sc = store.get_scout(k)
        team = Team(0, "x", "", 1, sc["updated_at"], None,
                    [Member(r["puuid"], r["game_name"], r["tag_line"], r["position"]) for r in sc["roster"]])
        say(f"Kader: " + ", ".join(f"{r['game_name']}{'*' if r['searched'] else ''} ({r['games']})" for r in sc["roster"]))
        say()
        report_block(f"{title} [{mode}]", build_report(team, svc.scout_records(sc)), dd)
        return sc

    # 2) Scouting ein Spieler
    say("## Scouting – ein Spieler")
    sc = scout([acc], title=riot_id)
    if sc is None:
        return finish(started)

    # 3) Scouting zwei Spieler: häufigster Mitspieler, beide Modi
    mate = next((r for r in sc["roster"] if not r["searched"]), None)
    if mate:
        mate_acc = {"puuid": mate["puuid"], "gameName": mate["game_name"], "tagLine": mate["tag_line"]}
        names = f"{riot_id} + {mate['game_name']}#{mate['tag_line']}"
        say("## Scouting – zwei Spieler")
        scout([acc, mate_acc], "all", names)
        scout([acc, mate_acc], "any", names)

    # 4) Team aus den 5 häufigsten Kader-Spielern, Sync über die Riot-API
    roster = sc["roster"][:5]
    team_id = store.create_team("Live-Check", "", 4, [Member(r["puuid"], r["game_name"], r["tag_line"], "")
                                                      for r in roster])
    job = SyncJob(team_id)
    svc.sync_team(store.get_team(team_id), job)
    team = store.get_team(team_id)
    records = svc.team_records(team)
    say(f"## Team-Sync – {', '.join(r['game_name'] for r in roster)}")
    say(f"{job.new_games} Teamspiele gefunden (≥ 4 Spieler zusammen).")
    say()
    if records:
        report_block("Team", build_report(team, records), dd)
    return finish(started)


def finish(started: float) -> int:
    say(f"_Laufzeit: {time.time() - started:.0f} s_")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).write_text("\n".join(out) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
