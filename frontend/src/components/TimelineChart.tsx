import { useEffect, useMemo, useState } from "react";

import { useAnalysis } from "../api/hooks";
import type { Analysis } from "../api/types";
import { useGameData } from "../lib/meta";
import { MinuteLineChart, PALETTE } from "./charts";
import { ErrorBox, Spinner } from "./ui";
import { InfoTip } from "./InfoTip";

const STAT_KEY = "ps-stat";

function storedStat() {
  try {
    return localStorage.getItem(STAT_KEY) ?? "gold";
  } catch {
    return "gold";
  }
}

/** Minutenwerte je Spieler: Statistik wählen, Spieler ein-/ausblenden. */
export function TimelineChart({ data: raw, teamOnly = false }: { data: Analysis; teamOnly?: boolean }) {
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

  // teamOnly: nur die eigenen Spieler (Fokus), keine Gegner
  const data = useMemo(
    () => (teamOnly ? { ...raw, players: raw.players.filter((p) => p.focus) } : raw),
    [raw, teamOnly],
  );
  const colors = useMemo(
    () => Object.fromEntries(data.players.map((p, i) => [p.puuid, PALETTE[i % PALETTE.length]])),
    [data],
  );

  const focused = data.players.filter((p) => p.focus);
  const known = new Set(data.players.map((p) => p.puuid));
  const current = active
    ? new Set([...active].filter((p) => known.has(p)))
    : new Set((teamOnly ? data.players : focused.length ? focused : data.players.slice(0, 5)).map((p) => p.puuid));
  const statKey = data.series[stat] ? stat : "gold";
  const statLabel = data.stats.find((s) => s.key === statKey)?.label ?? statKey;
  const series = data.players
    .filter((p) => current.has(p.puuid))
    .map((p) => ({ label: p.name, data: data.series[statKey]?.[p.puuid] ?? [], color: colors[p.puuid] }));

  const setChips = (mode: "all" | "none" | "focus") =>
    setActive(new Set(mode === "all" ? data.players.map((p) => p.puuid) : mode === "focus" ? focused.map((p) => p.puuid) : []));

  return (
    <>
      <div className="row">
        <label className="field">
          Statistik
          <select value={statKey} onChange={(e) => setStat(e.target.value)}>
            {data.stats.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        <div className="row push">
          {!teamOnly && <button className="btn small" type="button" onClick={() => setChips("focus")}>Fokus</button>}
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
    </>
  );
}

/** Zeitverlauf direkt im Report: folgt der Spielauswahl in der Spieletabelle. */
export function InlineTimeline({ ids, focus, team }: { ids: string[]; focus?: string[]; team?: number }) {
  const sorted = useMemo(() => [...ids].sort(), [ids]);
  const { data, error, isPending, isFetching } = useAnalysis(sorted, focus ?? [], team);
  return (
    <section className={`card stack${isFetching && data ? " refreshing" : ""}`}>
      <div className="row between">
        <div>
          <h2>
            Zeitverlauf
            <InfoTip>
              Minutenwerte der Teamspieler, gemittelt über die im Spiele-Tab ausgewählten Spiele (höchstens die 20 neuesten)
              {data ? ` (${data.matches.length})` : ""}.
            </InfoTip>
          </h2>
        </div>
        {isFetching && <Spinner />}
      </div>
      {ids.length === 0 ? (
        <p className="muted">
          Keine Spiele ausgewählt.
          <InfoTip>Im Spiele-Tab Spiele auswählen, um ihren Zeitverlauf zu sehen.</InfoTip>
        </p>
      ) : error ? (
        <ErrorBox error={error} />
      ) : isPending ? (
        <p className="muted">Lade Timelines …</p>
      ) : !data.players.some((p) => p.focus) ? (
        <p className="muted">Für die ausgewählten Spiele sind keine Timeline-Daten verfügbar.</p>
      ) : (
        <TimelineChart data={data} teamOnly />
      )}
    </section>
  );
}
