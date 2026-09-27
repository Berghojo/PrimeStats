import { useNavigate } from "react-router-dom";

import { buildQuery } from "../api/client";
import { InfoTip } from "./InfoTip";

interface Props {
  selected: Set<string>;
  onSelect: (mode: "all" | "none" | "filtered") => void;
  focus?: string[];
  team?: number;
  showFiltered?: boolean;
  /** Zeitverlauf wird direkt auf der Seite angezeigt – kein Wechsel zur Analyse-Seite */
  inline?: boolean;
}

export function SelectionBar({ selected, onSelect, focus, team, showFiltered, inline }: Props) {
  const navigate = useNavigate();
  const analyse = () => navigate(`/analysis${buildQuery({ m: [...selected], focus, team })}`);
  return (
    <div className="stickybar">
      {showFiltered && <button type="button" className="btn small" onClick={() => onSelect("filtered")}>Gefilterte</button>}
      <button type="button" className="btn small" onClick={() => onSelect("all")}>Alle</button>
      <button type="button" className="btn small" onClick={() => onSelect("none")}>Keine</button>
      <span className="muted"><b>{selected.size}</b> ausgewählt</span>
      {inline ? (
        <span className="push"><InfoTip>Der Zeitverlauf oben aktualisiert sich mit der Auswahl.</InfoTip></span>
      ) : (
        <button type="button" className="btn primary push" disabled={selected.size === 0} onClick={analyse}>
          Zeitverlauf analysieren →
        </button>
      )}
    </div>
  );
}

export function toggle(set: Set<string>, id: string): Set<string> {
  const next = new Set(set);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}
