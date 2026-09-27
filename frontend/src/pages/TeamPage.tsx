import { Link, useParams } from "react-router-dom";

import { useTeamReport } from "../api/hooks";
import { ReportBody, useUrlFilters } from "../components/team/ReportBody";
import { SyncControl } from "../components/team/SyncControl";
import { AddToGroup } from "../components/AddToGroup";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { useGameData } from "../lib/meta";
import { InfoTip } from "../components/InfoTip";
import { usePanels, ViewCustomizer } from "../components/ViewCustomizer";

export function TeamPage() {
  const teamId = Number(useParams().teamId);
  const [filters] = useUrlFilters();
  const { data, error, isPending, isFetching } = useTeamReport(teamId, filters);
  const { position } = useGameData();
  const view = usePanels("team");

  if (isPending) return <Loading message="Berechne Statistiken …" />;
  if (error) return <ErrorBox error={error} />;

  const { team, history } = data;
  return (
    <>
      <section className="card">
        <div className="row between">
          <div className="team-head">
            <div className="team-logo">{(team.tag || team.name).slice(0, 4)}</div>
            <div>
              <h1>{team.name} <span className="badge">{team.public ? "öffentlich" : "privat"}</span></h1>
              <div className="row small">
                {team.members.map((m) => (
                  <span className="badge" key={m.puuid} title={m.riot_id}>
                    {m.role && `${position(m.role)} · `}{m.game_name}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="row">
            <AddToGroup kind="team" refId={String(teamId)} />
            {team.can_edit && (
              <>
                <SyncControl teamId={teamId} initial={data.job} />
                <Link className="btn" to={`/teams/${teamId}/edit`}>Bearbeiten</Link>
              </>
            )}
          </div>
        </div>
        {!team.can_see_scrims && (
          <div className="small" style={{ marginTop: ".5rem" }}>
            <span className="badge">Nur Turnierspiele</span>
            <InfoTip>
              Scrims sind ausschließlich für Spieler im Kader sichtbar –{" "}
              {team.can_edit ? <>verknüpfe dazu einen Riot-Account aus dem Kader unter <Link to="/account">Konto</Link>.</>
                : "dazu muss dein verknüpfter Riot-Account im Kader stehen."}
            </InfoTip>
          </div>
        )}
        {history.length > 0 && <ViewCustomizer kind="team" {...view} />}
      </section>

      {history.length === 0 ? (
        <Empty>
          <h2>Noch keine Spiele</h2>
          <p>
            Starte die Synchronisation: PrimeStats übernimmt alle Spiele, in denen mindestens {team.min_members} Mitglieder
            im selben Team standen – Prime-League-Spiele (Turniercode) über die Riot-API und Scrims, die jemand aus dem Team
            per <Link to="/uploader">Uploader</Link> hochgeladen hat.
          </p>
        </Empty>
      ) : (
        <ReportBody data={data} refreshing={isFetching} teamId={teamId} editable={team.can_edit}
          hideLabelFilter={!team.can_see_scrims} panels={view.panels} />
      )}
    </>
  );
}
