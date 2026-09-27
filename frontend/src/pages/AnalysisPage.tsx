import { Link, useSearchParams } from "react-router-dom";

import { useAnalysis } from "../api/hooks";
import { ChampIcon } from "../components/ChampIcon";
import { TimelineChart } from "../components/TimelineChart";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { dt } from "../lib/format";
import { InfoTip } from "../components/InfoTip";

export function AnalysisPage() {
  const [params] = useSearchParams();
  const ids = params.getAll("m");
  const focus = params.getAll("focus");
  const team = params.get("team") ? Number(params.get("team")) : undefined;
  const { data, error, isPending } = useAnalysis(ids, focus, team);

  if (ids.length === 0) return <Empty>Keine Spiele ausgewählt.</Empty>;
  if (isPending) return <Loading message="Lade Timelines …" />;
  if (error) return <ErrorBox error={error} />;

  return (
    <>
      <section>
        <h1>
          Zeitverlauf
          <InfoTip>Minutenwerte, gemittelt über {data.matches.length} Spiel{data.matches.length !== 1 && "e"} pro Spieler.</InfoTip>
        </h1>
      </section>
      {data.players.length === 0 ? (
        <Empty>Für die ausgewählten Spiele sind keine Timeline-Daten verfügbar.</Empty>
      ) : (
        <section className="card stack">
          <TimelineChart data={data} />
        </section>
      )}
      <section className="card">
        <h2>Ausgewählte Spiele</h2>
        <div className="list-compact">
          {data.matches.map((m) => (
            <div className="item" key={m.match_id}>
              <span className="nowrap muted">{dt(m.created)}</span>
              <span className="champ-row">{m.blue.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} size="sm" />)}</span>
              <span className="muted">vs</span>
              <span className="champ-row">{m.red.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} size="sm" />)}</span>
              <span className="grow" />
              <Link to={`/match/${m.match_id}${team ? `?team=${team}` : ""}`}>Scoreboard</Link>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
