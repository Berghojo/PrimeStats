import { type FormEvent, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useMe, useMeta } from "../api/hooks";
import { splitRiotId } from "../lib/format";

export function PlayerSearch({ big, autoFocus }: { big?: boolean; autoFocus?: boolean }) {
  const navigate = useNavigate();
  const { data: meta } = useMeta();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    const parts = splitRiotId(value);
    if (!parts) {
      setError("Bitte im Format Name#TAG eingeben.");
      return;
    }
    setError("");
    navigate(`/player/${encodeURIComponent(parts[0])}/${encodeURIComponent(parts[1])}`);
  };
  return (
    <form className="search" onSubmit={submit} role="search">
      <input
        className="input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={big && meta?.demo ? "Name#TAG – z.B. NLE Polaris#EUW" : "Name#TAG"}
        aria-label="Riot-ID suchen"
        aria-invalid={!!error}
        title={error || undefined}
        autoFocus={autoFocus}
      />
      <button className={`btn${big ? " primary" : ""}`} type="submit">{big ? "Spieler suchen" : "Suchen"}</button>
    </form>
  );
}

function UserMenu() {
  const { data: me } = useMe();
  const { pathname } = useLocation();
  if (!me) return null;
  if (!me.user) {
    return <NavLink className="btn small" to={`/login?next=${encodeURIComponent(pathname)}`}>Anmelden</NavLink>;
  }
  return (
    <NavLink className="user-link" to="/account" title="Konto">
      <span className="avatar">{me.user.username.slice(0, 1).toUpperCase()}</span>
      <span>{me.user.username}</span>
    </NavLink>
  );
}

export function Layout() {
  const { data: meta } = useMeta();
  const { pathname } = useLocation();
  return (
    <>
      <header className="topbar">
        <div className="inner">
          <NavLink className="brand" to="/"><span className="logo">PS</span> PrimeStats</NavLink>
          <nav className="nav">
            <NavLink to="/" className={() => (pathname === "/" || pathname.startsWith("/player") ? "active" : "")}>Spielersuche</NavLink>
            <NavLink to="/scout">Scouting</NavLink>
            <NavLink to="/teams">Teams</NavLink>
            <NavLink to="/uploader">Scrims hochladen</NavLink>
          </nav>
          {meta?.demo && <span className="badge official" title="Es werden generierte Beispieldaten verwendet">Demo-Modus</span>}
          <div className="topbar-right">
            {pathname !== "/" && <PlayerSearch />}
            <UserMenu />
          </div>
        </div>
      </header>
      <main className="container stack">
        {meta && !meta.configured && (
          <div className="flash">
            Kein Riot-API-Key konfiguriert – PrimeStats zeigt nur Spiele, die per{" "}
            <NavLink to="/uploader">Uploader</NavLink> aus dem League Client hochgeladen wurden. Für Prime-League-Spiele
            (Turniercode) im Backend <code>LOL_API_KEY</code> setzen.
          </div>
        )}
        <Outlet />
      </main>
    </>
  );
}
