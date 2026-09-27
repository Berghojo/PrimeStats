import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useUpdateTeamGame } from "../../api/hooks";
import type { HistoryRow, Label } from "../../api/types";
import { dt, duration, signed, tone } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { ChampIcon } from "../ChampIcon";
import { SelectionBar, toggle } from "../SelectionBar";
import { ResultBadge, SideBadge } from "../ui";

export function GamesTable({ teamId, history, editable }: { teamId: number; history: HistoryRow[]; editable: boolean }) {
  const { meta, label } = useGameData();
  const updateGame = useUpdateTeamGame(teamId);
  const initial = () => new Set(history.filter((r) => r.selected).slice(0, 10).map((r) => r.match_id));
  const [selected, setSelected] = useState<Set<string>>(initial);
  const filterKey = history.map((r) => `${r.match_id}:${r.selected}`).join(",");
  // Auswahl zurücksetzen, sobald sich die Filter (und damit die markierten Spiele) ändern
  useEffect(() => setSelected(initial()), [filterKey]);

  return (
    <section className="card">
      <h2>Spiele</h2>
      <div className="sub">
        Alle gefundenen Teamspiele. Ausgeschlossene Spiele fließen nicht in die Statistik ein; das Label steuert den Spieltyp-Filter.
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th /><th className="left">Datum</th><th className="left">Ergebnis</th><th className="left">Gegner</th>
              <th className="left">Unsere Picks</th><th className="left">Gegnerische Picks</th><th>K–T</th><th>Gold Δ</th>
              <th>GD@15</th><th>Dauer</th><th className="left">Typ</th><th />
            </tr>
          </thead>
          <tbody>
            {history.map((g) => (
              <tr key={g.match_id} className={[g.included ? "" : "dim", selected.has(g.match_id) ? "selected" : ""].join(" ")}>
                <td>
                  <input type="checkbox" checked={selected.has(g.match_id)} aria-label="Für Analyse auswählen"
                    onChange={() => setSelected((s) => toggle(s, g.match_id))} />
                </td>
                <td className="left nowrap"><Link to={`/match/${g.match_id}?team=${teamId}`}>{dt(g.date)}</Link></td>
                <td className="left nowrap"><ResultBadge win={g.win} /> <SideBadge side={g.side} /></td>
                <td className="left">{g.opponent || "–"}</td>
                <td className="left"><span className="champ-row">{g.us.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} size="sm" />)}</span></td>
                <td className="left"><span className="champ-row">{g.them.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} size="sm" />)}</span></td>
                <td>{g.us.kills}–{g.them.kills}</td>
                <td className={tone(g.gold_diff)}>{signed(g.gold_diff)}</td>
                <td className={tone(g.gd15)}>{signed(g.gd15)}</td>
                <td>{duration(g.duration)}</td>
                <td className="left nowrap">
                  {editable ? (
                    <select value={g.label} aria-label="Spieltyp"
                      onChange={(e) => updateGame.mutate({ matchId: g.match_id, label: e.target.value as Label })}>
                      {Object.entries(meta?.labels ?? {}).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
                    </select>
                  ) : label(g.label)}{" "}
                  {g.tournament && <span className="badge official" title="Spiel mit Turniercode">TC</span>}
                </td>
                <td>
                  {editable && (
                    <button type="button" className="btn small"
                      title={g.included ? "Aus der Statistik ausschließen" : "Wieder in die Statistik aufnehmen"}
                      onClick={() => updateGame.mutate({ matchId: g.match_id, included: !g.included })}>
                      {g.included ? "✕" : "＋"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SelectionBar
        selected={selected}
        team={teamId}
        showFiltered
        onSelect={(mode) =>
          setSelected(new Set(mode === "none" ? [] : history.filter((r) => mode === "all" || r.selected).map((r) => r.match_id)))}
      />
    </section>
  );
}
