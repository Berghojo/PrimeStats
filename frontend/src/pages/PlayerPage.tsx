import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useMeta, usePlayerReport, usePlayerSync, useStartPlayerSync } from "../api/hooks";
import type { PlayerFilters, PlayerReport, QueueKey } from "../api/types";
import { ChampIcon } from "../components/ChampIcon";
import { InfoTip } from "../components/InfoTip";
import { FightCard } from "../components/team/Fights";
import { Empty, ErrorBox, Kpi, Loading, ResultBadge, Spinner } from "../components/ui";
import { ago, dt, duration, num, pct, signed, tone } from "../lib/format";
import { useGameData } from "../lib/meta";

const QUEUES: { key: QueueKey; label: string }[] = [
  { key: "solo", label: "Solo/Duo" },
  { key: "flex", label: "Flex" },
  { key: "tourney", label: "Turnier" },
  { key: "scrim", label: "Scrims" },
];
const QUEUE_LABEL = Object.fromEntries(QUEUES.map((q) => [q.key, q.label])) as Record<QueueKey, string>;

/** Filter der Spieleransicht stehen in der URL (teilbar) */
function usePlayerFilters(): [Partial<PlayerFilters>, (next: Partial<PlayerFilters>) => void] {
  const [params, setParams] = useSearchParams();
  const filters: Partial<PlayerFilters> = {
    queue: params.getAll("queue") as QueueKey[],
    patch: params.get("patch") ?? "",
    last: Number(params.get("last") ?? 0),
    champion: Number(params.get("champion") ?? 0),
    role: params.get("role") ?? "",
  };
  const set = (next: Partial<PlayerFilters>) => {
    const merged = { ...filters, ...next };
    const out = new URLSearchParams();
    (merged.queue ?? []).forEach((q) => out.append("queue", q));
    if (merged.patch) out.set("patch", merged.patch);
    if (merged.last) out.set("last", String(merged.last));
    if (merged.champion) out.set("champion", String(merged.champion));
    if (merged.role) out.set("role", merged.role);
    setParams(out, { replace: true });
  };
  return [filters, set];
}

export function PlayerPage() {
  const { name = "", tag = "" } = useParams();
  const { data: meta } = useMeta();
  const { champion, position } = useGameData();
  const [filters, setFilters] = usePlayerFilters();
  const qc = useQueryClient();
  const report = usePlayerReport(name, tag, filters);
  const sync = usePlayerSync(name, tag, true);
  const start = useStartPlayerSync(name, tag);
  const job = sync.data;
  const running = job?.status === "running";
  const previous = useRef(job?.status);
  const autoStarted = useRef(false);

  // nach dem Laden neu auswerten
  useEffect(() => {
    if (previous.current === "running" && job?.status === "done") {
      qc.invalidateQueries({ queryKey: ["player", name, tag, "report"] });
    }
    previous.current = job?.status;
  }, [job?.status, name, tag, qc]);

  // beim ersten Besuch automatisch laden
  const data = report.data;
  useEffect(() => {
    if (autoStarted.current || !data || !meta?.configured || data.last_fetch || running || sync.isPending) return;
    autoStarted.current = true;
    start.mutate();
  }, [data, meta?.configured, running, sync.isPending, start]);

  if (report.isPending) return <Loading message="Lade Spieler …" />;
  if (report.error) {
    return report.error instanceof ApiError && report.error.status === 404
      ? <Empty>{report.error.message}</Empty> : <ErrorBox error={report.error} />;
  }

  const r = data!.report;
  const ov = r.overview;
  const selectedQueues = new Set(filters.queue ?? []);
  const toggleQueue = (q: QueueKey) => {
    const next = new Set(selectedQueues);
    if (next.has(q)) next.delete(q);
    else next.add(q);
    setFilters({ queue: QUEUES.map((x) => x.key).filter((k) => next.has(k)) });
  };
  const self: PlayerReport[] = [{
    puuid: data!.account.puuid, name: data!.account.game_name, tag: "", member: true,
    position: r.roles[0]?.key ?? "", games: ov.games,
  } as PlayerReport];

  return (
    <>
      <section className="card">
        <div className="row between">
          <div className="team-head">
            <div className="team-logo">{data!.account.game_name.slice(0, 2).toUpperCase()}</div>
            <div>
              <h1>
                {data!.account.game_name}#{data!.account.tag_line}
                <InfoTip>
                  Einzelansicht: nur dieser Spieler, aus Solo/Duo, Flex, Turnierspielen und – für Spieler im selben Kader –
                  hochgeladenen Scrims. Geladen werden die jeweils neuesten 20 Spiele pro Queue; Timelines (für Lane-
                  Differenzen und die Karten) für die neuesten 10.
                </InfoTip>
              </h1>
              <div className="muted small">
                {data!.last_fetch ? `geladen ${ago(data!.last_fetch)}` : "noch nicht geladen"}
              </div>
            </div>
          </div>
          {running ? (
            <div className="sync-box" aria-live="polite">
              <Spinner />
              <div>
                <div>{job!.message}</div>
                <div className="progress"><span style={{ width: `${job!.percent}%` }} /></div>
              </div>
            </div>
          ) : (
            <button className="btn" type="button" disabled={start.isPending || !meta?.configured} onClick={() => start.mutate()}>
              ⟳ Aktualisieren
            </button>
          )}
        </div>
        {(start.error || job?.status === "error") && <ErrorBox error={start.error ?? job!.error} />}
      </section>

      <section className="card filters">
        <div className="field">
          Queue
          <div className="segmented multi" role="group" aria-label="Queue">
            {QUEUES.map((q) => {
              const n = data!.queue_counts[q.key] ?? 0;
              const on = selectedQueues.size === 0 || selectedQueues.has(q.key);
              return (
                <button key={q.key} type="button" aria-pressed={selectedQueues.has(q.key)} disabled={!n}
                  className={selectedQueues.has(q.key) ? "on" : on ? "" : "off"} onClick={() => toggleQueue(q.key)}>
                  {q.label} <span className="muted small">{n}</span>
                </button>
              );
            })}
          </div>
        </div>
        <label className="field">Rolle
          <select value={filters.role ?? ""} onChange={(e) => setFilters({ role: e.target.value })}>
            <option value="">Alle</option>
            {data!.roles.map((role) => <option key={role} value={role}>{position(role)}</option>)}
          </select>
        </label>
        <label className="field">Champion
          <select value={filters.champion ?? 0} onChange={(e) => setFilters({ champion: Number(e.target.value) })}>
            <option value={0}>Alle</option>
            {data!.champions.map((c) => <option key={c} value={c}>{champion(c).name}</option>)}
          </select>
        </label>
        <label className="field">Patch
          <select value={filters.patch ?? ""} onChange={(e) => setFilters({ patch: e.target.value })}>
            <option value="">Alle</option>
            {data!.patches.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="field">Zeitraum
          <select value={filters.last ?? 0} onChange={(e) => setFilters({ last: Number(e.target.value) })}>
            <option value={0}>Alle Spiele</option>
            {[5, 10, 20, 40].map((n) => <option key={n} value={n}>Letzte {n}</option>)}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => setFilters({ queue: [], patch: "", last: 0, champion: 0, role: "" })}>
          Zurücksetzen
        </button>
      </section>

      <div className={report.isFetching ? "stack refreshing" : "stack"}>
        {ov.games === 0 ? (
          <Empty>{running ? "Spiele werden geladen …" : "Keine Spiele für diese Filter."}</Empty>
        ) : (
          <>
            <section className="kpis">
              <Kpi label="Spiele" value={ov.games} hint={`${ov.wins} S · ${ov.games - ov.wins} N`} />
              <Kpi label="Winrate" value={pct(ov.winrate)} meter={ov.winrate} />
              <Kpi label="KDA" value={num(ov.kda, 2)} hint={`${num(ov.kills)} / ${num(ov.deaths)} / ${num(ov.assists)}`} />
              <Kpi label="Kill-Beteiligung" value={pct(ov.kp)} meter={ov.kp} />
              <Kpi label="CS / min" value={num(ov.cspm)} />
              <Kpi label="Schaden / min" value={num(ov.dpm, 0)} />
              <Kpi label="Vision / min" value={num(ov.vspm, 2)} />
              <Kpi label="Gold @15" value={<span className={tone(ov.gd15)}>{signed(ov.gd15)}</span>}
                hint={ov.timeline_games ? `vs. Lane-Gegner · ${ov.timeline_games} Timelines` : "keine Timelines"} />
              <Kpi label="CS @15" value={<span className={tone(ov.csd15)}>{signed(ov.csd15, 1)}</span>} />
            </section>

            <section className="grid two">
              <div className="card">
                <h2>Queues</h2>
                <table className="data">
                  <thead><tr><th className="left">Queue</th><th>Spiele</th><th>WR</th><th>KDA</th></tr></thead>
                  <tbody>
                    {r.queues.map((q) => (
                      <tr key={q.key}>
                        <td className="left">{QUEUE_LABEL[q.key as QueueKey] ?? q.key}</td>
                        <td>{q.games}</td><td>{pct(q.winrate)}</td><td>{num(q.kda, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card">
                <h2>Rollen</h2>
                <table className="data">
                  <thead><tr><th className="left">Rolle</th><th>Spiele</th><th>WR</th><th>KDA</th></tr></thead>
                  <tbody>
                    {r.roles.map((role) => (
                      <tr key={role.key}>
                        <td className="left">{position(role.key)}</td>
                        <td>{role.games}</td><td>{pct(role.winrate)}</td><td>{num(role.kda, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="card">
              <h2>Champions</h2>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th className="left">Champion</th><th>Spiele</th><th>WR</th><th>K / D / A</th><th>KDA</th>
                      <th>CS/min</th><th>Schaden/min</th><th className="left">Rollen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.champions.map((c) => (
                      <tr key={c.champion_id} style={{ cursor: "pointer" }}
                        className={filters.champion === c.champion_id ? "selected" : ""}
                        onClick={() => setFilters({ champion: filters.champion === c.champion_id ? 0 : c.champion_id })}>
                        <td className="left"><span className="champ-cell"><ChampIcon id={c.champion_id} size="sm" />{champion(c.champion_id).name}</span></td>
                        <td>{c.games}</td>
                        <td className={c.winrate >= 0.5 ? "pos" : "neg"}>{pct(c.winrate)}</td>
                        <td>{num(c.kills / c.games)} / {num(c.deaths / c.games)} / {num(c.assists / c.games)}</td>
                        <td>{num(c.kda, 2)}</td>
                        <td>{num(c.cspm)}</td>
                        <td>{num(c.dpm, 0)}</td>
                        <td className="left">{c.positions.map(position).join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {r.kills.length > 0 && <FightCard mode="kills" kills={r.kills} players={self} />}
            {r.deaths.length > 0 && <FightCard mode="deaths" deaths={r.deaths} players={self} />}

            <section className="card">
              <h2>Spiele</h2>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th className="left">Datum</th><th className="left">Queue</th><th className="left">Champion</th>
                      <th className="left">Rolle</th><th className="left">Ergebnis</th><th>K / D / A</th><th>CS</th>
                      <th>GD@15</th><th>Dauer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.history.map((g) => (
                      <tr key={g.match_id}>
                        <td className="left nowrap"><Link to={`/match/${g.match_id}`}>{dt(g.date)}</Link></td>
                        <td className="left"><span className={`badge${g.queue === "tourney" ? " official" : ""}`}>{QUEUE_LABEL[g.queue]}</span></td>
                        <td className="left"><span className="champ-cell"><ChampIcon id={g.champion_id} size="sm" />{champion(g.champion_id).name}</span></td>
                        <td className="left">{position(g.position)}</td>
                        <td className="left"><ResultBadge win={g.win} /></td>
                        <td>{g.kills} / {g.deaths} / {g.assists}</td>
                        <td>{g.cs}</td>
                        <td className={tone(g.gd15)}>{signed(g.gd15)}</td>
                        <td>{duration(g.duration)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}
