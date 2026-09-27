import { useState } from "react";

import type { ChampionRow } from "../../api/types";
import { num, pct, tone } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { ChampIcon } from "../ChampIcon";

type Col = {
  key: string;
  label: string;
  title?: string;
  sort: (r: ChampionRow) => number | string;
  render: (r: ChampionRow) => React.ReactNode;
  className?: (r: ChampionRow) => string;
  left?: boolean;
};

const nn = (v: number | null) => (v === null ? -Infinity : v);
const POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

/** Champion-Pick-Tabelle: eigene Picks mit Leistung, dazu Bans beider Seiten und Präsenz. */
export function ChampionTable({ rows }: { rows: ChampionRow[] }) {
  const { champion, position } = useGameData();
  const [sort, setSort] = useState<{ key: string; desc: boolean }>({ key: "picks", desc: true });
  const [role, setRole] = useState("");
  const [withBans, setWithBans] = useState(false);

  const cols: Col[] = [
    { key: "champ", label: "Champion", left: true, sort: (r) => champion(r.champion_id).name,
      render: (r) => <div className="champ-cell"><ChampIcon id={r.champion_id} size="sm" /><b>{champion(r.champion_id).name}</b></div> },
    { key: "pos", label: "Rolle", sort: (r) => position(r.position), render: (r) => (r.position ? position(r.position) : "–") },
    { key: "players", label: "Gespielt von", left: true, sort: (r) => r.players[0]?.name ?? "",
      render: (r) => r.players.length
        ? r.players.map((p) => `${p.name} (${p.games})`).join(", ")
        : <span className="muted">nur gebannt</span> },
    { key: "picks", label: "Picks", sort: (r) => r.picks, render: (r) => r.picks || "–" },
    { key: "wr", label: "WR", sort: (r) => nn(r.winrate), render: (r) => (r.picks ? `${pct(r.winrate)} (${r.wins}–${r.picks - r.wins})` : "–"),
      className: (r) => tone(r.winrate, 0.5) },
    { key: "kda", label: "KDA", sort: (r) => nn(r.kda), render: (r) => num(r.kda, 2) },
    { key: "kdaline", label: "K / D / A", sort: (r) => nn(r.kills),
      render: (r) => (r.picks ? `${num(r.kills)} / ${num(r.deaths)} / ${num(r.assists)}` : "–") },
    { key: "cspm", label: "CS/min", sort: (r) => nn(r.cspm), render: (r) => num(r.cspm) },
    { key: "dpm", label: "Schaden/min", sort: (r) => nn(r.dpm), render: (r) => num(r.dpm, 0) },
    { key: "ban_us", label: "Bans (eigene)", title: "Wie oft das Team diesen Champion gebannt hat",
      sort: (r) => r.bans_by_us, render: (r) => r.bans_by_us || "–" },
    { key: "ban_them", label: "Bans (Gegner)", title: "Wie oft der Gegner diesen Champion gegen das Team gebannt hat",
      sort: (r) => r.bans_against, render: (r) => r.bans_against || "–" },
    { key: "presence", label: "Präsenz", title: "Anteil der Spiele, in denen der Champion gepickt oder gebannt wurde",
      sort: (r) => nn(r.presence), render: (r) => pct(r.presence) },
  ];

  let shown = rows.filter((r) => (withBans || r.picks > 0) && (!role || r.position === role));
  const col = cols.find((c) => c.key === sort.key)!;
  shown = [...shown].sort((a, b) => {
    const x = col.sort(a), y = col.sort(b);
    const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return sort.desc ? -cmp : cmp;
  });

  return (
    <section className="card">
      <div className="row between">
        <div>
          <h2>Champion-Picks</h2>
          <div className="sub">Alle eigenen Picks mit Leistung, dazu Bans beider Seiten. Spalten sind sortierbar.</div>
        </div>
        <div className="row">
          <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Rolle filtern">
            <option value="">Alle Rollen</option>
            {POSITIONS.map((p) => <option key={p} value={p}>{position(p)}</option>)}
          </select>
          <label className="check small">
            <input type="checkbox" checked={withBans} onChange={(e) => setWithBans(e.target.checked)} />
            <span>auch nur gebannte</span>
          </label>
        </div>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.key} title={c.title}
                  className={[c.left && "left", "sortable", sort.key === c.key && (sort.desc ? "sorted-desc" : "sorted-asc")].filter(Boolean).join(" ")}
                  onClick={() => setSort((s) => ({ key: c.key, desc: s.key === c.key ? !s.desc : true }))}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.champion_id} className={r.picks ? "" : "dim"}>
                {cols.map((c) => (
                  <td key={c.key} className={[c.left && "left", c.key === "players" && "wrap", c.className?.(r)].filter(Boolean).join(" ")}>
                    {c.render(r)}
                  </td>
                ))}
              </tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={cols.length} className="muted">Keine Champions für diese Auswahl.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
