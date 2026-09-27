import { type FormEvent, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useLogin, useMe, useRegister } from "../api/hooks";
import { ErrorBox } from "../components/ui";

export function LoginPage() {
  const [params] = useSearchParams();
  const next = params.get("next") || "/account";
  const [mode, setMode] = useState<"login" | "register">(params.get("mode") === "register" ? "register" : "login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [localError, setLocalError] = useState("");
  const { data: me } = useMe();
  const login = useLogin();
  const register = useRegister();
  const navigate = useNavigate();
  const action = mode === "login" ? login : register;

  if (me?.user) return <Navigate to={next} replace />;

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    setLocalError("");
    if (mode === "register" && password !== repeat) {
      setLocalError("Die Passwörter stimmen nicht überein.");
      return;
    }
    action.mutate({ username, password }, { onSuccess: () => navigate(next, { replace: true }) });
  };

  return (
    <section className="auth">
      <div className="card stack">
        <div className="tabs">
          <button type="button" className={mode === "login" ? "on" : ""} onClick={() => setMode("login")}>Anmelden</button>
          <button type="button" className={mode === "register" ? "on" : ""} onClick={() => setMode("register")}>Konto erstellen</button>
        </div>
        {(localError || action.error) && <ErrorBox error={localError || action.error} />}
        <form className="stack" onSubmit={submit}>
          <label className="field">Benutzername oder E-Mail
            <input className="input" autoComplete="username" required minLength={3} maxLength={64}
              pattern="\s*[A-Za-z0-9_.+@\-]{3,64}\s*" title="3–64 Zeichen: Buchstaben, Ziffern und _ . - + @ (z.B. deine E-Mail-Adresse)"
              value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </label>
          <label className="field">Passwort
            <input className="input" type="password" required minLength={mode === "register" ? 8 : 1}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {mode === "register" && (
            <label className="field">Passwort wiederholen
              <input className="input" type="password" required minLength={8} autoComplete="new-password"
                value={repeat} onChange={(e) => setRepeat(e.target.value)} />
            </label>
          )}
          <button className="btn primary" type="submit" disabled={action.isPending}>
            {mode === "login" ? "Anmelden" : "Konto erstellen"}
          </button>
        </form>
        {mode === "register" && (
          <p className="muted small">
            Nach der Registrierung verknüpfst du deinen Riot-Account über den PrimeStats-Uploader. Erst dann kannst du
            Scrims hochladen und siehst private Teamdaten.
          </p>
        )}
      </div>
    </section>
  );
}
