import { type FormEvent, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useMeta } from "../api/hooks";
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
            <NavLink to="/teams">Teams</NavLink>
          </nav>
          {meta?.demo && <span className="badge official" title="Es werden generierte Beispieldaten verwendet">Demo-Modus</span>}
          {pathname !== "/" && <PlayerSearch />}
        </div>
      </header>
      <main className="container stack">
        {meta && !meta.configured && (
          <div className="flash error">
            Kein Riot-API-Key konfiguriert. Setze <code>LOL_API_KEY</code> im Backend oder starte mit{" "}
            <code>PRIMESTATS_DEMO=1</code>, um Beispieldaten zu sehen.
          </div>
        )}
        <Outlet />
      </main>
    </>
  );
}
