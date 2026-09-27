import { Link } from "react-router-dom";

import { useMe, useTeams } from "../api/hooks";
import type { Team } from "../api/types";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { ago } from "../lib/format";

export function TeamCard({ team }: { team: Team }) {
  return (
    <Link className="card team-card" to={`/teams/${team.id}`}>
      <div className="team-head">
        <div className="team-logo">{(team.tag || team.name).slice(0, 4)}</div>
        <div>
          <h3>{team.name} {!team.public && <span className="badge" title="Nur für Ersteller und Kader sichtbar">privat</span>}</h3>
          <div className="muted small">
            {team.members.length} Spieler · {team.last_synced ? `synchronisiert ${ago(team.last_synced)}` : "noch nicht synchronisiert"}
          </div>
        </div>
      </div>
      <div className="names muted small">{team.members.map((m) => m.game_name).join(" · ")}</div>
    </Link>
  );
}

export function NewTeamButton() {
  const { data: me } = useMe();
  const to = me?.user ? "/teams/new" : "/login?next=/teams/new";
  return <Link className="btn primary" to={to}>+ Team anlegen</Link>;
}

export function TeamsPage() {
  const { data, error, isPending } = useTeams();
  return (
    <>
      <section className="row between">
        <div>
          <h1>Teams</h1>
          <div className="muted">
            Aggregierte Statistiken aus gemeinsamen Custom Games (Prime League &amp; Scrims). Du siehst öffentliche Teams und
            Teams, in deren Kader einer deiner verknüpften Riot-Accounts steht.
          </div>
        </div>
        <NewTeamButton />
      </section>
      {isPending ? <Loading /> : error ? <ErrorBox error={error} /> : data.length === 0 ? (
        <Empty>Noch keine Teams angelegt.</Empty>
      ) : (
        <div className="grid three">{data.map((t) => <TeamCard key={t.id} team={t} />)}</div>
      )}
    </>
  );
}
