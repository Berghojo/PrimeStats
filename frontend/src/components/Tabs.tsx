import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

/** Aktiver Tab steht in der URL (?tab=…), damit Links und Zurück-Button funktionieren. */
export function useTab<T extends string>(fallback: T): [T, (tab: T) => void] {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as T | null) ?? fallback;
  const set = (next: T) => {
    const out = new URLSearchParams(params);
    if (next === fallback) out.delete("tab");
    else out.set("tab", next);
    setParams(out, { replace: true });
  };
  return [tab, set];
}

export function Tabs<T extends string>({ value, onChange, tabs }: {
  value: T;
  onChange: (tab: T) => void;
  tabs: { value: T; label: ReactNode }[];
}) {
  return (
    <div className="page-tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.value} type="button" role="tab" aria-selected={t.value === value}
          className={t.value === value ? "on" : ""} onClick={() => onChange(t.value)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
