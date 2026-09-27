import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { InfoTip } from "../InfoTip";

import { useUpdateTeamGame } from "../../api/hooks";
import type { HistoryRow, Label } from "../../api/types";
import { dt, duration, signed, tone } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { ChampIcon } from "../ChampIcon";
import { SelectionBar } from "../SelectionBar";
import { BanEditor } from "./BanEditor";
import { ResultBadge, SideBadge } from "../ui";

interface Props {
  teamId?: number;
  history: HistoryRow[];
  editable: boolean;
  /** Spieler, die in der Zeitverlaufs-Analyse vorausgewählt werden */
  focus?: string[];
  /** Spalte mit von Hand eingetragenem Gegner (nur eigene Teamansicht) */
  showOpponent?: boolean;
  /** Zeitverlauf wird auf derselben Seite angezeigt (kein Wechsel zur Analyse-Seite) */
  inlineTimeline?: boolean;
  /** abgewählte Spiele (zählen nicht in die Statistik) */
  excluded: Set<string>;
  onExcludedChange: (excluded: Set<string>) => void;
}

function OpponentInput({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  const commit = () => {
    if (draft.trim() !== value) onSave(draft.trim());
  };
  return (
    <input className="input opponent" value={draft} maxLength={40} placeholder="Gegner …" aria-label="Gegner"
      onChange={(e) => setDraft(e.target.value)} onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") setDraft(value);
      }} />
  );
}

export function GamesTable({
  teamId, history, editable, focus, showOpponent = false, inlineTimeline = false, excluded, onExcludedChange,
}: Props) {
  const { meta, label, champion } = useGameData();
  const updateGame = useUpdateTeamGame(teamId ?? 0);
  const [editBans, setEditBans] = useState<string | null>(null);
  // gezeigt werden die Spiele, die zu den Filtern passen; die Häkchen steuern, was davon in die Statistik zählt
  const shown = history.filter((g) => g.selected);
  const hiddenByFilter = history.length - shown.length;
  const toggle = (id: string) => {
    const next = new Set(excluded);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onExcludedChange(next);
  };
  const picks = (players: HistoryRow["us"]["players"]) => (
    <span className="champ-row">
      {players.map((p) => (
        <span key={p.puuid} title={`${p.name} – ${champion(p.champion_id).name} (${p.kills}/${p.deaths}/${p.assists})`}>
          <ChampIcon id={p.champion_id} size="sm" />
        </span>
      ))}
    </span>
  );

  const bans = (g: HistoryRow) => {
    const known = g.us.bans.length > 0 || g.them.bans.length > 0;
    const icons = (ids: number[]) => ids.map((id) => <ChampIcon key={id} id={id} size="sm" ban />);
    return (
      <span className="champ-row" title={g.bans_manual ? "Von Hand nachgetragen" : undefined}>
        {known ? <>{icons(g.us.bans)}<span className="muted ban-sep">|</span>{icons(g.them.bans)}</> : <span className="muted">–</span>}
        {g.bans_manual && <span className="badge" title="Von Hand nachgetragen">manuell</span>}
        {editable && g.bans_missing && (
          <button type="button" className="btn small" onClick={() => setEditBans(editBans === g.match_id ? null : g.match_id)}>
            {g.bans_manual ? "Ändern" : "Nachtragen"}
          </button>
        )}
      </span>
    );
  };
  const columns = 16 + (showOpponent ? 1 : 0) + (editable ? 1 : 0);

  return (
    <section className="card">
      <h2>
        Spiele
        <InfoTip>
          Spiele, die zu den Filtern passen{hiddenByFilter ? ` (${hiddenByFilter} weitere ausgefiltert)` : ""}. Häkchen = zählt
          in die Übersicht; abgewählte Spiele fallen dort aus Kennzahlen, Tabellen, Karten und Zeitverlauf heraus.
          {editable && " „✕“ schließt ein Spiel dauerhaft für alle aus; das Label steuert den Spieltyp-Filter."}
          {editable && " Custom-Lobbys im Blind-Modus speichern keine Bans – die lassen sich in der Bans-Spalte nachtragen."}
        </InfoTip>
      </h2>
      <div className="table-wrap">
        <table className="data games-table">
          <thead>
            <tr>
              <th title="In der Statistik" /><th className="left">Datum</th><th className="left">Ergebnis</th>
              {showOpponent && <th className="left">Gegner</th>}
              <th className="left">Unsere Picks</th><th className="left">Gegnerische Picks</th>
              <th className="left" title="Unsere | gegnerische Bans">Bans</th><th>Kills</th>
              <th>Gold Δ</th><th>GD@15</th><th title="Türme">Türme</th><th title="Drachen">Drachen</th>
              <th title="Barone">Baron</th><th>Dauer</th><th>Patch</th><th className="left">Typ</th>{editable && <th />}
            </tr>
          </thead>
          <tbody>
            {shown.map((g) => {
              const on = !excluded.has(g.match_id);
              return (
                <Fragment key={g.match_id}>
                <tr className={[g.included ? "" : "dim", on ? "" : "off"].join(" ")}>
                  <td>
                    <input type="checkbox" checked={on} aria-label="In der Statistik" onChange={() => toggle(g.match_id)} />
                  </td>
                  <td className="left nowrap"><Link to={`/match/${g.match_id}${teamId ? `?team=${teamId}` : ""}`}>{dt(g.date)}</Link></td>
                  <td className="left nowrap"><ResultBadge win={g.win} /> <SideBadge side={g.side} /></td>
                  {showOpponent && (
                    <td className="left">
                      {editable
                        ? <OpponentInput value={g.opponent} onSave={(opponent) => updateGame.mutate({ matchId: g.match_id, opponent })} />
                        : g.opponent || "–"}
                    </td>
                  )}
                  <td className="left">{picks(g.us.players)}</td>
                  <td className="left">{picks(g.them.players)}</td>
                  <td className="left">{bans(g)}</td>
                  <td>{g.us.kills}–{g.them.kills}</td>
                  <td className={tone(g.gold_diff)}>{signed(g.gold_diff)}</td>
                  <td className={tone(g.gd15)}>{signed(g.gd15)}</td>
                  <td>{g.us.towers}–{g.them.towers}</td>
                  <td>{g.us.dragons}–{g.them.dragons}</td>
                  <td>{g.us.barons}–{g.them.barons}</td>
                  <td>{duration(g.duration)}</td>
                  <td>{g.patch}</td>
                  <td className="left nowrap">
                    {editable ? (
                      <select value={g.label} aria-label="Spieltyp"
                        onChange={(e) => updateGame.mutate({ matchId: g.match_id, label: e.target.value as Label })}>
                        {Object.entries(meta?.labels ?? {}).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
                      </select>
                    ) : label(g.label)}{" "}
                    {g.tournament && <span className="badge official" title="Spiel mit Turniercode">TC</span>}
                  </td>
                  {editable && (
                    <td>
                      <button type="button" className="btn small"
                        title={g.included ? "Für alle dauerhaft aus der Statistik ausschließen" : "Wieder aufnehmen"}
                        onClick={() => updateGame.mutate({ matchId: g.match_id, included: !g.included })}>
                        {g.included ? "✕" : "＋"}
                      </button>
                    </td>
                  )}
                </tr>
                {editBans === g.match_id && (
                  <tr className="ban-edit-row">
                    <td colSpan={columns} className="left">
                      <BanEditor
                        initial={{ us: g.bans_manual ? g.us.bans : [], them: g.bans_manual ? g.them.bans : [] }}
                        busy={updateGame.isPending}
                        onCancel={() => setEditBans(null)}
                        onSave={(b) => updateGame.mutate({ matchId: g.match_id, bans: b }, { onSuccess: () => setEditBans(null) })} />
                      {updateGame.error && <p className="neg small">{updateGame.error.message}</p>}
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            })}
            {!shown.length && <tr><td className="left muted" colSpan={columns}>Keine Spiele für diese Filter.</td></tr>}
          </tbody>
        </table>
      </div>
      <SelectionBar
        games={shown.map((g) => ({ id: g.match_id, win: g.win }))}
        excluded={excluded}
        onChange={onExcludedChange}
        team={teamId}
        focus={focus}
        inline={inlineTimeline}
      />
    </section>
  );
}
