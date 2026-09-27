import { useMemo, useState } from "react";

import { useGameData } from "../../lib/meta";
import { ChampIcon } from "../ChampIcon";

const MAX_BANS = 5;

export interface Bans { us: number[]; them: number[] }

/** Eine Seite: bis zu fünf Champions, per Namenssuche hinzufügen, per Klick entfernen. */
function BanSide({ title, value, taken, onChange }: {
  title: string;
  value: number[];
  taken: Set<number>;
  onChange: (ids: number[]) => void;
}) {
  const { meta } = useGameData();
  const [query, setQuery] = useState("");
  const champions = useMemo(
    () => Object.entries(meta?.champions ?? {})
      .map(([key, c]) => ({ key: Number(key), name: c.name }))
      .sort((a, b) => a.name.localeCompare(b.name, "de")),
    [meta],
  );
  const matches = query.trim()
    ? champions.filter((c) => !taken.has(c.key) && c.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 8)
    : [];
  const add = (key: number) => {
    onChange([...value, key]);
    setQuery("");
  };
  return (
    <div className="ban-side">
      <div className="muted small">{title} <span className="tab-count">{value.length}/{MAX_BANS}</span></div>
      <div className="champ-row">
        {value.map((id) => (
          <button key={id} type="button" className="ban-slot" title="Entfernen" onClick={() => onChange(value.filter((x) => x !== id))}>
            <ChampIcon id={id} />
          </button>
        ))}
        {Array.from({ length: MAX_BANS - value.length }, (_, i) => <span key={i} className="ban-slot empty" />)}
      </div>
      {value.length < MAX_BANS && (
        <div className="ban-search">
          <input className="input" value={query} placeholder="Champion suchen …" aria-label={`${title}: Champion suchen`}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (matches[0]) add(matches[0].key);
              }
            }} />
          {matches.length > 0 && (
            <ul className="ban-results" role="listbox">
              {matches.map((c) => (
                <li key={c.key}>
                  <button type="button" onClick={() => add(c.key)}><ChampIcon id={c.key} size="sm" /> {c.name}</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** Bans eines Spiels nachtragen (Custom-Lobby im Blind-Modus speichert keine). */
export function BanEditor({ initial, busy, onSave, onCancel }: {
  initial: Bans;
  busy: boolean;
  onSave: (bans: Bans) => void;
  onCancel: () => void;
}) {
  const [bans, setBans] = useState<Bans>(initial);
  const taken = new Set([...bans.us, ...bans.them]);
  const changed = JSON.stringify(bans) !== JSON.stringify(initial);
  return (
    <div className="ban-editor">
      <BanSide title="Unsere Bans" value={bans.us} taken={taken} onChange={(us) => setBans((b) => ({ ...b, us }))} />
      <BanSide title="Gegnerische Bans" value={bans.them} taken={taken} onChange={(them) => setBans((b) => ({ ...b, them }))} />
      <div className="row ban-actions">
        <button type="button" className="btn primary small" disabled={busy || !changed} onClick={() => onSave(bans)}>Speichern</button>
        <button type="button" className="btn small" onClick={onCancel}>Abbrechen</button>
        {(initial.us.length > 0 || initial.them.length > 0) && (
          <button type="button" className="btn small danger" disabled={busy} onClick={() => onSave({ us: [], them: [] })}>
            Bans entfernen
          </button>
        )}
      </div>
    </div>
  );
}
