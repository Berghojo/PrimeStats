import { useState } from "react";
import { Link } from "react-router-dom";

import { useAddGroupEntry, useCreateGroup, useGroups, useMe } from "../api/hooks";
import type { GroupEntryKind } from "../api/types";

/** Auswahl „Zu Gruppe hinzufügen“ für Team- und Scouting-Seiten (nur angemeldet). */
export function AddToGroup({ kind, refId }: { kind: GroupEntryKind; refId: string }) {
  const { data: me } = useMe();
  const groups = useGroups(!!me?.user);
  const add = useAddGroupEntry();
  const create = useCreateGroup();
  const [done, setDone] = useState<{ key: string; name: string } | null>(null);
  if (!me?.user) return null;
  const pick = (value: string) => {
    const entry = { kind, ref: refId, name: "" };
    if (value === "__new") {
      const name = window.prompt("Name der neuen Gruppe")?.trim();
      if (name) create.mutate({ name, entries: [entry] }, { onSuccess: (g) => setDone({ key: g.key, name: g.name }) });
    } else if (value) {
      add.mutate({ key: value, entry }, { onSuccess: (g) => setDone({ key: g.key, name: g.name }) });
    }
  };
  const error = add.error ?? create.error;
  return (
    <span className="row">
      <select className="btn" value="" aria-label="Zu Gruppe hinzufügen" disabled={add.isPending || create.isPending}
        onChange={(e) => pick(e.target.value)} title={error?.message}>
        <option value="">+ Zu Gruppe …</option>
        {groups.data?.map((g) => <option key={g.key} value={g.key}>{g.name}</option>)}
        <option value="__new">Neue Gruppe …</option>
      </select>
      {done && <Link className="small" to={`/groups/${done.key}`}>Hinzugefügt zu „{done.name}“</Link>}
    </span>
  );
}
