import { useNavigate } from "react-router-dom";

import { buildQuery } from "../api/client";
import { InfoTip } from "./InfoTip";

interface Props {
  /** gezeigte Spiele mit Ergebnis */
  games: { id: string; win: boolean }[];
  excluded: Set<string>;
  onChange: (excluded: Set<string>) => void;
  focus?: string[];
  team?: number;
  /** Zeitverlauf wird direkt auf der Seite angezeigt – kein Wechsel zur Analyse-Seite */
  inline?: boolean;
}

/** Schnellauswahl, welche Spiele in die Statistik zählen */
export function SelectionBar({ games, excluded, onChange, focus, team, inline }: Props) {
  const navigate = useNavigate();
  const included = games.filter((g) => !excluded.has(g.id));
  const only = (keep: (g: { win: boolean }) => boolean) =>
    onChange(new Set(games.filter((g) => !keep(g)).map((g) => g.id)));
  const analyse = () => navigate(`/analysis${buildQuery({ m: included.slice(0, 20).map((g) => g.id), focus, team })}`);
  return (
    <div className="stickybar">
      <span><b>{included.length}</b> von {games.length} in der Statistik</span>
      <button type="button" className="btn small" onClick={() => onChange(new Set())}>Alle</button>
      <button type="button" className="btn small" onClick={() => only(() => false)}>Keine</button>
      <button type="button" className="btn small" onClick={() => only((g) => g.win)}>Nur Siege</button>
      <button type="button" className="btn small" onClick={() => only((g) => !g.win)}>Nur Niederlagen</button>
      <InfoTip>Abgewählte Spiele zählen in der Übersicht nicht mit – in Kennzahlen, Tabellen, Karten und Zeitverlauf.</InfoTip>
      {!inline && team !== undefined && (
        <button type="button" className="btn primary push" disabled={included.length === 0} onClick={analyse}>
          Zeitverlauf analysieren
        </button>
      )}
    </div>
  );
}
