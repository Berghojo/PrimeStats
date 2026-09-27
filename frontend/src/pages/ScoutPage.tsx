import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useMeta, useRecentScouts, useStartScout } from "../api/hooks";
import type { ScoutSummary } from "../api/types";
import { ErrorBox } from "../components/ui";
import { ago, splitRiotId } from "../lib/format";

export function ScoutCard({ scout }: { scout: ScoutSummary }) {
  return (
    <Link className="card team-card" to={`/scout/${scout.puuid}`}>
      <div className="team-head">
        <div className="team-logo">{scout.game_name.slice(0, 2).toUpperCase()}</div>
        <div>
          <h3>{scout.game_name}<span className="muted">#{scout.tag_line}</span></h3>
          <div className="muted small">{scout.games} Turnierspiele · gescoutet {ago(scout.updated_at)}</div>
        </div>
      </div>
      <div className="names muted small">
        Mitspieler: {scout.roster.filter((r) => r.puuid !== scout.puuid).map((r) => r.game_name).join(" · ")}
      </div>
    </Link>
  );
}

export function ScoutPage() {
  const { data: meta } = useMeta();
  const recent = useRecentScouts();
  const start = useStartScout();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [minMembers, setMinMembers] = useState(4);
  const [error, setError] = useState("");

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    const parts = splitRiotId(value);
    if (!parts) {
      setError("Bitte im Format Name#TAG eingeben.");
      return;
    }
    setError("");
    start.mutate({ riot_id: `${parts[0]}#${parts[1]}`, min_members: minMembers },
      { onSuccess: (res) => navigate(`/scout/${res.puuid}`) });
  };

  return (
    <>
      <section className="card hero">
        <h1>Turnier-Scouting</h1>
        <p>
          Gib einen einzigen Spieler des Gegners ein. PrimeStats leitet aus seinen Turnierspielen (Prime League,
          Turniercode) die Mitspieler ab, durchsucht auch deren Spiele und erstellt daraus einen Scouting-Report: Picks,
          Bans, Champion-Pools, Objectives und Spielverlauf. Genutzt werden nur öffentliche Riot-API-Daten.
        </p>
        <form className="search" onSubmit={submit}>
          <input className="input" value={value} onChange={(e) => setValue(e.target.value)} autoFocus
            placeholder={meta?.demo ? "Name#TAG – z.B. RHW Anker#EUW" : "Spieler des Gegners, Name#TAG"} aria-label="Spieler" />
          <select value={minMembers} onChange={(e) => setMinMembers(Number(e.target.value))} aria-label="Mindestanzahl"
            title="Wie viele Kader-Spieler mindestens gemeinsam gespielt haben müssen">
            {[3, 4, 5].map((n) => <option key={n} value={n}>≥ {n} Spieler</option>)}
          </select>
          <button className="btn primary" type="submit" disabled={start.isPending}>Scouten</button>
        </form>
        {(error || start.error) && <div style={{ marginTop: "1rem" }}><ErrorBox error={error || start.error} /></div>}
        {meta && !meta.configured && (
          <p className="flash error" style={{ marginTop: "1rem" }}>Scouting braucht einen Riot-API-Key auf dem Server.</p>
        )}
      </section>
      {recent.data && recent.data.length > 0 && (
        <section>
          <h2>Zuletzt gescoutet</h2>
          <div className="grid three">{recent.data.map((s) => <ScoutCard key={s.puuid} scout={s} />)}</div>
        </section>
      )}
    </>
  );
}
