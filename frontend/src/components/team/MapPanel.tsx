import type { ReactNode } from "react";

/**
 * Aufbau der Karten-Panels wie in Analyse-Tools: links Filter, Mitte Karte, rechts Kennzahlen/Tabelle.
 * Auf schmalen Bildschirmen rutschen Details unter die Karte.
 */
export function MapPanel({ rail, map, caption, side }: { rail: ReactNode; map: ReactNode; caption?: ReactNode; side: ReactNode }) {
  return (
    <div className="mp">
      <aside className="mp-rail" aria-label="Filter">{rail}</aside>
      <div className="mp-map">
        {map}
        {caption && <div className="mp-caption muted small" aria-live="polite">{caption}</div>}
      </div>
      <div className="mp-side">{side}</div>
    </div>
  );
}

export function RailSection({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rail-sec">
      <div className="rail-title"><span>{title}</span>{action}</div>
      {children}
    </section>
  );
}

export interface Option<T extends string> {
  value: T;
  label: ReactNode;
  count?: number;
  hint?: string;
}

/** Filterliste mit Zählern: Einfachauswahl (radio) oder Mehrfachauswahl (checkbox). */
export function OptionList<T extends string>({ options, selected, onToggle, multi = false, label }: {
  options: Option<T>[];
  selected: Set<T> | T;
  onToggle: (value: T) => void;
  multi?: boolean;
  label: string;
}) {
  const isOn = (v: T) => (selected instanceof Set ? selected.has(v) : selected === v);
  return (
    <div className="opt-list" role={multi ? "group" : "radiogroup"} aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role={multi ? "checkbox" : "radio"} aria-checked={isOn(o.value)}
          className={`opt${isOn(o.value) ? " on" : ""}${multi ? " multi" : ""}`} title={o.hint}
          onClick={() => onToggle(o.value)}>
          <span className="opt-box" aria-hidden />
          <span className="opt-label">{o.label}</span>
          {o.count !== undefined && <span className="opt-count">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}
