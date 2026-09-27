import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  useDeleteGroup, useMe, useGroupCompare, useRecentScouts, useStartScout, useTeams, useUpdateGroup,
} from "../api/hooks";
import type { Group, GroupEntry, GroupEntryOut, GroupTeamStats, PlayerReport } from "../api/types";
import { PALETTE } from "../components/charts";
import { InfoTip } from "../components/InfoTip";
import { Tabs, useTab } from "../components/Tabs";
import { FilterBar } from "../components/team/FilterBar";
import { PlayersTable } from "../components/team/PlayersTable";
import { useUrlFilters } from "../components/team/ReportBody";
import { Empty, ErrorBox, Loading, Spinner } from "../components/ui";
import { duration, num, pct, signed, tone } from "../lib/format";
import { parseTeams } from "../lib/teamImport";
import { ApiError } from "../api/client";
import { useGameData } from "../lib/meta";


/** feste Farbe je Team (Reihenfolge in der Gruppe) */
const teamColor = (i: number) => PALETTE[i % PALETTE.length];
const entryLink = (e: GroupEntry) => (e.kind === "team" ? `/teams/${e.ref}` : `/scout/${e.ref}`);
const plain = (e: GroupEntry): GroupEntry => ({ kind: e.kind, ref: e.ref, name: e.name });

// ------------------------------------------------------------------ Kopf & Verwaltung
function GroupHeader({ group }: { group: Group }) {
  const update = useUpdateGroup();
  const remove = useDeleteGroup();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const rename = () => {
    const name = window.prompt("Neuer Name der Gruppe", group.name)?.trim();
    if (name && name !== group.name) update.mutate({ key: group.key, name });
  };
  const share = () => {
    void navigator.clipboard?.writeText(window.location.href).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <section className="row between">
      <h1>
        {group.name}
        <InfoTip>
          Vergleich aller Teams der Gruppe – nur Turnierspiele (Prime League mit Turniercode), Scrims zählen nicht. Teams,
          die du nicht sehen darfst, bleiben leer.
        </InfoTip>
      </h1>
      <div className="row">
        <button className="btn small" type="button" onClick={share}>{copied ? "Link kopiert" : "Link teilen"}</button>
        {group.can_edit && (
          <>
            <button className="btn small" type="button" onClick={rename}>Umbenennen</button>
            <button className="btn small danger" type="button" disabled={remove.isPending}
              onClick={() => {
                if (window.confirm(`Gruppe „${group.name}“ löschen?`)) {
                  remove.mutate(group.key, { onSuccess: () => navigate("/groups") });
                }
              }}>
              Löschen
            </button>
          </>
        )}
      </div>
    </section>
  );
}

/** Mehrere Gegner auf einmal: Text einfügen, jedes Team wird gescoutet und hinzugefügt. */
function BulkImport({ busy, onAdd }: { busy: boolean; onAdd: (entries: GroupEntry[]) => void }) {
  const start = useStartScout();
  const [text, setText] = useState("");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [failed, setFailed] = useState<string[]>([]);
  const parsed = useMemo(() => parseTeams(text), [text]);
  const valid = parsed.filter((t) => t.riotIds.length > 0);

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    const added: GroupEntry[] = [];
    const errors: string[] = [];
    const leftover: string[] = [];
    setProgress({ done: 0, total: valid.length });
    for (const [i, team] of valid.entries()) {
      try {
        const res = await start.mutateAsync({ riotIds: team.riotIds, mode: "any" });
        added.push({ kind: "scout", ref: res.key, name: team.name.slice(0, 40) });
      } catch (err) {
        const detail = err instanceof ApiError && err.details.length ? ` (${err.details.join("; ")})` : "";
        errors.push(`${team.name || team.riotIds.join(", ")}: ${err instanceof Error ? err.message : String(err)}${detail}`);
        leftover.push(`${team.name ? `${team.name}: ` : ""}${team.riotIds.join(", ")}`);
      }
      setProgress({ done: i + 1, total: valid.length });
    }
    if (added.length) onAdd(added);
    setFailed(errors);
    setText(leftover.join("\n"));  // fehlgeschlagene Teams zum Korrigieren stehen lassen
    setProgress(null);
  };

  return (
    <form className="stack bulk-import" onSubmit={submit}>
      <div className="muted small">
        Neue Teams scouten – mehrere auf einmal
        <InfoTip>
          Ein Team pro Zeile als „Teamname: Spieler#TAG, Spieler#TAG, …“ oder als Block (erste Zeile Teamname, dann eine
          Riot-ID pro Zeile, Blöcke durch Leerzeile getrennt). Bis zu 5 Spieler je Team, Ersatzspieler dürfen dabei sein.
          Geladen werden die Turnierspiele jedes Spielers.
        </InfoTip>
      </div>
      <textarea className="input" rows={8} value={text} onChange={(e) => setText(e.target.value)} aria-label="Teams einfügen"
        placeholder={"Nordlicht Esports: NLE Polaris#EUW, NLE Kompass#EUW, NLE Waldgeist#EUW\nBerserker: BSK Skalde#EUW, BSK Drakkar#EUW\n…"} />
      {parsed.length > 0 && (
        <ul className="import-preview">
          {parsed.map((t, i) => (
            <li key={i} className={t.riotIds.length ? "" : "bad"}>
              <b>{t.name || `Team ${i + 1}`}</b>
              <span className="muted small"> · {t.riotIds.length} Spieler</span>
              {t.invalid.length > 0 && <span className="neg small"> · keine Riot-ID: {t.invalid.join(", ")}</span>}
            </li>
          ))}
        </ul>
      )}
      <div className="row">
        {progress && <span className="muted small"><Spinner /> Scoute Team {Math.min(progress.done + 1, progress.total)} von {progress.total} …</span>}
        <button className="btn primary push" type="submit" disabled={!valid.length || !!progress || busy}>
          {valid.length > 1 ? `${valid.length} Teams scouten & hinzufügen` : "Scouten & hinzufügen"}
        </button>
      </div>
      {failed.length > 0 && (
        <div className="flash error">
          Nicht hinzugefügt (steht noch im Textfeld):
          <ul>{failed.map((f) => <li key={f}>{f}</li>)}</ul>
        </div>
      )}
    </form>
  );
}

function AddTeamForm({ group, onAdd, busy }: { group: Group; onAdd: (entries: GroupEntry[]) => void; busy: boolean }) {
  const teams = useTeams();
  const scouts = useRecentScouts();
  const [team, setTeam] = useState("");
  const [scout, setScout] = useState("");
  const has = (kind: string, ref: string) => group.entries.some((e) => e.kind === kind && e.ref === ref);

  return (
    <div className="group-add">
      <BulkImport busy={busy} onAdd={onAdd} />
      <div className="stack">
        <div className="field-row">
          <label className="field">Angelegtes Team
            <select value={team} onChange={(e) => setTeam(e.target.value)}>
              <option value="">– auswählen –</option>
              {teams.data?.filter((t) => !has("team", String(t.id))).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <button className="btn" type="button" disabled={!team || busy}
            onClick={() => { onAdd([{ kind: "team", ref: team, name: "" }]); setTeam(""); }}>Hinzufügen</button>
        </div>
        <div className="field-row">
          <label className="field">Bisheriges Scouting
            <select value={scout} onChange={(e) => setScout(e.target.value)}>
              <option value="">– auswählen –</option>
              {scouts.data?.filter((s) => !has("scout", s.key)).map((s) => (
                <option key={s.key} value={s.key}>{s.players.map((p) => p.game_name).join(s.mode === "any" ? " / " : " + ")}</option>
              ))}
            </select>
          </label>
          <button className="btn" type="button" disabled={!scout || busy}
            onClick={() => { onAdd([{ kind: "scout", ref: scout, name: "" }]); setScout(""); }}>Hinzufügen</button>
        </div>
      </div>
    </div>
  );
}

function EntriesCard({ group, stats }: { group: Group; stats: GroupTeamStats[] }) {
  const update = useUpdateGroup();
  const [adding, setAdding] = useState(group.entries.length === 0);
  const save = (entries: GroupEntry[]) => update.mutate({ key: group.key, entries: entries.map(plain) });
  const rename = (e: GroupEntryOut) => {
    const name = window.prompt("Anzeigename (leer = automatisch)", e.name || e.title);
    if (name === null) return;
    save(group.entries.map((x) => (x === e ? { ...x, name: name.trim().slice(0, 40) } : x)));
  };
  const syncing = (e: GroupEntryOut) => stats.find((s) => s.entry.kind === e.kind && s.entry.ref === e.ref)?.syncing;
  return (
    <section className="card stack">
      <div className="row between">
        <h2>Teams <span className="tab-count">{group.entries.length}</span></h2>
        {group.can_edit && (
          <button className="btn small" type="button" onClick={() => setAdding((a) => !a)}>
            {adding ? "Fertig" : "+ Team hinzufügen"}
          </button>
        )}
      </div>
      {group.entries.length === 0 && <p className="muted">Noch keine Teams in dieser Gruppe.</p>}
      <div className="chips">
        {group.entries.map((e, i) => (
          <span key={`${e.kind}:${e.ref}`} className={`chip on group-chip${e.available ? "" : " unavailable"}`}
            style={{ "--chip-color": teamColor(i) } as React.CSSProperties}>
            <span className="dot" />
            {e.available ? <Link to={entryLink(e)}>{e.title}</Link> : <span>{e.title}</span>}
            <span className="muted small">{e.kind === "team" ? "Team" : "Scouting"}</span>
            {syncing(e) && <Spinner />}
            {group.can_edit && (
              <>
                <button type="button" className="chip-btn" title="Anzeigename ändern" onClick={() => rename(e)}>✎</button>
                <button type="button" className="chip-btn" title="Aus der Gruppe entfernen"
                  onClick={() => save(group.entries.filter((x) => x !== e))}>✕</button>
              </>
            )}
          </span>
        ))}
      </div>
      {group.can_edit && adding && (
        <AddTeamForm group={group} busy={update.isPending} onAdd={(added) => save([...group.entries, ...added])} />
      )}
      {update.error && <ErrorBox error={update.error} />}
    </section>
  );
}

// ------------------------------------------------------------------ Teamvergleich
interface Metric {
  key: string;
  /** kurzer Spaltenkopf */
  label: string;
  /** ausführlicher Name (Tooltip) */
  title: string;
  get: (t: GroupTeamStats) => number | null | undefined;
  fmt: (v: number) => ReactNode;
  /** 1 = höher ist besser, -1 = niedriger ist besser, 0 = neutral */
  better: 1 | -1 | 0;
}

const ov = (t: GroupTeamStats) => t.overview;
const monster = (key: string) => (t: GroupTeamStats) => t.monsters.find((m) => m.key === key)?.share ?? null;
const rate = (key: string, label: string, title: string, get: Metric["get"]): Metric =>
  ({ key, label, title, get, fmt: (v) => pct(v), better: 1 });
const avg = (key: string, label: string, title: string, get: Metric["get"], better: 1 | -1): Metric =>
  ({ key, label, title, get, fmt: (v) => num(v), better });
const gold = (key: string, label: string, title: string, get: Metric["get"]): Metric =>
  ({ key, label, title, get, fmt: (v) => <span className={tone(v)}>{signed(v)}</span>, better: 1 });

const METRICS: Metric[] = [
  { key: "games", label: "Spiele", title: "Turnierspiele", get: (t) => ov(t)?.games, fmt: (v) => v, better: 0 },
  rate("wr", "WR", "Winrate", (t) => ov(t)?.winrate),
  rate("wr_blue", "WR Blue", "Winrate auf Blue Side", (t) => ov(t)?.blue_winrate),
  rate("wr_red", "WR Red", "Winrate auf Red Side", (t) => ov(t)?.red_winrate),
  { key: "dur", label: "Dauer", title: "Ø Spieldauer", get: (t) => ov(t)?.duration, fmt: duration, better: 0 },
  gold("gd10", "GD@10", "Ø Teamgold-Differenz nach 10 Minuten", (t) => ov(t)?.gd10),
  gold("gd15", "GD@15", "Ø Teamgold-Differenz nach 15 Minuten", (t) => ov(t)?.gd15),
  avg("kills", "Kills", "Ø Kills pro Spiel", (t) => ov(t)?.kills, 1),
  avg("deaths", "Tode", "Ø Tode pro Spiel", (t) => ov(t)?.deaths, -1),
  avg("towers", "Türme", "Ø zerstörte Türme pro Spiel", (t) => ov(t)?.towers, 1),
  avg("towers_lost", "Türme verl.", "Ø verlorene Türme pro Spiel", (t) => ov(t)?.towers_lost, -1),
  rate("fb", "FB", "First Blood", (t) => ov(t)?.first_blood),
  rate("ft", "1. Turm", "Erster Turm", (t) => ov(t)?.first_tower),
  rate("fd", "1. Drache", "Erster Drache", (t) => ov(t)?.first_dragon),
  rate("fg", "1. Grubs", "Erste Grubs", (t) => ov(t)?.first_grubs),
  rate("fh", "1. Herald", "Erster Herald", (t) => ov(t)?.first_herald),
  rate("fbar", "1. Baron", "Erster Baron", (t) => ov(t)?.first_baron),
  rate("dragons", "Drachen %", "Anteil eigener an allen getöteten Drachen", monster("DRAGON")),
  rate("grubs", "Grubs %", "Anteil eigener an allen getöteten Grubs", monster("HORDE")),
  rate("heralds", "Herald %", "Anteil eigener an allen getöteten Heralds", monster("RIFTHERALD")),
  rate("barons", "Baron %", "Anteil eigener an allen getöteten Barons", monster("BARON_NASHOR")),
];

function TeamCompare({ teams }: { teams: GroupTeamStats[] }) {
  const [sort, setSort] = useState<{ key: string; desc: boolean }>({ key: "wr", desc: true });
  const value = (m: Metric, t: GroupTeamStats) => (t.overview && t.overview.games > 0 ? m.get(t) ?? null : null);
  const indexed = teams.map((t, i) => ({ t, i }));
  const sortMetric = METRICS.find((m) => m.key === sort.key);
  const rows = sort.key === "team"
    ? [...indexed].sort((a, b) => a.t.entry.title.localeCompare(b.t.entry.title) * (sort.desc ? -1 : 1))
    : [...indexed].sort((a, b) => {
      const x = value(sortMetric!, a.t), y = value(sortMetric!, b.t);
      if (x === null || y === null) return x === null ? (y === null ? 0 : 1) : -1;  // leere Werte immer unten
      return sort.desc ? y - x : x - y;
    });
  // bester Wert je Spalte
  const best = new Map(METRICS.filter((m) => m.better).map((m) => {
    const vals = teams.map((t) => value(m, t)).filter((v): v is number => v !== null);
    return [m.key, vals.length > 1 ? (m.better > 0 ? Math.max(...vals) : Math.min(...vals)) : null];
  }));
  const th = (key: string, label: string, title?: string, left = false) => (
    <th key={key} title={title}
      className={[left && "left", "sortable", sort.key === key && (sort.desc ? "sorted-desc" : "sorted-asc")].filter(Boolean).join(" ")}
      onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== "team" }))}>
      {label}
    </th>
  );
  return (
    <section className="card">
      <h2>
        Teamvergleich
        <InfoTip>
          Nur Turnierspiele, Durchschnitt pro Spiel. Spaltenkopf anklicken zum Sortieren (Tooltip = ausführlicher Name);
          der beste Wert je Spalte ist grün.
        </InfoTip>
      </h2>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {th("team", "Team", undefined, true)}
              {METRICS.map((m) => th(m.key, m.label, m.title))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ t, i }) => (
              <tr key={`${t.entry.kind}:${t.entry.ref}`} className={t.entry.available ? "" : "dim"}>
                <td className="left">
                  <span className="legend-dot" style={{ background: teamColor(i), marginLeft: 0 }} />
                  {t.entry.available ? <Link to={entryLink(t.entry)}><b>{t.entry.title}</b></Link> : t.entry.title}
                  {t.syncing && <> <Spinner /></>}
                </td>
                {METRICS.map((m) => {
                  const v = value(m, t);
                  return (
                    <td key={m.key} className={v !== null && v === best.get(m.key) ? "best" : ""}>
                      {v === null ? <span className="muted">–</span> : m.fmt(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Spielervergleich
const ROLE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];

type GroupPlayer = PlayerReport & { teamIndex: number; teamTitle: string };

function PlayerCompare({ teams }: { teams: GroupTeamStats[] }) {
  const { position } = useGameData();
  const [role, setRole] = useState("");
  const [minGames, setMinGames] = useState(3);
  const [rosterOnly, setRosterOnly] = useState(true);
  const all = useMemo<GroupPlayer[]>(() => teams.flatMap((t, i) => t.players.map((p) => ({ ...p, teamIndex: i, teamTitle: t.entry.title }))),
    [teams]);
  const rows = all
    .filter((p) => (!role || p.position === role) && p.games >= minGames && (!rosterOnly || p.member))
    .sort((a, b) => ROLE_ORDER.indexOf(a.position) - ROLE_ORDER.indexOf(b.position) || a.teamIndex - b.teamIndex || b.games - a.games);
  return (
    <section className="card stack">
      <div className="row between">
        <h2>
          Spielervergleich
          <InfoTip>Alle Spieler aller Teams der Gruppe (nur Turnierspiele); Spaltenköpfe zum Sortieren anklicken. Rolle wählen für den direkten Positionsvergleich.</InfoTip>
        </h2>
        <div className="row">
          <div className="segmented" role="radiogroup" aria-label="Rolle">
            {["", ...ROLE_ORDER].map((r) => (
              <button key={r || "all"} type="button" className={role === r ? "on" : ""} aria-checked={role === r} role="radio"
                onClick={() => setRole(r)}>
                {r ? position(r) : "Alle"} <span className="muted">{all.filter((p) => (!r || p.position === r) && p.games >= minGames && (!rosterOnly || p.member)).length}</span>
              </button>
            ))}
          </div>
          <label className="field inline">Min. Spiele
            <select value={minGames} onChange={(e) => setMinGames(Number(e.target.value))}>
              {[1, 3, 5, 10].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={rosterOnly} onChange={(e) => setRosterOnly(e.target.checked)} />
            <span>Ohne Aushilfen</span>
          </label>
        </div>
      </div>
      {rows.length === 0 ? <p className="muted">Keine Spieler für diese Auswahl.</p> : (
        <PlayersTable
          players={rows}
          rowKey={(p) => `${(p as GroupPlayer).teamIndex}:${p.puuid}`}
          team={{
            label: "Team",
            sort: (p) => (p as GroupPlayer).teamTitle.toLowerCase(),
            render: (p) => (
              <span className="nowrap">
                <span className="legend-dot" style={{ background: teamColor((p as GroupPlayer).teamIndex), marginLeft: 0 }} />
                {(p as GroupPlayer).teamTitle}
              </span>
            ),
          }}
        />
      )}
    </section>
  );
}

// ------------------------------------------------------------------ Seite
export function GroupPage() {
  const { data: me } = useMe();
  if (!me) return <Loading />;
  if (!me.user) {
    return (
      <Empty>
        <h2>Gruppen gibt es nur für angemeldete Nutzer</h2>
        <p>Melde dich an, um diese Gruppe zu öffnen.</p>
        <Link className="btn primary" to={`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`}>Anmelden</Link>
      </Empty>
    );
  }
  return <GroupView />;
}

function GroupView() {
  const { key = "" } = useParams();
  const [filters, setFilters, resetFilters] = useUrlFilters();
  // Vergleich immer nur mit Turnierspielen – Spieltyp ist daher kein Filter
  const { exclude: _exclude, label: _label, ...query } = filters;
  const { data, error, isPending, isFetching } = useGroupCompare(key, query);
  const [tab, setTab] = useTab<"teams" | "players">("teams");
  if (isPending) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const { group, teams } = data;
  return (
    <>
      <GroupHeader group={group} />
      <EntriesCard group={group} stats={teams} />
      {teams.length === 0 ? (
        <Empty>Füge Teams hinzu, um sie zu vergleichen.</Empty>
      ) : (
        <div className={`stack${isFetching ? " refreshing" : ""}`}>
          <FilterBar filters={filters} patches={data.patches} onChange={setFilters} onReset={resetFilters} hideLabel />
          <Tabs value={tab} onChange={setTab} tabs={[
            { value: "teams", label: "Teams" },
            { value: "players", label: <>Spieler <span className="tab-count">{teams.reduce((n, t) => n + t.players.filter((p) => p.member).length, 0)}</span></> },
          ]} />
          {tab === "teams" ? <TeamCompare teams={teams} /> : <PlayerCompare teams={teams} />}
        </div>
      )}
    </>
  );
}
