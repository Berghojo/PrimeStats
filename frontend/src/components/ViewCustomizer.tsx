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

function Editor({ kind, panels, onChange }: { kind: ReportKind; panels: string[]; onChange: (p: string[]) => void }) {
  const all = panelsFor(kind);
  const hidden = all.filter((p) => !panels.includes(p.key));
  const label = (key: string) => all.find((p) => p.key === key)?.label ?? key;
  const move = (i: number, by: number) => {
    const next = [...panels];
    [next[i], next[i + by]] = [next[i + by], next[i]];
    onChange(next);
  };
  return (
    <div className="panel-editor">
      <ol className="panel-list">
        {panels.map((key, i) => (
          <li key={key}>
            <label className="check">
              <input type="checkbox" checked onChange={() => onChange(panels.filter((k) => k !== key))} />
              <span>{label(key)}</span>
            </label>
            <span className="push row" style={{ gap: ".25rem" }}>
              <button type="button" className="btn small" disabled={i === 0} aria-label={`${label(key)} nach oben`}
                onClick={() => move(i, -1)}>↑</button>
              <button type="button" className="btn small" disabled={i === panels.length - 1}
                aria-label={`${label(key)} nach unten`} onClick={() => move(i, 1)}>↓</button>
            </span>
          </li>
        ))}
        {hidden.map((p) => (
          <li key={p.key} className="off">
            <label className="check">
              <input type="checkbox" checked={false} onChange={() => onChange([...panels, p.key])} />
              <span>{p.label}</span>
            </label>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Ansicht wählen, anpassen, teilen und (angemeldet) speichern. */
export function ViewCustomizer({ kind, panels, setPanels, views, loggedIn }: ReturnType<typeof usePanels> & {
  kind: ReportKind;
}) {
  const { pathname, search } = useLocation();
  const save = useSaveView(kind);
  const remove = useDeleteView();
  const [open, setOpen] = useState(false);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [asDefault, setAsDefault] = useState(true);
  const [copied, setCopied] = useState(false);

  const all = defaultPanels(kind);
  const current: SavedView | undefined = views.find((v) => same(cleanPanels(v.panels, kind), panels));
  const value = current ? String(current.id) : same(panels, all) ? "all" : "custom";

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

  return (
    <div className="view-bar">
      <div className="row">
        <label className="field row" style={{ gap: ".5rem", alignItems: "center" }}>
          Ansicht
          <select value={value} onChange={(e) => choose(e.target.value)} aria-label="Ansicht wählen">
            <option value="all">Alle Panels</option>
            {views.map((v) => <option key={v.id} value={v.id}>{v.name}{v.is_default ? " (Standard)" : ""}</option>)}
            {value === "custom" && <option value="custom">Angepasst</option>}
          </select>
        </label>
        <button type="button" className={`btn small${open ? " primary" : ""}`} aria-expanded={open}
          onClick={() => setOpen((o) => !o)}>Anpassen</button>
        <button type="button" className="btn small" onClick={share}>{copied ? "Link kopiert" : "Link teilen"}</button>
        {loggedIn ? (
          <>
            {!current && <button type="button" className="btn small" onClick={() => setNaming((n) => !n)}>Ansicht speichern</button>}
            {current && !current.is_default && (
              <button type="button" className="btn small" onClick={() => save.mutate({ id: current.id, is_default: true })}>
                Als Standard
              </button>
            )}
            {current && (
              <button type="button" className="btn small danger"
                onClick={() => window.confirm(`Ansicht „${current.name}“ löschen?`) && remove.mutate(current.id)}>
                Löschen
              </button>
            )}
          </>
        ) : (
          <span className="muted small"><Link to={`/login?next=${encodeURIComponent(pathname + search)}`}>Anmelden</Link>, um Ansichten zu speichern</span>
        )}
      </div>
      {naming && (
        <form className="row" onSubmit={submit}>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, z.B. Draft-Fokus"
            maxLength={40} required autoFocus aria-label="Name der Ansicht" />
          <label className="check small">
            <input type="checkbox" checked={asDefault} onChange={(e) => setAsDefault(e.target.checked)} />
            <span>{kind === "team" ? "Standard für alle Team-Seiten" : "Standard für alle Scoutings"}</span>
          </label>
          <button className="btn small primary" type="submit" disabled={save.isPending}>Speichern</button>
        </form>
      )}
      {(save.error || remove.error) && <ErrorBox error={save.error || remove.error} />}
      {open && <Editor kind={kind} panels={panels} onChange={setPanels} />}
    </div>
  );
}
