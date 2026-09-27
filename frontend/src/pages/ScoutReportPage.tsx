import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useScoutReport, useScoutStatus, useStartScout } from "../api/hooks";
import { ReportBody, useUrlFilters } from "../components/team/ReportBody";
import { ErrorBox, Loading, Spinner } from "../components/ui";
import { ago } from "../lib/format";
import { useGameData } from "../lib/meta";

export function ScoutReportPage() {
  const { puuid = "" } = useParams();
  const [filters] = useUrlFilters();
  const qc = useQueryClient();
  const report = useScoutReport(puuid, filters);
  const status = useScoutStatus(puuid, true);
  const restart = useStartScout();
  const { position } = useGameData();
  const job = status.data;
  const previous = useRef(job?.status);

  // Nach Abschluss des Scoutings den Report neu laden
  useEffect(() => {
    if (previous.current === "running" && job?.status === "done") {
      qc.invalidateQueries({ queryKey: ["scout", puuid, "report"] });
      qc.invalidateQueries({ queryKey: ["scouts"] });
    }
    previous.current = job?.status;
  }, [job?.status, puuid, qc]);

  const running = job?.status === "running";
  const progress = running && (
    <div className="sync-box" aria-live="polite">
      <Spinner />
      <div>
        <div>{job.message}</div>
        <div className="progress"><span style={{ width: `${job.percent}%` }} /></div>
      </div>
    </div>
  );

  if (report.isPending) return running ? <div className="card">{progress}</div> : <Loading message="Lade Scouting …" />;
  if (report.error) {
    const notYet = report.error instanceof ApiError && report.error.status === 404;
    return (
      <div className="card stack">
        {running ? progress : job?.status === "error" ? <ErrorBox error={job.error} /> : <ErrorBox error={report.error} />}
        {notYet && !running && <p className="muted">Für diesen Spieler gibt es noch kein Scouting.</p>}
      </div>
    );
  }

  const data = report.data;
  const refresh = () =>
    restart.mutate({ riot_id: `${data.player.game_name}#${data.player.tag_line}`, min_members: data.min_members });

  return (
    <>
      <section className="card">
        <div className="row between">
          <div className="team-head">
            <div className="team-logo">{data.player.game_name.slice(0, 2).toUpperCase()}</div>
            <div>
              <h1>{data.player.game_name}<span className="muted">#{data.player.tag_line}</span>{" "}
                <span className="badge accent">Scouting</span></h1>
              <div className="muted small">
                Turnierspiele mit ≥ {data.min_members} Spielern aus diesem Kader · aktualisiert {ago(data.updated_at)}
              </div>
              <div className="row small" style={{ marginTop: ".4rem" }}>
                {data.roster.map((r) => (
                  <span className="badge" key={r.puuid} title={`${r.game_name}#${r.tag_line}`}>
                    {position(r.position)} · {r.game_name} · {r.games}×
                  </span>
                ))}
              </div>
            </div>
          </div>
          {running ? progress : (
            <button className="btn" type="button" onClick={refresh} disabled={restart.isPending}>⟳ Neu scouten</button>
          )}
        </div>
        {restart.error && <ErrorBox error={restart.error} />}
      </section>
      <ReportBody data={data} refreshing={report.isFetching} hideLabelFilter focus={data.roster.map((r) => r.puuid)}
        noTimelineHint="Für diese Spiele sind keine Timeline-Daten verfügbar." />
    </>
  );
}
