import { useTeams } from "../api/hooks";
import { PlayerSearch } from "../components/Layout";
import { NewTeamButton, TeamCard } from "./TeamsPage";

export function HomePage() {
  const teams = useTeams();
  return (
    <>
      <section className="card hero">
        <h1>Prime League &amp; Custom-Game-Statistiken</h1>
        <p>
          Suche einen Spieler per Riot-ID, um seine Turnier- und Custom Games zu sehen und im Zeitverlauf zu analysieren –
          oder lege ein Team an und werte alle gemeinsamen Custom Games (Prime-League-Spiele und Scrims) aus.
        </p>
        <PlayerSearch big autoFocus />
      </section>
      <section className="card">
        <div className="row between">
          <h2>Teams</h2>
          <NewTeamButton />
        </div>
        {teams.data && teams.data.length > 0 ? (
          <div className="grid three" style={{ marginTop: ".75rem" }}>
            {teams.data.map((t) => <TeamCard key={t.id} team={t} />)}
          </div>
        ) : (
          <p className="muted">
            Noch keine Teams. Lege ein Team mit den Riot-IDs deiner Spieler an – PrimeStats findet dann alle Custom Games,
            in denen genug davon gemeinsam gespielt haben.
          </p>
        )}
      </section>
    </>
  );
}
