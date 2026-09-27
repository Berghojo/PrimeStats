import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import type { RosterPlayer, ScoutMode } from "../api/types";
import { useScoutReport, useScoutStatus, useStartScout } from "../api/hooks";
import { ReportBody, useUrlFilters } from "../components/team/ReportBody";
import { InfoTip } from "../components/InfoTip";
import { ErrorBox, Loading, Spinner } from "../components/ui";
import { usePanels, ViewCustomizer } from "../components/ViewCustomizer";
import { ago } from "../lib/format";
import { useGameData } from "../lib/meta";
import { MODE_TEXT, scoutTitle } from "./ScoutPage";

const MAX_SELECTED = 5;

/** Spielerauswahl im Report (bis zu fünf) – steht in der URL (?p=…&match=…). */
function useSelection(): [string[], ScoutMode | undefined, (p: string[], m?: ScoutMode) => void] {
  const [params, setParams] = useSearchParams();
  const selected = params.getAll("p");
  const match = (params.get("match") ?? undefined) as ScoutMode | undefined;
  const set = (players: string[], m?: ScoutMode) => {
    const out = new URLSearchParams(params);
    out.delete("p");
    out.delete("match");
    players.forEach((p) => out.append("p", p));
    if (m) out.set("match", m);
    setParams(out, { replace: true });
  };
  return [selected, match, set];
}

function PlayerSelect({ roster, selected, match, onChange }: {
  roster: RosterPlayer[];
  selected: string[];
  match: ScoutMode;
  onChange: (players: string[], match?: ScoutMode) => void;
}) {
  const { position } = useGameData();
  const full = selected.length >= MAX_SELECTED;
  const toggle = (puuid: string) =>
    onChange(selected.includes(puuid) ? selected.filter((p) => p !== puuid) : [...selected, puuid], match);
  return (
    <div className="player-select">
      <div className="row between">
        <div className="muted small">
          Spielerauswahl
          {selected.length > 0 && <> · <b>{selected.length}</b> ausgewählt</>}
          <InfoTip>
            Bis zu {MAX_SELECTED} Spieler auswählen, um alle Statistiken auf ihre Spiele einzugrenzen. Bei mehreren:
            „Mindestens einer“ = Spiele, in denen einer davon mitspielte; „Alle zusammen“ = nur Spiele mit allen.
          </InfoTip>
        </div>
        {selected.length > 0 && (
          <button type="button" className="btn small" onClick={() => onChange([])}>Auswahl aufheben</button>
        )}
      </div>
      <div className="chips">
        {roster.map((r) => {
          const on = selected.includes(r.puuid);
          return (
            <button type="button" key={r.puuid} className={`chip${on ? " on" : ""}${r.searched ? " searched" : ""}`}
              disabled={!on && full} aria-pressed={on} title={`${r.game_name}#${r.tag_line}`}
              onClick={() => toggle(r.puuid)}>
              <span className="dot" />
              {r.game_name} <span className="muted small">{position(r.position)} · {r.games}×</span>
            </button>
          );
        })}
      </div>
      {selected.length > 1 && (
        <div className="segmented" role="radiogroup" aria-label="Verknüpfung der ausgewählten Spieler">
          <button type="button" role="radio" aria-checked={match === "any"} className={match === "any" ? "on" : ""}
            onClick={() => onChange(selected, "any")}>
            Mindestens einer <span className="muted small">(Vereinigung)</span>
          </button>
          <button type="button" role="radio" aria-checked={match === "all"} className={match === "all" ? "on" : ""}
            onClick={() => onChange(selected, "all")}>
            Alle zusammen <span className="muted small">(Schnittmenge)</span>
          </button>
        </div>
      )}
    </div>
  );
}

export function ScoutReportPage() {
  const { key = "" } = useParams();
  const [filters] = useUrlFilters();
  const [selected, matchParam, setSelection] = useSelection();
  const qc = useQueryClient();
  const report = useScoutReport(key, filters, selected, matchParam);
  const view = usePanels("scout");
  const status = useScoutStatus(key, true);
  const restart = useStartScout();
  const job = status.data;
  const previous = useRef(job?.status);

  // Nach Abschluss des Scoutings den Report neu laden
  useEffect(() => {
    if (previous.current === "running" && job?.status === "done") {
      qc.invalidateQueries({ queryKey: ["scout", key, "report"] });
      qc.invalidateQueries({ queryKey: ["scouts"] });
    }
    previous.current = job?.status;
  }, [job?.status, key, qc]);

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

  if (report.isPending) return running ? <div className="card">{progress}</div> : <Loading message="Lade Spiele …" />;
  if (report.error) {
    const notYet = report.error instanceof ApiError && report.error.status === 404;
    return (
      <div className="card stack">
        {running ? progress : job?.status === "error" ? <ErrorBox error={job.error} /> : <ErrorBox error={report.error} />}
        {notYet && !running && <p className="muted">Dieses Scouting gibt es noch nicht.</p>}
      </div>
    );
  }

  const data = report.data;
  const refresh = () => restart.mutate({ riotIds: data.players.map((p) => `${p.game_name}#${p.tag_line}`), mode: data.mode });
  const multiple = data.players.length > 1;

  return (
    <>
      <section className="card">
        <div className="row between">
          <div className="team-head">
            <div className="team-logo">{data.players[0].game_name.slice(0, 2).toUpperCase()}</div>
            <div>
              <h1>
                {scoutTitle(data.players, data.mode)}
                <InfoTip>{multiple ? MODE_TEXT[data.mode] : "Alle Turnierspiele des Spielers"}.</InfoTip>
              </h1>
              <div className="muted small">aktualisiert {ago(data.updated_at)}</div>
            </div>
          </div>
          {running ? progress : (
            <button className="btn" type="button" onClick={refresh} disabled={restart.isPending}>⟳ Aktualisieren</button>
          )}
        </div>
        {restart.error && <ErrorBox error={restart.error} />}
        <PlayerSelect roster={data.roster} selected={selected.filter((p) => data.roster.some((r) => r.puuid === p))}
          match={matchParam ?? data.match} onChange={setSelection} />
        <ViewCustomizer kind="scout" {...view} />
      </section>
      <ReportBody data={data} refreshing={report.isFetching} hideLabelFilter focus={data.roster.map((r) => r.puuid)} kind="scout"
        panels={view.panels}
        noTimelineHint="Für diese Spiele sind keine Timeline-Daten verfügbar." />
    </>
  );
}
