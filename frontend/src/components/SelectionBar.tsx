import { useNavigate } from "react-router-dom";

import { buildQuery } from "../api/client";

interface Props {
  selected: Set<string>;
  onSelect: (mode: "all" | "none" | "filtered") => void;
  focus?: string[];
  team?: number;
  showFiltered?: boolean;
}

export function SelectionBar({ selected, onSelect, focus, team, showFiltered }: Props) {
  const navigate = useNavigate();
  const analyse = () => navigate(`/analysis${buildQuery({ m: [...selected], focus, team })}`);
  return (
    <div className="stickybar">
      {showFiltered && <button type="button" className="btn small" onClick={() => onSelect("filtered")}>Gefilterte</button>}
      <button type="button" className="btn small" onClick={() => onSelect("all")}>Alle</button>
      <button type="button" className="btn small" onClick={() => onSelect("none")}>Keine</button>
      <span className="muted"><b>{selected.size}</b> ausgewählt</span>
      <button type="button" className="btn primary push" disabled={selected.size === 0} onClick={analyse}>
        Zeitverlauf analysieren →
      </button>
    </div>
  );
}

export function toggle(set: Set<string>, id: string): Set<string> {
  const next = new Set(set);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}
