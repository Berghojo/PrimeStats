import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useAnalysis } from "../api/hooks";
import { ChampIcon } from "../components/ChampIcon";
import { MinuteLineChart, PALETTE } from "../components/charts";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { dt } from "../lib/format";
import { useGameData } from "../lib/meta";

const STAT_KEY = "ps-stat";

function storedStat() {
  try {
    return localStorage.getItem(STAT_KEY) ?? "gold";
  } catch {
    return "gold";
  }
}

export function AnalysisPage() {
  const [params] = useSearchParams();
  const ids = params.getAll("m");
  const focus = params.getAll("focus");
  const team = params.get("team") ? Number(params.get("team")) : undefined;
  const { data, error, isPending } = useAnalysis(ids, focus, team);
  const { position } = useGameData();
  const [stat, setStat] = useState(storedStat);
  const [active, setActive] = useState<Set<string> | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STAT_KEY, stat);
    } catch {
      /* egal */
    }
  }, [stat]);

  const colors = useMemo(
    () => Object.fromEntries((data?.players ?? []).map((p, i) => [p.puuid, PALETTE[i % PALETTE.length]])),
    [data],
  );

  if (ids.length === 0) return <Empty>Keine Spiele ausgewählt.</Empty>;
  if (isPending) return <Loading message="Lade Timelines …" />;
  if (error) return <ErrorBox error={error} />;

  const focused = data.players.filter((p) => p.focus);
  const current = active ?? new Set((focused.length ? focused : data.players.slice(0, 5)).map((p) => p.puuid));
  const statKey = data.series[stat] ? stat : "gold";
  const statLabel = data.stats.find((s) => s.key === statKey)?.label ?? statKey;
  const series = data.players
    .filter((p) => current.has(p.puuid))
    .map((p) => ({ label: p.name, data: data.series[statKey]?.[p.puuid] ?? [], color: colors[p.puuid] }));

  const setChips = (mode: "all" | "none" | "focus") =>
    setActive(new Set(mode === "all" ? data.players.map((p) => p.puuid) : mode === "focus" ? focused.map((p) => p.puuid) : []));

  return (
    <>
      <section>
        <h1>Zeitverlauf</h1>
        <div className="muted">Minutenwerte, gemittelt über {data.matches.length} Spiel{data.matches.length !== 1 && "e"} pro Spieler.</div>
      </section>
      {data.players.length === 0 ? (
        <Empty>Für die ausgewählten Spiele sind keine Timeline-Daten verfügbar.</Empty>
      ) : (
        <section className="card stack">
          <div className="row">
            <label className="field">
              Statistik
              <select value={statKey} onChange={(e) => setStat(e.target.value)}>
                {data.stats.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </label>
            <div className="row push">
              <button className="btn small" type="button" onClick={() => setChips("focus")}>Fokus</button>
              <button className="btn small" type="button" onClick={() => setChips("all")}>Alle</button>
              <button className="btn small" type="button" onClick={() => setChips("none")}>Keine</button>
            </div>
          </div>
          <div className="chips">
            {data.players.map((p) => (
              <button
                type="button"
                key={p.puuid}
                className={`chip${current.has(p.puuid) ? " on" : ""}`}
                style={{ "--chip-color": colors[p.puuid] } as React.CSSProperties}
                onClick={() => {
                  const next = new Set(current);
                  if (next.has(p.puuid)) next.delete(p.puuid);
                  else next.add(p.puuid);
                  setActive(next);
                }}
              >
                <span className="dot" />
                {p.name} <span className="muted small">{position(p.position)} · {p.games}×</span>
              </button>
            ))}
          </div>
          <MinuteLineChart series={series} yTitle={statLabel} />
        </section>
      )}
      <section className="card">
        <h2>Ausgewählte Spiele</h2>
        <div className="list-compact">
          {data.matches.map((m) => (
            <div className="item" key={m.match_id}>
              <span className="nowrap muted">{dt(m.created)}</span>
              <span className="champ-row">{m.blue.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} size="sm" />)}</span>
              <span className="muted">vs</span>
              <span className="champ-row">{m.red.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} size="sm" />)}</span>
              <span className="grow" />
              <Link to={`/match/${m.match_id}${team ? `?team=${team}` : ""}`}>Scoreboard</Link>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
