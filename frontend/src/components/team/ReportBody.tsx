import { useSearchParams } from "react-router-dom";

import type { Filters, HistoryRow, Report } from "../../api/types";
import { shortDt, signed } from "../../lib/format";
import { MinuteLineChart, ResultBarChart } from "../charts";
import { Empty } from "../ui";
import { FilterBar } from "./FilterBar";
import { GamesTable } from "./GamesTable";
import { ObjectivesCard, OverviewKpis } from "./Overview";
import { PlayersTable } from "./PlayersTable";
import { ChampionTable } from "./ChampionTable";
import { ChampionPools, DraftCards } from "./Pools";

const DEFAULT_FILTERS: Filters = { label: "all", side: "all", patch: "", last: 0 };

/** Filter stehen in der URL (teilbar, Zurück-Button funktioniert). */
export function useUrlFilters(): [Filters, (next: Partial<Filters>) => void, () => void] {
  const [params, setParams] = useSearchParams();
  const filters: Filters = {
    label: (params.get("label") ?? "all") as Filters["label"],
    side: (params.get("side") ?? "all") as Filters["side"],
    patch: params.get("patch") ?? "",
    last: Number(params.get("last") ?? 0),
  };
  const keys = Object.keys(DEFAULT_FILTERS) as (keyof Filters)[];
  const set = (next: Partial<Filters>) => {
    const merged = { ...filters, ...next };
    const out = new URLSearchParams(params);  // andere Parameter (z.B. Spielerauswahl) bleiben erhalten
    keys.forEach((k) => {
      out.delete(k);
      if (merged[k] !== DEFAULT_FILTERS[k]) out.set(k, String(merged[k]));
    });
    setParams(out, { replace: true });
  };
  const reset = () => {
    const out = new URLSearchParams(params);
    keys.forEach((k) => out.delete(k));
    setParams(out, { replace: true });
  };
  return [filters, set, reset];
}

interface Props {
  data: { filters: Filters; report: Report; history: HistoryRow[]; patches: string[] };
  refreshing: boolean;
  /** Team-Dashboard: Spiele bearbeitbar; Scouting: nur lesen */
  teamId?: number;
  editable?: boolean;
  hideLabelFilter?: boolean;
  noTimelineHint?: string;
  focus?: string[];
  /** Zeitverlauf direkt im Report statt auf einer eigenen Seite */
  inlineTimeline?: boolean;
}

export function ReportBody({ data, refreshing, teamId, editable = false, hideLabelFilter, noTimelineHint, focus, inlineTimeline }: Props) {
  const [, setFilters, resetFilters] = useUrlFilters();
  const { report, history } = data;
  const ov = report.overview;
  return (
    <>
      <FilterBar filters={data.filters} patches={data.patches} hideLabel={hideLabelFilter}
        onChange={setFilters} onReset={resetFilters} />
      <div className={refreshing ? "stack refreshing" : "stack"}>
        {ov.games === 0 ? <Empty>Keine Spiele für diese Filter.</Empty> : (
          <>
            <OverviewKpis ov={ov} />
            <section className="grid two">
              <div className="card">
                <h2>Ø Golddifferenz im Spielverlauf</h2>
                <div className="sub">Eigenes Team minus Gegner, pro Minute gemittelt.</div>
                {ov.timeline_games ? (
                  <MinuteLineChart height={260} yTitle="Gold (Team − Gegner)" series={[
                    { label: "Alle Spiele", data: report.gold_curves.all.values, counts: report.gold_curves.all.counts, color: "#00dcc0" },
                    { label: "Siege", data: report.gold_curves.win.values, counts: report.gold_curves.win.counts, color: "#2fd48a", dashed: true },
                    { label: "Niederlagen", data: report.gold_curves.loss.values, counts: report.gold_curves.loss.counts, color: "#ff4d5e", dashed: true },
                  ]} />
                ) : <p className="muted">{noTimelineHint ?? "Keine Timeline-Daten – bitte synchronisieren."}</p>}
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
            <ChampionTable rows={report.champion_table} />
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
        <GamesTable teamId={teamId} history={history} editable={editable} focus={focus} showOpponent={teamId !== undefined}
          inlineTimeline={inlineTimeline} />
      </div>
    </>
  );
}
