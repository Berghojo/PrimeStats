import { useState } from "react";
import { Link } from "react-router-dom";

import type { PlayerReport } from "../../api/types";
import { num, pct, playerUrl, signed, tone } from "../../lib/format";
import { useGameData } from "../../lib/meta";

type Col = {
  key: string;
  label: string;
  sort: (p: PlayerReport) => number | string;
  render: (p: PlayerReport) => React.ReactNode;
  className?: (p: PlayerReport) => string;
  left?: boolean;
};

const nullLast = (v: number | null) => (v === null ? -Infinity : v);

export function PlayersTable({ players }: { players: PlayerReport[] }) {
  const { position } = useGameData();
  const [sort, setSort] = useState<{ key: string; desc: boolean } | null>(null);

  const cols: Col[] = [
    { key: "name", label: "Spieler", left: true, sort: (p) => p.name.toLowerCase(),
      render: (p) => (
        <>
          {p.tag ? <Link to={playerUrl(p.name, p.tag)} title="Spieler-Einzelansicht"><b>{p.name}</b></Link> : <b>{p.name}</b>}
          {!p.member && <> <span className="badge">Aushilfe</span></>}
        </>
      ) },
    { key: "pos", label: "Rolle", sort: (p) => position(p.position), render: (p) => position(p.position) },
    { key: "games", label: "Spiele", sort: (p) => p.games, render: (p) => p.games },
    { key: "wr", label: "WR", sort: (p) => p.winrate, render: (p) => pct(p.winrate) },
    { key: "kda_line", label: "K / D / A", sort: (p) => p.kills + p.assists - p.deaths,
      render: (p) => `${num(p.kills)} / ${num(p.deaths)} / ${num(p.assists)}` },
    { key: "kda", label: "KDA", sort: (p) => p.kda, render: (p) => num(p.kda, 2) },
    { key: "kp", label: "KP", sort: (p) => nullLast(p.kp), render: (p) => pct(p.kp) },
    { key: "cspm", label: "CS/min", sort: (p) => p.cspm, render: (p) => num(p.cspm) },
    { key: "gpm", label: "Gold/min", sort: (p) => p.gpm, render: (p) => num(p.gpm, 0) },
    { key: "dpm", label: "Schaden/min", sort: (p) => p.dpm, render: (p) => num(p.dpm, 0) },
    { key: "dmg", label: "Sch.-Anteil", sort: (p) => nullLast(p.damage_share), render: (p) => pct(p.damage_share) },
    { key: "gold", label: "Gold-Anteil", sort: (p) => nullLast(p.gold_share), render: (p) => pct(p.gold_share) },
    { key: "vspm", label: "Vision/min", sort: (p) => p.vspm, render: (p) => num(p.vspm, 2) },
    { key: "cw", label: "Kontrollw.", sort: (p) => p.control_wards, render: (p) => num(p.control_wards) },
    { key: "gd15", label: "GD@15", sort: (p) => nullLast(p.gd15), render: (p) => signed(p.gd15), className: (p) => tone(p.gd15) },
    { key: "csd15", label: "CSD@15", sort: (p) => nullLast(p.csd15), render: (p) => signed(p.csd15, 1), className: (p) => tone(p.csd15) },
    { key: "xpd15", label: "XPD@15", sort: (p) => nullLast(p.xpd15), render: (p) => signed(p.xpd15), className: (p) => tone(p.xpd15) },
  ];

  let rows = players;
  if (sort) {
    const col = cols.find((c) => c.key === sort.key)!;
    rows = [...players].sort((a, b) => {
      const x = col.sort(a), y = col.sort(b);
      const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort.desc ? -cmp : cmp;
    });
  }

  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {cols.map((c) => (
              <th
                key={c.key}
                className={[c.left && "left", "sortable", sort?.key === c.key && (sort.desc ? "sorted-desc" : "sorted-asc")].filter(Boolean).join(" ")}
                onClick={() => setSort((s) => ({ key: c.key, desc: s?.key === c.key ? !s.desc : true }))}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.puuid} className={p.member ? "" : "dim"}>
              {cols.map((c) => (
                <td key={c.key} className={[c.left && "left", c.className?.(p)].filter(Boolean).join(" ")}>{c.render(p)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
