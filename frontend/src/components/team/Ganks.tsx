import { useMemo, useState } from "react";

import type { DeathEvent, DeathKind, PlayerReport } from "../../api/types";
import { dt, duration } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { MapBase, SIZE, Slider, px, py } from "./Jungle";
import { InfoTip } from "../InfoTip";

const KINDS: { key: DeathKind; label: string; color: string; hint: string }[] = [
  { key: "gank", label: "Gank", color: "#ffc23d", hint: "gegnerischer Jungler beteiligt" },
  { key: "roam", label: "Roam", color: "#c084fc", hint: "Laner einer anderen Lane beteiligt (bei Junglern: irgendein Laner)" },
  { key: "gank_roam", label: "Gank + Roam", color: "#ff7a45", hint: "Jungler und Laner einer anderen Lane" },
  { key: "lane", label: "Lane", color: "#4c8dff", hint: "nur die direkten Lane-Gegner" },
  { key: "duel", label: "Jungle 1v1", color: "#5ff2de", hint: "Jungler nur gegen den gegnerischen Jungler" },
  { key: "other", label: "Sonstige", color: "#8b93a5", hint: "ohne gegnerischen Champion (Turm, Minions)" },
];
const COLOR = Object.fromEntries(KINDS.map((k) => [k.key, k.color])) as Record<DeathKind, string>;
const LABEL = Object.fromEntries(KINDS.map((k) => [k.key, k.label])) as Record<DeathKind, string>;
const ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

const mmss = (t: number) => duration(t);

/** Tode der eigenen Spieler nach Ursache: Ganks und Roams gegen Laner, Roams gegen den Jungler. */
export function GankCard({ deaths, players }: { deaths: DeathEvent[]; players: PlayerReport[] }) {
  const { position, champion } = useGameData();
  const members = useMemo(
    () => players.filter((p) => p.member).sort((a, b) => ORDER.indexOf(a.position) - ORDER.indexOf(b.position)),
    [players],
  );
  const [who, setWho] = useState<string | null>(null);
  const [from, setFrom] = useState(0);
  const [to, setTo] = useState(15);
  const [hidden, setHidden] = useState<Set<DeathKind>>(new Set(["other"]));
  const [hover, setHover] = useState<DeathEvent | null>(null);
  const lastMinute = Math.max(15, Math.ceil(Math.max(0, ...deaths.map((d) => d.t)) / 60));

  const inWindow = deaths.filter((d) => d.t >= from * 60 && d.t <= to * 60);
  const shown = inWindow.filter((d) => (!who || d.puuid === who) && !hidden.has(d.kind));

  const rows = members.map((p) => {
    const mine = inWindow.filter((d) => d.puuid === p.puuid);
    const count = (k: DeathKind) => mine.filter((d) => d.kind === k).length;
    // wer roamt/gankt am häufigsten auf diesen Spieler?
    const roamers = new Map<string, number>();
    for (const d of mine) {
      if (d.kind === "lane" || d.kind === "other") continue;
      const own = p.position === "JUNGLE";
      for (const b of d.by) {
        const lane = (pos: string) => (pos === "UTILITY" ? "BOTTOM" : pos);
        const isRoamer = own ? b.position !== "JUNGLE" : b.position === "JUNGLE" || lane(b.position) !== lane(p.position);
        if (isRoamer) roamers.set(b.position, (roamers.get(b.position) ?? 0) + 1);
      }
    }
    const top = [...roamers.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
    return { p, total: mine.length, count, top };
  });

  const toggleKind = (k: DeathKind) => setHidden((s) => {
    const next = new Set(s);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    return next;
  });

  return (
    <section className="card stack">
      <div>
        <h2>
          Ganks &amp; Roams
          <InfoTip>
            Wo und wodurch die eigenen Spieler sterben: Laner durch Ganks und Roams, Jungler durch roamende Laner.
            Grundlage sind die an einem Kill beteiligten Gegner laut Timeline.
            <br /><br />
            <b>Gank</b> = gegnerischer Jungler beteiligt · <b>Roam</b> = Laner einer anderen Lane beteiligt (Bot und Support
            gelten als eine Lane); beim Jungler zählt jeder beteiligte Laner als Roam · <b>Lane / 1v1</b> = nur die direkten
            Gegner · <b>Sonstige</b> = ohne gegnerischen Champion (Turm, Minions).
          </InfoTip>
        </h2>
      </div>
      <div className="jungle-grid">
        <div className="stack">
          <div className="chips">
            <button type="button" className={`chip${who === null ? " on" : ""}`} onClick={() => setWho(null)}>
              <span className="dot" />Alle Spieler
            </button>
            {members.map((p) => (
              <button type="button" key={p.puuid} className={`chip${who === p.puuid ? " on" : ""}`}
                aria-pressed={who === p.puuid} onClick={() => setWho(who === p.puuid ? null : p.puuid)}>
                <span className="dot" />{p.name} <span className="muted small">{position(p.position)}</span>
              </button>
            ))}
          </div>
          <div className="sliders">
            <Slider label="Von Minute" value={from} min={0} max={lastMinute} onChange={(v) => {
              setFrom(v);
              if (v > to) setTo(v);
            }} />
            <Slider label="Bis Minute" value={Math.min(to, lastMinute)} min={0} max={lastMinute} onChange={(v) => {
              setTo(v);
              if (v < from) setFrom(v);
            }} />
          </div>
          <div className="chips">
            {KINDS.map((k) => (
              <button type="button" key={k.key} title={k.hint} aria-pressed={!hidden.has(k.key)}
                className={`chip${hidden.has(k.key) ? "" : " on"}`} style={{ "--chip-color": k.color } as React.CSSProperties}
                onClick={() => toggleKind(k.key)}>
                <span className="dot" />{k.label}
              </button>
            ))}
          </div>
          <div className="map">
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="map-layer" onMouseLeave={() => setHover(null)}>
              <MapBase />
              {shown.map((d, i) => (
                <g key={i} onMouseEnter={() => setHover(d)} style={{ cursor: "pointer" }}>
                  <circle cx={px(d.x)} cy={py(d.y)} r={12} fill="transparent" />
                  <circle cx={px(d.x)} cy={py(d.y)} r={hover === d ? 8 : 5.5} fill={COLOR[d.kind]}
                    stroke="#07090d" strokeWidth={2} opacity={hover && hover !== d ? 0.35 : 0.95} />
                </g>
              ))}
            </svg>
          </div>
          <div className="muted small" aria-live="polite">
            {hover ? (
              <>
                <b>{hover.name}</b> ({champion(hover.champion_id).name}) · {mmss(hover.t)} · {LABEL[hover.kind]} ·{" "}
                {dt(hover.date)} · {hover.win ? "Sieg" : "Niederlage"}
                <br />
                Beteiligt: {hover.by.length
                  ? hover.by.map((b) => `${position(b.position)} ${champion(b.champion_id).name}${b.killer ? " (Kill)" : ""}`).join(", ")
                  : "kein Champion"}
              </>
            ) : <>{shown.length} Tode im Zeitraum Minute {from}–{Math.min(to, lastMinute)}. Punkt überfahren für Details.</>}
          </div>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th className="left">Spieler</th><th>Tode</th><th>Gank</th><th>Roam</th><th>Gank + Roam</th>
                <th>Lane / 1v1</th><th className="left">Häufigste Täter</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ p, total, count, top }) => {
                const jungler = p.position === "JUNGLE";
                return (
                  <tr key={p.puuid} className={who === p.puuid ? "selected" : ""} style={{ cursor: "pointer" }}
                    onClick={() => setWho(who === p.puuid ? null : p.puuid)}>
                    <td className="left">{p.name} <span className="muted small">{position(p.position)}</span></td>
                    <td>{total} <span className="muted small">Ø {(total / Math.max(1, p.games)).toFixed(1)}</span></td>
                    <td>{jungler ? "–" : count("gank")}</td>
                    <td title={jungler ? "Tode mit Beteiligung eines gegnerischen Laners" : undefined}>{count("roam")}</td>
                    <td>{jungler ? "–" : count("gank_roam")}</td>
                    <td>{jungler ? count("duel") : count("lane")}</td>
                    <td className="left small">{top.map(([pos, n]) => `${position(pos)} ${n}×`).join(", ") || "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
