import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { useChangePassword, useLinkCode, useLogout, useMe, useMeta, useTeams, useUnlink } from "../api/hooks";
import type { LinkCode } from "../api/types";
import { ErrorBox, Loading } from "../components/ui";
import { ago, dt } from "../lib/format";
import { InfoTip } from "../components/InfoTip";

function useCountdown(until: string | undefined) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!until) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [until]);
  return until ? Math.max(0, Math.round((new Date(until).getTime() - now) / 1000)) : 0;
}

function LinkPanel({ onDone }: { onDone: () => void }) {
  const createCode = useLinkCode();
  const { data: meta } = useMeta();
  const [code, setCode] = useState<LinkCode | null>(null);
  const [linkedBefore, setLinkedBefore] = useState<number | null>(null);
  const { data: me } = useMe(code !== null);
  const seconds = useCountdown(code?.expires_at);

  // neu verknüpfter Account erscheint -> fertig
  useEffect(() => {
    if (code && me && linkedBefore !== null && me.riot_accounts.length > linkedBefore) {
      setCode(null);
      onDone();
    }
  }, [me, code, linkedBefore, onDone]);

  const start = () =>
    createCode.mutate(undefined, {
      onSuccess: (c) => {
        setLinkedBefore(me?.riot_accounts.length ?? 0);
        setCode(c);
      },
    });

  if (!code || seconds === 0) {
    return (
      <div className="stack">
        {code && <p className="neg">Der Code ist abgelaufen.</p>}
        <button className="btn primary" type="button" onClick={start} disabled={createCode.isPending}>
          + Riot-Account verknüpfen
        </button>
        {createCode.error && <ErrorBox error={createCode.error} />}
      </div>
    );
  }
  return (
    <div className="link-panel stack">
      <div className="link-code" aria-label="Verknüpfungscode">{code.code}</div>
      <div className="muted small">gültig noch {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")} min · nur einmal verwendbar</div>
      <ol className="steps">
        <li>League Client starten und mit dem Riot-Account einloggen, der verknüpft werden soll.</li>
        <li><a href={meta?.uploader_url} target="_blank" rel="noreferrer">PrimeStats-Uploader</a> starten.</li>
        <li>Das Tool erkennt den Account und fragt nach dem Code – diesen Code eingeben.</li>
      </ol>
      <div className="row muted small"><span className="spinner" /> Warte auf den Uploader …</div>
      <button className="btn small" type="button" onClick={() => setCode(null)}>Abbrechen</button>
    </div>
  );
}

function PasswordForm() {
  const change = useChangePassword();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    change.mutate({ old_password: oldPw, new_password: newPw }, {
      onSuccess: () => {
        setOldPw("");
        setNewPw("");
      },
    });
  };
  return (
    <form className="stack" onSubmit={submit}>
      <h3>Passwort ändern</h3>
      {change.error && <ErrorBox error={change.error} />}
      {change.isSuccess && <div className="flash ok">Passwort geändert.</div>}
      <input className="input" type="password" placeholder="Aktuelles Passwort" autoComplete="current-password" required
        value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
      <input className="input" type="password" placeholder="Neues Passwort (min. 8 Zeichen)" autoComplete="new-password"
        minLength={8} required value={newPw} onChange={(e) => setNewPw(e.target.value)} />
      <button className="btn" type="submit" disabled={change.isPending}>Ändern</button>
    </form>
  );
}

export function AccountPage() {
  const { data: me, isPending } = useMe();
  const teams = useTeams();
  const unlink = useUnlink();
  const logout = useLogout();
  const [justLinked, setJustLinked] = useState(false);
  const qc = useQueryClient();
  // Neuer Account ändert Sichtbarkeiten und Team-Rechte -> alles neu laden
  const linked = useCallback(() => {
    setJustLinked(true);
    qc.invalidateQueries();
  }, [qc]);

  if (isPending) return <Loading />;
  if (!me?.user) return <Navigate to="/login?next=/account" replace />;

  const myTeams = (teams.data ?? []).filter((t) => t.can_edit);
  return (
    <>
      <section className="row between">
        <div>
          <h1>{me.user.username}</h1>
          <div className="muted">Konto seit {dt(me.user.created_at)}</div>
        </div>
        <button className="btn" type="button" onClick={() => logout.mutate()}>Abmelden</button>
      </section>

      <section className="grid two">
        <div className="card stack">
          <h2>
            Riot-Accounts
            <InfoTip>
              Verknüpfte Accounts weisen dich als Spieler aus: Du siehst deine Scrims, kannst Teams bearbeiten, in deren
              Kader du stehst, und der Uploader lädt Spiele dieser Accounts hoch. Verknüpft wird über den Uploader – so ist
              sichergestellt, dass du im League Client mit dem Account eingeloggt bist.
            </InfoTip>
          </h2>
          {justLinked && <div className="flash ok">Riot-Account verknüpft.</div>}
          {me.riot_accounts.length > 0 ? (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th className="left">Riot-ID</th><th>Verknüpft</th><th>Letzter Upload</th><th /></tr></thead>
                <tbody>
                  {me.riot_accounts.map((r) => (
                    <tr key={r.puuid}>
                      <td className="left"><Link to={`/player/${encodeURIComponent(r.game_name)}/${encodeURIComponent(r.tag_line)}`}>{r.riot_id}</Link></td>
                      <td>{ago(r.linked_at)}</td>
                      <td>{r.last_upload_at ? ago(r.last_upload_at) : "–"}</td>
                      <td>
                        <button className="btn small danger" type="button" disabled={unlink.isPending}
                          onClick={() => confirm(`${r.riot_id} wirklich trennen?`) && unlink.mutate(r.puuid)}>Trennen</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">Noch kein Riot-Account verknüpft.</p>
          )}
          <LinkPanel onDone={linked} />
        </div>

        <div className="stack">
          <div className="card stack">
            <h2>Meine Teams</h2>
            {myTeams.length ? (
              <div className="list-compact">
                {myTeams.map((t) => (
                  <div className="item" key={t.id}>
                    <Link className="grow" to={`/teams/${t.id}`}>{t.name}</Link>
                    <span className="badge">{t.public ? "öffentlich" : "privat"}</span>
                    {t.can_delete && <span className="badge accent">Ersteller</span>}
                  </div>
                ))}
              </div>
            ) : <p className="muted">Keine Teams. <Link to="/teams/new">Team anlegen</Link></p>}
          </div>
          <div className="card"><PasswordForm /></div>
        </div>
      </section>
    </>
  );
}
