import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  useDeleteGroup, useGroupCompare, useRecentScouts, useStartScout, useTeams, useUpdateGroup,
} from "../api/hooks";
import type { Group, GroupEntry, GroupEntryOut, GroupTeamStats, PlayerReport } from "../api/types";
import { InfoTip } from "../components/InfoTip";
import { Tabs, useTab } from "../components/Tabs";
import { FilterBar } from "../components/team/FilterBar";
import { PlayersTable } from "../components/team/PlayersTable";
import { useUrlFilters } from "../components/team/ReportBody";
import { Empty, ErrorBox, Loading, Spinner } from "../components/ui";
import { duration, num, pct, signed, splitRiotId, tone } from "../lib/format";
import { useGameData } from "../lib/meta";

/** Feste Farbe je Team (Reihenfolge in der Gruppe) */
export const TEAM_COLORS = ["#00e1c4", "#ff5a6e", "#ffb547", "#7c6cff", "#4ea1ff", "#3ddc84", "#ff7ad9", "#c4d65a",
  "#ff8a4c", "#9aa7ff", "#5ad1e6", "#e0e0e0", "#b983ff", "#f5d76e", "#6ee7b7", "#fb7185"];

const teamColor = (i: number) => TEAM_COLORS[i % TEAM_COLORS.length];
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
        <button className="btn small" type="button" onClick={share}>{copied ? "✓ Link kopiert" : "Link teilen"}</button>
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

function AddTeamForm({ group, onAdd, busy }: { group: Group; onAdd: (e: GroupEntry) => void; busy: boolean }) {
  const teams = useTeams();
  const scouts = useRecentScouts();
  const start = useStartScout();
  const [team, setTeam] = useState("");
  const [scout, setScout] = useState("");
  const [rows, setRows] = useState<string[]>(["", ""]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const has = (kind: string, ref: string) => group.entries.some((e) => e.kind === kind && e.ref === ref);

  const scoutNew = (ev: FormEvent) => {
    ev.preventDefault();
    const filled = rows.map((r) => r.trim()).filter(Boolean);
    const invalid = filled.filter((r) => !splitRiotId(r));
    if (!filled.length || invalid.length) {
      setError(invalid.length ? `Bitte im Format Name#TAG eingeben: ${invalid.join(", ")}` : "Mindestens einen Spieler eingeben.");
      return;
    }
    setError("");
    start.mutate({ riotIds: filled, mode: "any" }, {
      onSuccess: (res) => {
        onAdd({ kind: "scout", ref: res.key, name: name.trim() });
        setRows(["", ""]);
        setName("");
      },
    });
  };

  return (
    <div className="group-add">
      <div className="field-row">
        <label className="field">Angelegtes Team
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="">– auswählen –</option>
            {teams.data?.filter((t) => !has("team", String(t.id))).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <button className="btn" type="button" disabled={!team || busy}
          onClick={() => { onAdd({ kind: "team", ref: team, name: "" }); setTeam(""); }}>Hinzufügen</button>
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
          onClick={() => { onAdd({ kind: "scout", ref: scout, name: "" }); setScout(""); }}>Hinzufügen</button>
      </div>
      <form className="stack" onSubmit={scoutNew}>
        <div className="muted small">
          Neues Team scouten
          <InfoTip>
            Riot-IDs der Spieler eines Gegners eingeben (auch Ersatzspieler). Geladen werden die Turnierspiele jedes Spielers;
            der Name ist frei wählbar, z.B. der Teamname.
          </InfoTip>
        </div>
        <input className="input" value={name} maxLength={40} onChange={(e) => setName(e.target.value)}
          placeholder="Teamname (optional)" aria-label="Teamname" />
        {rows.map((value, i) => (
          <input key={i} className="input" value={value} aria-label={`Spieler ${i + 1}`} placeholder="Name#TAG"
            onChange={(e) => setRows((r) => r.map((x, j) => (j === i ? e.target.value : x)))} />
        ))}
        <div className="row">
          {rows.length < 5 && <button type="button" className="btn small" onClick={() => setRows((r) => [...r, ""])}>+ Spieler</button>}
          <button className="btn primary push" type="submit" disabled={start.isPending || busy}>
            {start.isPending ? "Suche …" : "Scouten & hinzufügen"}
          </button>
        </div>
        {(error || start.error) && <ErrorBox error={error || start.error} />}
      </form>
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
        <AddTeamForm group={group} busy={update.isPending} onAdd={(e) => save([...group.entries, e])} />
      )}
      {update.error && <ErrorBox error={update.error} />}
    </section>
  );
}

// ------------------------------------------------------------------ Teamvergleich
interface Metric {
  label: string;
  get: (t: GroupTeamStats) => number | null | undefined;
  fmt: (v: number | null | undefined) => ReactNode;
  /** 1 = höher ist besser, -1 = niedriger ist besser, 0 = neutral */
  better: 1 | -1 | 0;
  /** Wert ist ein Anteil (0–1) → Balken */
  rate?: boolean;
  signed?: boolean;
  hint?: string;
}

const ov = (t: GroupTeamStats) => t.overview;
const monster = (key: string, field: "share" | "us_avg" | "first_time") => (t: GroupTeamStats) =>
  t.monsters.find((m) => m.key === key)?.[field] ?? null;
const rate = (label: string, get: Metric["get"], hint?: string): Metric => ({ label, get, fmt: (v) => pct(v), better: 1, rate: true, hint });
const signedM = (label: string, get: Metric["get"], hint?: string): Metric =>
  ({ label, get, fmt: (v) => <span className={tone(v)}>{signed(v)}</span>, better: 1, signed: true, hint });

const SECTIONS: { title: string; metrics: Metric[] }[] = [
  { title: "Allgemein", metrics: [
    { label: "Spiele", get: (t) => ov(t)?.games, fmt: (v) => v ?? "–", better: 0 },
    rate("Winrate", (t) => ov(t)?.winrate),
    rate("Winrate Blue", (t) => ov(t)?.blue_winrate),
    rate("Winrate Red", (t) => ov(t)?.red_winrate),
    { label: "Ø Spieldauer", get: (t) => ov(t)?.duration, fmt: duration, better: 0 },
    { label: "Ø Dauer Siege", get: (t) => ov(t)?.duration_win, fmt: duration, better: -1, hint: "Kürzer = Siege schneller zu Ende gespielt" },
  ] },
  { title: "Early Game", metrics: [
    signedM("Gold @10", (t) => ov(t)?.gd10, "Ø Teamgold-Differenz nach 10 Minuten"),
    signedM("Gold @15", (t) => ov(t)?.gd15, "Ø Teamgold-Differenz nach 15 Minuten"),
    rate("First Blood", (t) => ov(t)?.first_blood),
    rate("Erster Turm", (t) => ov(t)?.first_tower),
  ] },
  { title: "Kämpfe & Türme", metrics: [
    { label: "Ø Kills", get: (t) => ov(t)?.kills, fmt: (v) => num(v), better: 1 },
    { label: "Ø Tode", get: (t) => ov(t)?.deaths, fmt: (v) => num(v), better: -1 },
    { label: "Ø Türme", get: (t) => ov(t)?.towers, fmt: (v) => num(v), better: 1 },
    { label: "Ø Türme verloren", get: (t) => ov(t)?.towers_lost, fmt: (v) => num(v), better: -1 },
  ] },
  { title: "Objectives", metrics: [
    rate("Erster Drache", (t) => ov(t)?.first_dragon),
    rate("Erste Grubs", (t) => ov(t)?.first_grubs),
    rate("Erster Herald", (t) => ov(t)?.first_herald),
    rate("Erster Baron", (t) => ov(t)?.first_baron),
    rate("Drachen-Anteil", monster("DRAGON", "share"), "Eigene / alle getöteten Drachen"),
    rate("Grubs-Anteil", monster("HORDE", "share")),
    rate("Herald-Anteil", monster("RIFTHERALD", "share")),
    rate("Baron-Anteil", monster("BARON_NASHOR", "share")),
    { label: "Ø Drachen", get: monster("DRAGON", "us_avg"), fmt: (v) => num(v), better: 1 },
  ] },
];

function TeamCompare({ teams }: { teams: GroupTeamStats[] }) {
  return (
    <section className="card">
      <h2>
        Teamvergleich
        <InfoTip>Nur Turnierspiele. Bester Wert je Zeile ist hervorgehoben, schwächster abgeschwächt. Ø = pro Spiel.</InfoTip>
      </h2>
      <div className="table-wrap">
        <table className="data compare">
          <thead>
            <tr>
              <th className="left">Kennzahl</th>
              {teams.map((t, i) => (
                <th key={`${t.entry.kind}:${t.entry.ref}`} title={t.entry.title}>
                  <span className="legend-dot" style={{ background: teamColor(i), marginLeft: 0 }} />
                  {t.entry.tag || t.entry.title}
                </th>
              ))}
            </tr>
          </thead>
          {SECTIONS.map((sec) => (
            <tbody key={sec.title}>
              <tr className="section-row"><th className="left" colSpan={teams.length + 1}>{sec.title}</th></tr>
              {sec.metrics.map((m) => {
                const values = teams.map((t) => (t.overview && t.overview.games > 0 ? m.get(t) ?? null : null));
                const present = values.filter((v): v is number => v !== null);
                const best = m.better && present.length > 1 ? (m.better > 0 ? Math.max(...present) : Math.min(...present)) : null;
                const worst = m.better && present.length > 2 ? (m.better > 0 ? Math.min(...present) : Math.max(...present)) : null;
                const maxAbs = Math.max(...present.map(Math.abs), 1e-9);
                return (
                  <tr key={m.label}>
                    <td className="left">{m.label}{m.hint && <InfoTip>{m.hint}</InfoTip>}</td>
                    {values.map((v, i) => (
                      <td key={i} className={v !== null && v === best ? "best" : v !== null && v === worst && best !== worst ? "worst" : ""}>
                        {v === null ? <span className="muted">–</span> : m.fmt(v)}
                        {v !== null && !m.signed && m.better > 0 && (
                          <div className="bar cmp-bar">
                            <span style={{ width: `${Math.max(0, Math.min(1, m.rate ? v : v / maxAbs)) * 100}%`, background: teamColor(i) }} />
                          </div>
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          ))}
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
