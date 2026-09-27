import { type FormEvent, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useMe, useMeta, useStartScout } from "../api/hooks";
import { ErrorBox } from "./ui";
import { splitRiotId } from "../lib/format";
import { type UiStyle, applyStyle, storedStyle } from "../lib/style";

export function PlayerSearch({ big, autoFocus }: { big?: boolean; autoFocus?: boolean }) {
  const navigate = useNavigate();
  const { data: meta } = useMeta();
  const start = useStartScout();
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
    start.mutate({ riotIds: [`${parts[0]}#${parts[1]}`] }, {
      onSuccess: (res) => {
        setValue("");
        navigate(`/scout/${res.key}`);
      },
    });
  };
  return (
    <form className="search" onSubmit={submit} role="search">
      <input
        className="input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={big && meta?.demo ? "Name#TAG – z.B. NLE Polaris#EUW" : "Name#TAG"}
        aria-label="Riot-ID suchen"
        aria-invalid={!!error || !!start.error}
        title={error || start.error?.message || undefined}
        autoFocus={autoFocus}
      />
      <button className={`btn${big ? " primary" : ""}`} type="submit" disabled={start.isPending}>
        {big ? "Spieler suchen" : "Suchen"}
      </button>
      {big && start.error && <ErrorBox error={start.error} />}
    </form>
  );
}

/** Umschalter zwischen Prime-League-Stil und nüchternem Analyse-Stil */
function StyleToggle() {
  const [style, setStyle] = useState<UiStyle>(storedStyle);
  const next: UiStyle = style === "prime" ? "analytics" : "prime";
  return (
    <button type="button" className="btn small style-toggle" title="Darstellung umschalten"
      aria-label={`Stil: ${style === "prime" ? "Prime League" : "Analyse"} – umschalten`}
      onClick={() => {
        applyStyle(next);
        setStyle(next);
      }}>
      {style === "prime" ? "◧ Analyse-Stil" : "◧ Prime-Stil"}
    </button>
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
  const { data: me } = useMe();
  const { pathname } = useLocation();
  return (
    <>
      <header className="topbar">
        <div className="inner">
          <NavLink className="brand" to="/"><span className="logo">PS</span> PrimeStats</NavLink>
          <nav className="nav">
            <NavLink to="/" className={() => (pathname === "/" || pathname.startsWith("/scout") || pathname.startsWith("/player") ? "active" : "")}>Suche</NavLink>
            <NavLink to="/teams">Teams</NavLink>
            {me?.user && <NavLink to="/groups">Gruppen</NavLink>}
            <NavLink to="/uploader">Scrims hochladen</NavLink>
          </nav>
          {meta?.demo && <span className="badge official" title="Es werden generierte Beispieldaten verwendet">Demo-Modus</span>}
          <div className="topbar-right">
            {pathname !== "/" && <PlayerSearch />}
            <StyleToggle />
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
