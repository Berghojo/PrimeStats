import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useCreateGroup, useGroups, useMe } from "../api/hooks";
import type { GroupSummary } from "../api/types";
import { InfoTip } from "../components/InfoTip";
import { Empty, ErrorBox, Loading } from "../components/ui";
import { ago } from "../lib/format";

function GroupCard({ group }: { group: GroupSummary }) {
  return (
    <Link className="card team-card" to={`/groups/${group.key}`}>
      <div className="team-head">
        <div className="team-logo">{group.name.slice(0, 3).toUpperCase()}</div>
        <div>
          <h3>{group.name}</h3>
          <div className="muted small">{group.teams.length} Teams · geändert {ago(group.updated_at)}</div>
        </div>
      </div>
      <div className="names muted small">{group.teams.join(" · ") || "Noch keine Teams"}</div>
    </Link>
  );
}

function NewGroupForm() {
  const create = useCreateGroup();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    if (!name.trim()) return;
    create.mutate({ name }, { onSuccess: (g) => navigate(`/groups/${g.key}`) });
  };
  return (
    <form className="row" onSubmit={submit}>
      <input className="input" value={name} maxLength={60} onChange={(e) => setName(e.target.value)}
        placeholder="Name, z.B. Prime League Gruppe 4" aria-label="Name der neuen Gruppe" />
      <button className="btn primary" type="submit" disabled={create.isPending || !name.trim()}>+ Gruppe anlegen</button>
      {create.error && <ErrorBox error={create.error} />}
    </form>
  );
}

export function GroupsPage() {
  const { data: me } = useMe();
  const loggedIn = !!me?.user;
  const groups = useGroups(loggedIn);
  return (
    <>
      <section className="row between">
        <h1>
          Gruppen
          <InfoTip>
            Speichere mehrere Teams – angelegte Teams oder gescoutete Gegner – als Gruppe (z.B. deine Prime-League-Gruppe)
            und vergleiche ihre Kennzahlen und alle Spieler direkt miteinander. Gruppen lassen sich per Link teilen.
          </InfoTip>
        </h1>
      </section>
      {!me ? <Loading /> : !loggedIn ? (
        <Empty>
          <h2>Anmelden, um Gruppen zu speichern</h2>
          <p>Gruppen gehören zu deinem Konto. Geteilte Gruppen-Links kannst du auch ohne Anmeldung ansehen.</p>
          <Link className="btn primary" to="/login?next=/groups">Anmelden</Link>
        </Empty>
      ) : (
        <>
          <section className="card"><NewGroupForm /></section>
          {groups.isPending ? <Loading /> : groups.error ? <ErrorBox error={groups.error} /> : groups.data.length === 0 ? (
            <Empty>Noch keine Gruppen angelegt.</Empty>
          ) : (
            <div className="grid three">{groups.data.map((g) => <GroupCard key={g.key} group={g} />)}</div>
          )}
        </>
      )}
    </>
  );
}
