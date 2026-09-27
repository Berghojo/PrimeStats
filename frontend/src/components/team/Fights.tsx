import { useMemo, useState } from "react";

import type { DeathEvent, DeathKind, KillEvent, PlayerReport } from "../../api/types";
import { useGameData } from "../../lib/meta";
import { InfoTip } from "../InfoTip";
import { DEATH_RGB, Heat, KILL_RGB, MapBase, SIZE, Slider } from "./Jungle";
import { MapPanel, OptionList, RailSection } from "./MapPanel";

type Mode = "deaths" | "kills";

const KINDS: { key: DeathKind; label: string }[] = [
  { key: "lane", label: "1v1 (Bot: 2v2)" },
  { key: "gank", label: "Gank" },
  { key: "roam", label: "Roam" },
  { key: "gank_roam", label: "Gank + Roam" },
  { key: "duel", label: "Jungle 1v1" },
  { key: "other", label: "Sonstige" },
];
const ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
const lane = (pos: string) => (pos === "UTILITY" ? "BOTTOM" : pos);

/** Gemeinsame Form für Tode und Kills: wem das Ereignis zugeordnet wird und wer auf der anderen Seite stand */
interface Fight {
  t: number;
  x: number;
  y: number;
  kind: DeathKind;
  /** eigene Spieler, denen das Ereignis zählt (Tod: das Opfer; Kill: alle Beteiligten) */
  owners: string[];
  /** Gegner (Tod: Täter; Kill: das Opfer) */
  others: { position: string }[];
}

const TEXT: Record<Mode, { title: string; info: string; total: string; top: string; unit: string }> = {
  deaths: {
    title: "Deaths",
    total: "Tode",
    top: "Häufigste Täter",
    unit: "Tode",
    info: "Wo und wodurch die eigenen Spieler sterben. Gank = gegnerischer Jungler beteiligt · Roam = Laner einer "
      + "anderen Lane beteiligt · 1v1 = nur die direkten Lane-Gegner (auf der Botlane Bot + Support, also 2v2) · beim "
      + "Jungler: Roam = ein Laner beteiligt, Jungle 1v1 = nur der gegnerische Jungler · Sonstige = ohne Champion (Turm, Minions).",
  },
  kills: {
    title: "Kills",
    total: "Beteiligt",
    top: "Häufigste Opfer",
    unit: "Kills",
    info: "Kills des eigenen Teams, gleich eingeteilt aus eigener Sicht: 1v1 = nur die eigenen Lane-Spieler (auf der "
      + "Botlane Bot + Support, also 2v2) · Gank = eigener Jungler beteiligt · Roam = eigener Laner einer anderen Lane "
      + "beteiligt · gegen den gegnerischen Jungler: Jungle 1v1 = nur unser Jungler, Roam = mit Lanern. Je Spieler "
      + "zählen alle Kills, an denen er beteiligt war (Kill oder Assist).",
  },
};

function toFights(mode: Mode, deaths: DeathEvent[], kills: KillEvent[]): Fight[] {
  return mode === "deaths"
    ? deaths.map((d) => ({ t: d.t, x: d.x, y: d.y, kind: d.kind, owners: [d.puuid], others: d.by }))
    : kills.map((k) => ({ t: k.t, x: k.x, y: k.y, kind: k.kind, owners: k.by.map((b) => b.puuid), others: [k.victim] }));
}

/** Tode bzw. Kills der eigenen Spieler als Heatmap mit Einordnung (1v1/2v2, Gank, Roam) und Tabelle je Spieler. */
export function FightCard({ mode, deaths = [], kills = [], players }: {
  mode: Mode;
  deaths?: DeathEvent[];
  kills?: KillEvent[];
  players: PlayerReport[];
}) {
  const { position } = useGameData();
  const text = TEXT[mode];
  const events = useMemo(() => toFights(mode, deaths, kills), [mode, deaths, kills]);
  const members = useMemo(
    () => players.filter((p) => p.member).sort((a, b) => ORDER.indexOf(a.position) - ORDER.indexOf(b.position)),
    [players],
  );
  const [who, setWho] = useState<string | null>(null);
  const [from, setFrom] = useState(0);
  const [to, setTo] = useState(15);
  const [hidden, setHidden] = useState<Set<DeathKind>>(new Set(["other"]));
  const [radius, setRadius] = useState(32);
  const [intensity, setIntensity] = useState(1);
  const lastMinute = Math.max(15, Math.ceil(Math.max(0, ...events.map((d) => d.t)) / 60));

  const inWindow = events.filter((d) => d.t >= from * 60 && d.t <= to * 60);
  const shown = inWindow.filter((d) => (!who || d.owners.includes(who)) && !hidden.has(d.kind));

  const rows = members.map((p) => {
    const mine = inWindow.filter((d) => d.owners.includes(p.puuid));
    const count = (k: DeathKind) => mine.filter((d) => d.kind === k).length;
    const tally = new Map<string, number>();
    for (const d of mine) {
      if (d.kind === "other") continue;
      for (const o of d.others) {
        // Tode: nur die gankenden/roamenden Gegner; Kills: jedes Opfer
        const relevant = mode === "kills" || (p.position === "JUNGLE"
          ? o.position !== "JUNGLE"
          : o.position === "JUNGLE" || lane(o.position) !== lane(p.position));
        if (relevant && o.position) tally.set(o.position, (tally.get(o.position) ?? 0) + 1);
      }
    }
    const top = [...tally.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
    return { p, total: mine.length, count, top };
  });

  const toggleKind = (k: DeathKind) => setHidden((s) => {
    const next = new Set(s);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    return next;
  });

  const kindCounts = new Map<DeathKind, number>();
  for (const d of inWindow) {
    if (!who || d.owners.includes(who)) kindCounts.set(d.kind, (kindCounts.get(d.kind) ?? 0) + 1);
  }
  const perPlayer = (puuid: string) => inWindow.filter((d) => d.owners.includes(puuid) && !hidden.has(d.kind)).length;

  const rail = (
    <>
      <RailSection title="Spieler">
        <OptionList label="Spieler" selected={who ?? "all"}
          onToggle={(v) => setWho(v === "all" || v === who ? null : v)}
          options={[
            { value: "all", label: "Alle Spieler", count: inWindow.filter((d) => !hidden.has(d.kind)).length },
            ...members.map((p) => ({
              value: p.puuid,
              label: <>{p.name}<span className="muted small">{position(p.position)}</span></>,
              count: perPlayer(p.puuid),
            })),
          ]} />
      </RailSection>
      <RailSection title="Kategorie">
        <OptionList multi label="Kategorie" selected={new Set(KINDS.map((k) => k.key).filter((k) => !hidden.has(k)))}
          onToggle={toggleKind}
          options={KINDS.map((k) => ({ value: k.key, label: k.label, count: kindCounts.get(k.key) ?? 0 }))} />
      </RailSection>
      <RailSection title="Zeitraum">
        <Slider label="Von Minute" value={from} min={0} max={lastMinute} onChange={(v) => {
          setFrom(v);
          if (v > to) setTo(v);
        }} />
        <Slider label="Bis Minute" value={Math.min(to, lastMinute)} min={0} max={lastMinute} onChange={(v) => {
          setTo(v);
          if (v < from) setFrom(v);
        }} />
      </RailSection>
      <RailSection title="Darstellung">
        <Slider label="Punktgröße" value={radius} min={12} max={64} onChange={setRadius} format={(v) => `${v} px`} />
        <Slider label="Intensität" value={intensity} min={0.25} max={2} step={0.05} onChange={setIntensity}
          format={(v) => `${Math.round(v * 100)} %`} />
      </RailSection>
    </>
  );

  const table = (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th className="left">Spieler</th><th>{text.total}</th><th>1v1 / 2v2</th><th>Gank</th><th>Roam</th>
            <th>Gank + Roam</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ p, total, count, top }) => {
            const jungler = p.position === "JUNGLE";
            return (
              <tr key={p.puuid} className={who === p.puuid ? "selected" : ""} style={{ cursor: "pointer" }}
                onClick={() => setWho(who === p.puuid ? null : p.puuid)}>
                <td className="left">
                  {p.name} <span className="muted small">{position(p.position)}</span>
                  <div className="cell-sub">{text.top}: {top.map(([pos, n]) => `${position(pos)} ${n}×`).join(", ") || "–"}</div>
                </td>
                <td>{total} <span className="muted small">Ø {(total / Math.max(1, p.games)).toFixed(1)}</span></td>
                <td title={jungler ? "Jungle 1v1" : undefined}>{jungler ? count("duel") : count("lane")}</td>
                {/* ein toter Jungler wird nicht „gegankt“ – dort zählt nur Roam (Laner beteiligt) */}
                <td>{jungler && mode === "deaths" ? "–" : count("gank")}</td>
                <td>{count("roam")}</td>
                <td>{jungler && mode === "deaths" ? "–" : count("gank_roam")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <section className="card stack">
      <div className="panel-head">
        <h2>{text.title}<InfoTip>{text.info}</InfoTip></h2>
        <span className="muted small">Minute {from}–{Math.min(to, lastMinute)} · {shown.length} {text.unit}</span>
      </div>
      <MapPanel
        rail={rail}
        map={(
          <div className="map">
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="map-layer"><MapBase /></svg>
            <Heat points={shown} rgb={mode === "deaths" ? DEATH_RGB : KILL_RGB} radius={radius} intensity={intensity} />
          </div>
        )}
        caption={who ? `${members.find((p) => p.puuid === who)?.name}: ${shown.length} ${text.unit}` : undefined}
        side={table}
      />
    </section>
  );
}
