import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useMeta, useRecentScouts, useStartScout } from "../api/hooks";
import type { ScoutMode, ScoutPlayer, ScoutSummary } from "../api/types";
import { ErrorBox } from "../components/ui";
import { ago, splitRiotId } from "../lib/format";

const MAX_PLAYERS = 5;

/** "+" = alle zusammen, "/" = mindestens einer */
export const scoutTitle = (players: ScoutPlayer[], mode: ScoutMode = "all") =>
  players.map((p) => `${p.game_name}#${p.tag_line}`).join(mode === "any" ? " / " : " + ");

export const MODE_TEXT: Record<ScoutMode, string> = {
  all: "Turnierspiele, in denen alle gesuchten Spieler im selben Team standen",
  any: "Turnierspiele, in denen mindestens einer der gesuchten Spieler mitspielte",
};

export function ScoutCard({ scout }: { scout: ScoutSummary }) {
  const others = scout.roster.filter((r) => !r.searched);
  return (
    <Link className="card team-card" to={`/scout/${scout.key}`}>
      <div className="team-head">
        <div className="team-logo">{scout.players[0]?.game_name.slice(0, 2).toUpperCase()}</div>
        <div>
          <h3>{scout.players.map((p) => p.game_name).join(scout.mode === "any" ? " / " : " + ")}</h3>
          <div className="muted small">{scout.games} Turnierspiele · gescoutet {ago(scout.updated_at)}</div>
        </div>
      </div>
      <div className="names muted small">Mitspieler: {others.map((r) => r.game_name).join(" · ") || "–"}</div>
    </Link>
  );
}

export function ScoutPage() {
  const { data: meta } = useMeta();
  const recent = useRecentScouts();
  const start = useStartScout();
  const navigate = useNavigate();
  const [rows, setRows] = useState<string[]>([""]);
  const [mode, setMode] = useState<ScoutMode>("all");
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
      <section className="card hero">
        <h1>Turnier-Scouting</h1>
        <p>
          Gib einen oder mehrere Spieler ein und werte ihre Turnierspiele (Prime League, Turniercode) aus. Bei mehreren
          Spielern wählst du, ob nur Spiele zählen, in denen <b>alle im selben Team</b> standen (z.B. das aktuelle Lineup
          eines Gegners), oder alle Spiele, in denen <b>mindestens einer</b> mitspielte. Genutzt werden nur öffentliche
          Riot-API-Daten.
        </p>
        <form className="scout-form" onSubmit={submit}>
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
              <legend className="muted small">Welche Spiele zählen?</legend>
              <label className="check">
                <input type="radio" name="mode" checked={mode === "all"} onChange={() => setMode("all")} />
                <span><b>Alle im selben Team</b> – nur Spiele, in denen alle gewählten Spieler zusammen spielten</span>
              </label>
              <label className="check">
                <input type="radio" name="mode" checked={mode === "any"} onChange={() => setMode("any")} />
                <span><b>Mindestens einer</b> – alle Spiele, in denen einer der gewählten Spieler mitspielte</span>
              </label>
            </fieldset>
          )}
          <div className="row">
            {rows.length < MAX_PLAYERS && (
              <button type="button" className="btn small" onClick={() => setRows((r) => [...r, ""])}>+ weiterer Spieler</button>
            )}
            <button className="btn primary push" type="submit" disabled={start.isPending}>Scouten</button>
          </div>
        </form>
        {(error || start.error) && <div style={{ marginTop: "1rem" }}><ErrorBox error={error || start.error} /></div>}
        {meta && !meta.configured && (
          <p className="flash error" style={{ marginTop: "1rem" }}>Scouting braucht einen Riot-API-Key auf dem Server.</p>
        )}
      </section>
      {recent.data && recent.data.length > 0 && (
        <section>
          <h2>Zuletzt gescoutet</h2>
          <div className="grid three">{recent.data.map((s) => <ScoutCard key={s.key} scout={s} />)}</div>
        </section>
      )}
    </>
  );
}
