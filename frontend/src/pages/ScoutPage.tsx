import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useMeta, useRecentScouts, useStartScout } from "../api/hooks";
import type { ScoutMode, ScoutPlayer, ScoutSummary } from "../api/types";
import { ErrorBox, Loading } from "../components/ui";
import { ago, splitRiotId } from "../lib/format";

const MAX_PLAYERS = 5;

/** "+" = alle zusammen, "/" = mindestens einer */
export const scoutTitle = (players: ScoutPlayer[], mode: ScoutMode = "all") =>
  players.map((p) => `${p.game_name}#${p.tag_line}`).join(mode === "any" ? " / " : " + ");

export const MODE_TEXT: Record<ScoutMode, string> = {
  all: "Turnierspiele, in denen alle gesuchten Spieler im selben Team standen",
  any: "Turnierspiele jedes gesuchten Spielers (einzeln gesucht)",
};

export function ScoutCard({ scout }: { scout: ScoutSummary }) {
  const others = scout.roster.filter((r) => !r.searched);
  return (
    <Link className="card team-card" to={`/scout/${scout.key}`}>
      <div className="team-head">
        <div className="team-logo">{scout.players[0]?.game_name.slice(0, 2).toUpperCase()}</div>
        <div>
          <h3>{scout.players.map((p) => p.game_name).join(scout.mode === "any" ? " / " : " + ")}</h3>
          <div className="muted small">{scout.games} Turnierspiele · gesucht {ago(scout.updated_at)}</div>
        </div>
      </div>
      <div className="names muted small">Mitspieler: {others.map((r) => r.game_name).join(" · ") || "–"}</div>
    </Link>
  );
}

/** Eine Suche für alles: ein Spieler oder mehrere (z.B. Stammspieler + Ersatz). */
export function SearchForm() {
  const { data: meta } = useMeta();
  const start = useStartScout();
  const navigate = useNavigate();
  const [rows, setRows] = useState<string[]>([""]);
  const [mode, setMode] = useState<ScoutMode>("any");
  const [error, setError] = useState("");

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    const filled = rows.map((r) => r.trim()).filter(Boolean);
    const invalid = filled.filter((r) => !splitRiotId(r));
    if (!filled.length || invalid.length) {
      setError(invalid.length ? `Bitte im Format Name#TAG eingeben: ${invalid.join(", ")}` : "Mindestens einen Spieler eingeben.");
      return;
    }
    setError("");
    start.mutate({ riotIds: filled, mode }, { onSuccess: (res) => navigate(`/scout/${res.key}`) });
  };

  return (
    <>
      <form className="scout-form" onSubmit={submit} role="search">
        {rows.map((value, i) => (
          <div className="row" key={i}>
            <input className="input" value={value} autoFocus={i === 0} aria-label={`Spieler ${i + 1}`}
              placeholder={i === 0 && meta?.demo ? "Name#TAG – z.B. NLE Polaris#EUW" : "Name#TAG"}
              onChange={(e) => setRows((r) => r.map((x, j) => (j === i ? e.target.value : x)))} />
            {rows.length > 1 && (
              <button type="button" className="btn small" title="Entfernen"
                onClick={() => setRows((r) => r.filter((_, j) => j !== i))}>✕</button>
            )}
          </div>
        ))}
        {rows.filter((r) => r.trim()).length > 1 && (
          <fieldset className="mode-select">
            <legend className="muted small">Welche Spiele laden?</legend>
            <label className="check">
              <input type="radio" name="mode" checked={mode === "any"} onChange={() => setMode("any")} />
              <span><b>Jeder einzeln</b> – die Spiele jedes Spielers (z.B. Stammspieler und Ersatz); im Ergebnis kannst du
                danach die Spieler auswählen</span>
            </label>
            <label className="check">
              <input type="radio" name="mode" checked={mode === "all"} onChange={() => setMode("all")} />
              <span><b>Nur gemeinsam</b> – nur Spiele, in denen alle eingegebenen Spieler im selben Team standen</span>
            </label>
          </fieldset>
        )}
        <div className="row">
          {rows.length < MAX_PLAYERS && (
            <button type="button" className="btn small" onClick={() => setRows((r) => [...r, ""])}>+ weiterer Spieler</button>
          )}
          <button className="btn primary push" type="submit" disabled={start.isPending}>
            {start.isPending ? "Suche …" : "Suchen"}
          </button>
        </div>
      </form>
      {(error || start.error) && <div style={{ marginTop: "1rem" }}><ErrorBox error={error || start.error} /></div>}
      {meta && !meta.configured && (
        <p className="flash error" style={{ marginTop: "1rem" }}>Die Suche braucht einen Riot-API-Key auf dem Server.</p>
      )}
    </>
  );
}

export function RecentSearches() {
  const recent = useRecentScouts();
  if (!recent.data?.length) return null;
  return (
    <section>
      <h2>Zuletzt gesucht</h2>
      <div className="grid three">{recent.data.map((s) => <ScoutCard key={s.key} scout={s} />)}</div>
    </section>
  );
}

/** Alte Spieler-Links (/player/Name/TAG) starten die Suche nach diesem Spieler. */
export function PlayerRedirect() {
  const { name = "", tag = "" } = useParams();
  const start = useStartScout();
  const navigate = useNavigate();
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    start.mutate({ riotIds: [`${name}#${tag}`] }, { onSuccess: (res) => navigate(`/scout/${res.key}`, { replace: true }) });
  }, [name, tag, start, navigate]);
  return start.error ? <ErrorBox error={start.error} /> : <Loading message={`Suche ${name}#${tag} …`} />;
}
