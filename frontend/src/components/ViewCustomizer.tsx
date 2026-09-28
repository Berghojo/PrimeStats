import { type FormEvent, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { useDeleteView, useMe, useSaveView, useViews } from "../api/hooks";
import type { SavedView } from "../api/types";
import { type ReportKind, cleanPanels, defaultPanels, panelsFor } from "./team/panels";
import { ErrorBox } from "./ui";

const PARAM = "panels";
const same = (a: string[], b: string[]) => a.length === b.length && a.every((k, i) => k === b[i]);

/**
 * Sichtbare Panels: aus dem Link (?panels=…, teilbar) → sonst Standard-Ansicht des Kontos → sonst alle.
 * Änderungen landen im Link, damit die aktuelle Ansicht direkt geteilt werden kann.
 */
export function usePanels(kind: ReportKind) {
  const [params, setParams] = useSearchParams();
  const { data: me } = useMe();
  const views = useViews(!!me?.user, kind);
  const raw = params.get(PARAM);
  const fromUrl = raw !== null ? cleanPanels(raw.split(",").filter(Boolean), kind) : null;
  const saved = views.data?.find((v) => v.is_default);
  const panels = fromUrl ?? (saved ? cleanPanels(saved.panels, kind) : defaultPanels(kind));
  const setPanels = (next: string[] | null) => {
    const out = new URLSearchParams(params);
    if (next === null) out.delete(PARAM);
    else out.set(PARAM, next.join(","));
    setParams(out, { replace: true });
  };
  return { panels, setPanels, views: views.data ?? [], loggedIn: !!me?.user };
}

const Eye = ({ off }: { off?: boolean }) => (
  <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
    <circle cx="12" cy="12" r="3" />
    {off && <path d="M3 3l18 18" />}
  </svg>
);

/** Knopf oben rechts in einem Panel (erscheint beim Überfahren): Panel ausblenden */
export function HidePanelButton({ label, onHide }: { label: string; onHide: () => void }) {
  return (
    <button type="button" className="panel-hide" title={`„${label}“ ausblenden`} aria-label={`${label} ausblenden`}
      onClick={onHide}>
      <Eye off />
    </button>
  );
}

export const panelLabel = (kind: ReportKind, key: string) => panelsFor(kind).find((p) => p.key === key)?.label ?? key;

/**
 * Schmale Leiste rechts neben dem Report: alle Panels mit Sichtbarkeit und Reihenfolge, darunter Ansicht
 * wählen, teilen und (angemeldet) speichern.
 */
export function PanelRail({ kind, panels, setPanels, views, loggedIn }: ReturnType<typeof usePanels> & {
  kind: ReportKind;
}) {
  const { pathname, search } = useLocation();
  const save = useSaveView(kind);
  const remove = useDeleteView();
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [asDefault, setAsDefault] = useState(true);
  const [copied, setCopied] = useState(false);

  const all = defaultPanels(kind);
  const hidden = all.filter((k) => !panels.includes(k));
  const current: SavedView | undefined = views.find((v) => same(cleanPanels(v.panels, kind), panels));
  const value = current ? String(current.id) : same(panels, all) ? "all" : "custom";

  const move = (i: number, by: number) => {
    const next = [...panels];
    [next[i], next[i + by]] = [next[i + by], next[i]];
    setPanels(next);
  };
  const choose = (v: string) => {
    if (v === "all") setPanels(all);
    const view = views.find((x) => String(x.id) === v);
    if (view) setPanels(cleanPanels(view.panels, kind));
  };
  const share = async () => {
    const url = new URL(`${pathname}${search}`, window.location.origin);
    url.searchParams.set(PARAM, panels.join(","));
    try {
      await navigator.clipboard.writeText(url.toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Link zum Kopieren:", url.toString());
    }
  };
  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    save.mutate({ name: name.trim(), panels, is_default: asDefault }, {
      onSuccess: () => {
        setNaming(false);
        setName("");
      },
    });
  };
  const scrollTo = (key: string) =>
    document.getElementById(`panel-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <aside className="panel-rail" aria-label="Panels">
      <div className="rail-title">Panels <span className="muted">{panels.length}/{all.length}</span></div>
      <ol className="rail-list">
        {panels.map((key, i) => (
          <li key={key}>
            <button type="button" className="rail-eye" title="Ausblenden" aria-label={`${panelLabel(kind, key)} ausblenden`}
              onClick={() => setPanels(panels.filter((k) => k !== key))}><Eye /></button>
            <button type="button" className="rail-name" onClick={() => scrollTo(key)} title="Zum Panel springen">
              {panelLabel(kind, key)}
            </button>
            <span className="rail-move">
              <button type="button" disabled={i === 0} aria-label={`${panelLabel(kind, key)} nach oben`}
                onClick={() => move(i, -1)}>↑</button>
              <button type="button" disabled={i === panels.length - 1} aria-label={`${panelLabel(kind, key)} nach unten`}
                onClick={() => move(i, 1)}>↓</button>
            </span>
          </li>
        ))}
        {hidden.map((key) => (
          <li key={key} className="off">
            <button type="button" className="rail-eye" title="Einblenden" aria-label={`${panelLabel(kind, key)} einblenden`}
              onClick={() => setPanels([...panels, key])}><Eye off /></button>
            <button type="button" className="rail-name" onClick={() => setPanels([...panels, key])} title="Einblenden">
              {panelLabel(kind, key)}
            </button>
          </li>
        ))}
      </ol>

      <div className="rail-title">Ansicht</div>
      <select value={value} onChange={(e) => choose(e.target.value)} aria-label="Ansicht wählen">
        <option value="all">Alle Panels</option>
        {views.map((v) => <option key={v.id} value={v.id}>{v.name}{v.is_default ? " (Standard)" : ""}</option>)}
        {value === "custom" && <option value="custom">Angepasst</option>}
      </select>
      <div className="rail-actions">
        <button type="button" className="btn small" onClick={share}>{copied ? "Link kopiert" : "Link teilen"}</button>
        {loggedIn && !current && (
          <button type="button" className="btn small" onClick={() => setNaming((n) => !n)}>Speichern …</button>
        )}
        {loggedIn && current && !current.is_default && (
          <button type="button" className="btn small" onClick={() => save.mutate({ id: current.id, is_default: true })}>
            Als Standard
          </button>
        )}
        {loggedIn && current && (
          <button type="button" className="btn small danger"
            onClick={() => window.confirm(`Ansicht „${current.name}“ löschen?`) && remove.mutate(current.id)}>
            Löschen
          </button>
        )}
      </div>
      {!loggedIn && (
        <span className="muted small">
          <Link to={`/login?next=${encodeURIComponent(pathname + search)}`}>Anmelden</Link>, um Ansichten zu speichern
        </span>
      )}
      {naming && (
        <form className="rail-save" onSubmit={submit}>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name der Ansicht"
            maxLength={40} required autoFocus aria-label="Name der Ansicht" />
          <label className="check small">
            <input type="checkbox" checked={asDefault} onChange={(e) => setAsDefault(e.target.checked)} />
            <span>{kind === "team" ? "Standard für alle Team-Seiten" : "Standard für alle Scoutings"}</span>
          </label>
          <button className="btn small primary" type="submit" disabled={save.isPending}>Speichern</button>
        </form>
      )}
      {(save.error || remove.error) && <ErrorBox error={save.error || remove.error} />}
    </aside>
  );
}
