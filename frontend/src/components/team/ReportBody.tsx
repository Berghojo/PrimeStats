import { useSearchParams } from "react-router-dom";

import type { Filters, HistoryRow, Report } from "../../api/types";
import { shortDt, signed } from "../../lib/format";
import { MinuteLineChart, ResultBarChart } from "../charts";
import { Empty } from "../ui";
import { FilterBar } from "./FilterBar";
import { InlineTimeline } from "../TimelineChart";
import { Tabs, useTab } from "../Tabs";
import { GamesTable } from "./GamesTable";
import { ObjectivesCard, OverviewKpis } from "./Overview";
import { PlayersTable } from "./PlayersTable";
import { ChampionTable } from "./ChampionTable";
import { FightCard } from "./Fights";
import { JungleCard } from "./Jungle";
import { type ReportKind, PANELS, defaultPanels } from "./panels";
import { ChampionPools, DraftCards } from "./Pools";
import { InfoTip } from "../InfoTip";

const DEFAULT_FILTERS: Omit<Filters, "exclude"> = { label: "all", side: "all", patch: "", last: 0 };

/** Filter stehen in der URL (teilbar, Zurück-Button funktioniert). */
export function useUrlFilters(): [Filters, (next: Partial<Filters>) => void, () => void] {
  const [params, setParams] = useSearchParams();
  const filters: Filters = {
    label: (params.get("label") ?? "all") as Filters["label"],
    side: (params.get("side") ?? "all") as Filters["side"],
    patch: params.get("patch") ?? "",
    last: Number(params.get("last") ?? 0),
    exclude: params.getAll("x"),
  };
  const keys = Object.keys(DEFAULT_FILTERS) as (keyof typeof DEFAULT_FILTERS)[];
  const set = (next: Partial<Filters>) => {
    const merged = { ...filters, ...next };
    const out = new URLSearchParams(params);  // andere Parameter (z.B. Spielerauswahl) bleiben erhalten
    keys.forEach((k) => {
      out.delete(k);
      if (merged[k] !== DEFAULT_FILTERS[k]) out.set(k, String(merged[k]));
    });
    out.delete("x");
    merged.exclude.forEach((id) => out.append("x", id));
    setParams(out, { replace: true });
  };
  const reset = () => {
    const out = new URLSearchParams(params);
    keys.forEach((k) => out.delete(k));
    out.delete("x");
    setParams(out, { replace: true });
  };
  return [filters, set, reset];
}

interface Props {
  data: { filters: Filters; report: Report; history: HistoryRow[]; patches: string[] };
  refreshing: boolean;
  /** Team-Dashboard (Spiele bearbeitbar, Jungle) oder Scouting (nur lesen, Zeitverlauf eingebettet) */
  kind?: ReportKind;
  /** sichtbare Panels in dieser Reihenfolge (Standard: alle) */
  panels?: string[];
  teamId?: number;
  editable?: boolean;
  hideLabelFilter?: boolean;
  noTimelineHint?: string;
  focus?: string[];
}

export function ReportBody({
  data, refreshing, kind = "team", panels, teamId, editable = false, hideLabelFilter, noTimelineHint, focus,
}: Props) {
  const [filters, setFilters, resetFilters] = useUrlFilters();
  const [tab, setTab] = useTab<"overview" | "games">("overview");
  const { report, history } = data;
  const ov = report.overview;
  const excluded = new Set(filters.exclude);
  const setExcluded = (next: Set<string>) => setFilters({ exclude: [...next] });
  // Spiele der Übersicht: passen zu den Filtern und sind im Spiele-Tab nicht abgewählt
  const statGames = history.filter((g) => g.selected && !excluded.has(g.match_id)).map((g) => g.match_id);
  const shownGames = history.filter((g) => g.selected).length;
  const visible = (panels ?? defaultPanels(kind)).filter((k) => k !== "games");
  const empty = ov.games === 0;

  const render = (key: string) => {
    if (empty && key !== "games") return null;
    switch (key) {
      case "overview":
        return <OverviewKpis ov={ov} />;
      case "gold":
        return (
          <div className="card">
            <h2>
              Ø Golddifferenz im Spielverlauf
              <InfoTip>Eigenes Team minus Gegner, pro Minute gemittelt.</InfoTip>
            </h2>
            {ov.timeline_games ? (
              <MinuteLineChart height={260} yTitle="Gold (Team − Gegner)" series={[
                { label: "Alle Spiele", data: report.gold_curves.all.values, counts: report.gold_curves.all.counts, color: "#e8e6e1" },
                { label: "Siege", data: report.gold_curves.win.values, counts: report.gold_curves.win.counts, color: "#4cb782", dashed: true },
                { label: "Niederlagen", data: report.gold_curves.loss.values, counts: report.gold_curves.loss.counts, color: "#e5535f", dashed: true },
              ]} />
            ) : <p className="muted">{noTimelineHint ?? "Keine Timeline-Daten – bitte synchronisieren."}</p>}
          </div>
        );
      case "objectives":
        return <ObjectivesCard monsters={report.monsters} ov={ov} />;
      case "players":
        return (
          <section className="card">
            <h2>
              Spieler
              <InfoTip>
                Durchschnitt pro Spiel. Lane-Differenzen @15 gegen den direkten Gegner (benötigt Timelines). Spalten sind
                sortierbar.
              </InfoTip>
            </h2>
            <PlayersTable players={report.players} />
          </section>
        );
      case "champions":
        return <ChampionTable rows={report.champion_table} />;
      case "pools":
        return <ChampionPools players={report.players} />;
      case "draft":
        return <DraftCards picks={report.picks} ourBans={report.our_bans} enemyBans={report.enemy_bans} enemyPicks={report.enemy_picks} />;
      case "jungle":
        return kind === "team" && report.jungle ? <JungleCard jungle={report.jungle} /> : null;
      case "kills":
        return report.kills?.length ? <FightCard mode="kills" kills={report.kills} players={report.players} /> : null;
      case "deaths":
        return report.deaths?.length ? <FightCard mode="deaths" deaths={report.deaths} players={report.players} /> : null;
      case "trend":
        return ov.timeline_games > 0 ? (
          <section className="card">
            <h2>
              Formkurve
              <InfoTip>Teamgold-Differenz nach 15 Minuten je Spiel (grün = Sieg, rot = Niederlage).</InfoTip>
            </h2>
            <ResultBarChart points={report.trend.map((t) => ({
              label: shortDt(t.date),
              value: t.gd15,
              positive: t.win,
              tooltip: [`${t.win ? "Sieg" : "Niederlage"} · ${t.kills}–${t.deaths}`, `GD@15: ${signed(t.gd15)}`],
            }))} />
          </section>
        ) : null;
      case "timeline":
        // Zeitverlauf über die (bis zu 20 neuesten) Spiele der Übersicht
        return <InlineTimeline ids={statGames.slice(0, 20)} focus={focus} team={teamId} />;
      default:
        return null;
    }
  };

  // aufeinanderfolgende halbe Panels nebeneinander
  const half = new Set(PANELS.filter((p) => p.half).map((p) => p.key));
  const rows: string[][] = [];
  for (const key of visible) {
    const last = rows[rows.length - 1];
    if (half.has(key) && last && last.length === 1 && half.has(last[0])) last.push(key);
    else rows.push([key]);
  }

  return (
    <>
      <FilterBar filters={data.filters} patches={data.patches} hideLabel={hideLabelFilter}
        onChange={setFilters} onReset={resetFilters} />
      <Tabs value={tab} onChange={setTab} tabs={[
        { value: "overview", label: "Übersicht" },
        { value: "games", label: <>Spiele <span className="tab-count">{excluded.size ? `${statGames.length}/${shownGames}` : shownGames}</span></> },
      ]} />
      {tab === "games" ? (
        <div className={refreshing ? "stack refreshing" : "stack"}>
          <GamesTable teamId={teamId} history={history} editable={editable} focus={focus} showOpponent={teamId !== undefined}
            inlineTimeline excluded={excluded} onExcludedChange={setExcluded} />
        </div>
      ) : (
      <div className={refreshing ? "stack refreshing" : "stack"}>
        {excluded.size > 0 && (
          <div className="flash small">
            {excluded.size} Spiel{excluded.size > 1 ? "e" : ""} im Spiele-Tab abgewählt – die Übersicht zeigt {statGames.length}{" "}
            von {shownGames}.{" "}
            <button type="button" className="btn small" onClick={() => setExcluded(new Set())}>Alle wieder einbeziehen</button>
          </div>
        )}
        {empty && <Empty>Keine Spiele für diese Filter.</Empty>}
        {rows.map((row) =>
          row.length === 2 && !empty
            ? <section className="grid two" key={row.join("+")}>{render(row[0])}{render(row[1])}</section>
            : <div className="panel" key={row[0]}>{render(row[0])}</div>,
        )}
        {!visible.length && <Empty>Alle Panels sind ausgeblendet – über „Ansicht anpassen“ wieder einblenden.</Empty>}
      </div>
      )}
    </>
  );
}
