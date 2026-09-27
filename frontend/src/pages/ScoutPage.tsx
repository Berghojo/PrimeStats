import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useMeta, useRecentScouts, useStartScout } from "../api/hooks";
import type { ScoutPlayer, ScoutSummary } from "../api/types";
import { ErrorBox } from "../components/ui";
import { ago, splitRiotId } from "../lib/format";

const MAX_PLAYERS = 5;

export const scoutTitle = (players: ScoutPlayer[]) => players.map((p) => `${p.game_name}#${p.tag_line}`).join(" + ");

export function ScoutCard({ scout }: { scout: ScoutSummary }) {
  const others = scout.roster.filter((r) => !r.searched);
  return (
    <Link className="card team-card" to={`/scout/${scout.key}`}>
      <div className="team-head">
        <div className="team-logo">{scout.players[0]?.game_name.slice(0, 2).toUpperCase()}</div>
        <div>
          <h3>{scout.players.map((p) => p.game_name).join(" + ")}</h3>
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
    start.mutate(filled, { onSuccess: (res) => navigate(`/scout/${res.key}`) });
  };

  return (
    <>
      <section className="card hero">
        <h1>Turnier-Scouting</h1>
        <p>
          Gib einen oder mehrere Spieler ein. Ausgewertet werden alle Turnierspiele (Prime League, Turniercode), in denen
          <b> alle eingegebenen Spieler im selben Team</b> standen – so lässt sich z.B. das aktuelle Lineup eines Gegners
          eingrenzen. Genutzt werden nur öffentliche Riot-API-Daten.
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
