import { useTeams } from "../api/hooks";
import { RecentSearches, SearchForm } from "./ScoutPage";
import { NewTeamButton, TeamCard } from "./TeamsPage";

export function HomePage() {
  const teams = useTeams();
  return (
    <>
      <section className="card hero">
        <h1>Prime League &amp; Custom-Game-Statistiken</h1>
        <p>
          Suche einen oder mehrere Spieler per Riot-ID und werte ihre Turnierspiele aus. Im Ergebnis wählst du bis zu fünf
          Spieler aus, um die Statistik auf deren Spiele einzugrenzen. Scrims wertest du über ein Team aus.
        </p>
        <SearchForm />
      </section>
      <RecentSearches />
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
