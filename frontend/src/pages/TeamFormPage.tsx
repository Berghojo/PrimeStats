import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useDeleteTeam, useSaveTeam, useTeam } from "../api/hooks";
import { ErrorBox, Loading } from "../components/ui";
import { useGameData } from "../lib/meta";

interface Row { riot_id: string; role: string }

const POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"];
const emptyRows = (): Row[] => [...POSITIONS.map((role) => ({ riot_id: "", role })), { riot_id: "", role: "" }];

export function TeamFormPage() {
  const params = useParams();
  const teamId = params.teamId ? Number(params.teamId) : undefined;
  const existing = useTeam(teamId);
  const save = useSaveTeam(teamId);
  const remove = useDeleteTeam();
  const navigate = useNavigate();
  const { position } = useGameData();

  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [minMembers, setMinMembers] = useState(4);
  const [rows, setRows] = useState<Row[]>(emptyRows);

  useEffect(() => {
    const team = existing.data;
    if (!team) return;
    setName(team.name);
    setTag(team.tag);
    setMinMembers(team.min_members);
    setRows([...team.members.map((m) => ({ riot_id: m.riot_id, role: m.role })), { riot_id: "", role: "" }]);
  }, [existing.data]);

  if (teamId !== undefined && existing.isPending) return <Loading />;
  if (existing.error) return <ErrorBox error={existing.error} />;

  const update = (i: number, patch: Partial<Row>) => setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)));

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    const members = rows.filter((r) => r.riot_id.trim()).map((r) => ({ riot_id: r.riot_id.trim(), role: r.role }));
    save.mutate(
      { name, tag, min_members: minMembers, members },
      { onSuccess: (team) => navigate(`/teams/${team.id}`) },
    );
  };

  return (
    <>
      <section>
        <h1>{teamId ? "Team bearbeiten" : "Neues Team"}</h1>
        <div className="muted">Spieler werden über ihre Riot-ID (Name#TAG) gefunden. Auswechselspieler einfach mit eintragen.</div>
      </section>
      {save.error && <ErrorBox error={save.error} />}
      <form className="card stack" onSubmit={submit}>
        <div className="grid three">
          <label className="field">Teamname
            <input className="input" required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">Kürzel
            <input className="input" maxLength={8} value={tag} onChange={(e) => setTag(e.target.value)} />
          </label>
          <label className="field">Mindestanzahl Teamspieler pro Spiel
            <select value={minMembers} onChange={(e) => setMinMembers(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} Spieler{n === 4 ? " (empfohlen)" : ""}</option>)}
            </select>
          </label>
        </div>
        <p className="muted small" style={{ margin: 0 }}>
          Ein Custom Game zählt als Teamspiel, wenn mindestens so viele eingetragene Spieler <em>auf derselben Seite</em>{" "}
          gespielt haben. Mit 4 werden auch Spiele mit einer Aushilfe erfasst.
        </p>
        <div>
          <h2>Spieler</h2>
          <div className="grid" style={{ gap: ".5rem" }}>
            {rows.map((row, i) => (
              <div className="member-row" key={i}>
                <input className="input" placeholder="Name#TAG" value={row.riot_id} aria-label={`Spieler ${i + 1}`}
                  onChange={(e) => update(i, { riot_id: e.target.value })} />
                <select value={row.role} onChange={(e) => update(i, { role: e.target.value })} aria-label={`Rolle ${i + 1}`}>
                  <option value="">Rolle –</option>
                  {POSITIONS.map((p) => <option key={p} value={p}>{position(p)}</option>)}
                </select>
                <button type="button" className="btn small" title="Entfernen"
                  onClick={() => setRows((r) => (r.length > 1 ? r.filter((_, j) => j !== i) : [{ riot_id: "", role: "" }]))}>✕</button>
              </div>
            ))}
          </div>
          <button type="button" className="btn small" style={{ marginTop: ".6rem" }}
            onClick={() => setRows((r) => [...r, { riot_id: "", role: "" }])}>+ Spieler</button>
        </div>
        <div className="row">
          <button className="btn primary" type="submit" disabled={save.isPending}>
            {save.isPending ? "Suche Spieler …" : teamId ? "Speichern" : "Team anlegen"}
          </button>
          <Link className="btn" to={teamId ? `/teams/${teamId}` : "/teams"}>Abbrechen</Link>
        </div>
      </form>
      {teamId !== undefined && (
        <button className="btn danger" type="button" disabled={remove.isPending}
          onClick={() => {
            if (confirm("Team wirklich löschen?")) remove.mutate(teamId, { onSuccess: () => navigate("/teams") });
          }}>Team löschen</button>
      )}
    </>
  );
}
