import { Link, useParams, useSearchParams } from "react-router-dom";

import { useTeamReport } from "../api/hooks";
import type { Filters } from "../api/types";
import { MinuteLineChart, ResultBarChart } from "../components/charts";
import { FilterBar } from "../components/team/FilterBar";
import { GamesTable } from "../components/team/GamesTable";
import { ObjectivesCard, OverviewKpis } from "../components/team/Overview";
import { PlayersTable } from "../components/team/PlayersTable";
import { ChampionPools, DraftCards } from "../components/team/Pools";
import { SyncControl } from "../components/team/SyncControl";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { shortDt, signed } from "../lib/format";
import { useGameData } from "../lib/meta";

const DEFAULT_FILTERS: Filters = { label: "all", side: "all", patch: "", opponent: "", last: 0 };

function readFilters(params: URLSearchParams): Filters {
  return {
    label: (params.get("label") ?? "all") as Filters["label"],
    side: (params.get("side") ?? "all") as Filters["side"],
    patch: params.get("patch") ?? "",
    opponent: params.get("opponent") ?? "",
    last: Number(params.get("last") ?? 0),
  };
}

export function TeamPage() {
  const teamId = Number(useParams().teamId);
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const { data, error, isPending, isFetching } = useTeamReport(teamId, filters);
  const { position } = useGameData();

  if (isPending) return <Loading message="Berechne Statistiken …" />;
  if (error) return <ErrorBox error={error} />;

  const { team, report, history } = data;
  const ov = report.overview;
  const setFilters = (next: Partial<Filters>) => {
    const merged = { ...filters, ...next };
    const out = new URLSearchParams();
    (Object.keys(merged) as (keyof Filters)[]).forEach((k) => {
      if (merged[k] !== DEFAULT_FILTERS[k]) out.set(k, String(merged[k]));
    });
    setParams(out, { replace: true });
  };

  return (
    <>
      <section className="card">
        <div className="row between">
          <div className="team-head">
            <div className="team-logo">{(team.tag || team.name).slice(0, 4)}</div>
            <div>
              <h1>{team.name}</h1>
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
            <SyncControl teamId={teamId} initial={data.job} />
            <Link className="btn" to={`/teams/${teamId}/edit`}>Bearbeiten</Link>
          </div>
        </div>
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
        <>
          <FilterBar filters={data.filters} patches={data.patches} opponents={data.opponents}
            onChange={setFilters} onReset={() => setParams({}, { replace: true })} />
          <div className={isFetching ? "stack refreshing" : "stack"}>
            {ov.games === 0 ? <Empty>Keine Spiele für diese Filter.</Empty> : (
              <>
                <OverviewKpis ov={ov} />
                <section className="grid two">
                  <div className="card">
                    <h2>Ø Golddifferenz im Spielverlauf</h2>
                    <div className="sub">Eigenes Team minus Gegner, pro Minute gemittelt.</div>
                    {ov.timeline_games ? (
                      <MinuteLineChart height={260} yTitle="Gold (eigenes Team − Gegner)" series={[
                        { label: "Alle Spiele", data: report.gold_curves.all.values, counts: report.gold_curves.all.counts, color: "#7c5cff" },
                        { label: "Siege", data: report.gold_curves.win.values, counts: report.gold_curves.win.counts, color: "#2fd48a", dashed: true },
                        { label: "Niederlagen", data: report.gold_curves.loss.values, counts: report.gold_curves.loss.counts, color: "#ff5a6a", dashed: true },
                      ]} />
                    ) : <p className="muted">Keine Timeline-Daten – bitte synchronisieren.</p>}
                  </div>
                  <ObjectivesCard monsters={report.monsters} ov={ov} />
                </section>
                <section className="card">
                  <h2>Spieler</h2>
                  <div className="sub">
                    Durchschnitt pro Spiel. Lane-Differenzen @15 gegen den direkten Gegner (benötigt Timelines). Spalten sind sortierbar.
                  </div>
                  <PlayersTable players={report.players} />
                </section>
                <ChampionPools players={report.players} />
                <DraftCards picks={report.picks} ourBans={report.our_bans} enemyBans={report.enemy_bans} enemyPicks={report.enemy_picks} />
                {ov.timeline_games > 0 && (
                  <section className="card">
                    <h2>Formkurve</h2>
                    <div className="sub">Teamgold-Differenz nach 15 Minuten je Spiel (grün = Sieg, rot = Niederlage).</div>
                    <ResultBarChart points={report.trend.map((t) => ({
                      label: shortDt(t.date),
                      value: t.gd15,
                      positive: t.win,
                      tooltip: [`${t.win ? "Sieg" : "Niederlage"} · ${t.kills}–${t.deaths}`, `GD@15: ${signed(t.gd15)}`],
                    }))} />
                  </section>
                )}
              </>
            )}
            <GamesTable teamId={teamId} history={history} />
          </div>
        </>
      )}
    </>
  );
}
