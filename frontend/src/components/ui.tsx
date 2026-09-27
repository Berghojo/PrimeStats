import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import type { Side } from "../api/types";

export const ResultBadge = ({ win }: { win: boolean }) => (
  <span className={`badge ${win ? "win" : "loss"}`}>{win ? "Sieg" : "Niederlage"}</span>
);

export const SideBadge = ({ side }: { side: Side }) => (
  <span className={`badge ${side}`}>{side === "blue" ? "Blue" : "Red"}</span>
);

export const TournamentBadge = ({ code }: { code: boolean }) =>
  code ? <span className="badge official" title="Spiel mit Turniercode">Turniercode</span> : <span className="badge">Custom</span>;

export function Kpi({ label, value, hint, meter }: { label: string; value: ReactNode; hint?: ReactNode; meter?: number | null }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {meter !== undefined && meter !== null && (
        <div className="meter"><span style={{ width: `${Math.max(0, Math.min(1, meter)) * 100}%` }} /></div>
      )}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export const Spinner = () => <div className="spinner" role="status" aria-label="Lädt" />;

export function Loading({ message = "Lade Daten …" }: { message?: string }) {
  return (
    <div className="card empty loading">
      <Spinner />
      <div>{message}</div>
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  const details = error instanceof ApiError ? error.details : [];
  return (
    <div className="flash error" role="alert">
      <b>{message}</b>
      {details.length > 0 && <ul>{details.map((d) => <li key={d}>{d}</li>)}</ul>}
    </div>
  );
}

export const Empty = ({ children }: { children: ReactNode }) => <div className="card empty">{children}</div>;
