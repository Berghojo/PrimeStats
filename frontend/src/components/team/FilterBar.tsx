import type { Filters } from "../../api/types";
import { useGameData } from "../../lib/meta";

interface Props {
  filters: Filters;
  patches: string[];
  onChange: (next: Partial<Filters>) => void;
  onReset: () => void;
  /** Scouting/ohne Scrims: Spieltyp-Filter ergibt keinen Sinn */
  hideLabel?: boolean;
}

export function FilterBar({ filters, patches, onChange, onReset, hideLabel }: Props) {
  const { meta } = useGameData();
  return (
    <div className="card filters">
      {!hideLabel && <label className="field">Spieltyp
        <select value={filters.label} onChange={(e) => onChange({ label: e.target.value as Filters["label"] })}>
          <option value="all">Alle</option>
          {Object.entries(meta?.labels ?? {}).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
        </select>
      </label>}
      <label className="field">Seite
        <select value={filters.side} onChange={(e) => onChange({ side: e.target.value as Filters["side"] })}>
          <option value="all">Beide</option>
          <option value="blue">Blau</option>
          <option value="red">Rot</option>
        </select>
      </label>
      <label className="field">Patch
        <select value={filters.patch} onChange={(e) => onChange({ patch: e.target.value })}>
          <option value="">Alle</option>
          {patches.map((p) => <option key={p}>{p}</option>)}
        </select>
      </label>
      <label className="field">Zeitraum
        <select value={filters.last} onChange={(e) => onChange({ last: Number(e.target.value) })}>
          <option value={0}>Alle Spiele</option>
          {[5, 10, 20].map((n) => <option key={n} value={n}>Letzte {n}</option>)}
        </select>
      </label>
      <button className="btn" type="button" onClick={onReset}>Zurücksetzen</button>
    </div>
  );
}
