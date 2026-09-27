import { useMeta } from "../api/hooks";

export function UploaderPage() {
  const { data: meta } = useMeta();
  const server = window.location.origin;
  return (
    <>
      <section>
        <h1>Scrims hochladen</h1>
        <div className="muted">
          Die Riot-API liefert Custom Games nur, wenn sie mit einem Turniercode erstellt wurden (z.B. Prime-League-Spiele).
          Normale Custom-Lobbys – also die meisten Scrims – kennt nur der League Client. Der PrimeStats-Uploader liest sie
          dort aus und lädt alles hoch, was noch nicht auf dem Server ist.
        </div>
      </section>

      {meta && !meta.uploads_enabled && (
        <div className="flash error">
          Uploads sind auf diesem Server noch deaktiviert. Der Admin muss im Backend <code>UPLOAD_TOKEN</code> setzen.
        </div>
      )}

      <section className="grid two">
        <div className="card stack">
          <h2>So geht&apos;s</h2>
          <ol className="steps">
            <li>
              <b>Uploader herunterladen:</b>{" "}
              <a href={meta?.uploader_url} target="_blank" rel="noreferrer">PrimeStats-Uploader.exe</a>{" "}
              <span className="muted small">(Windows; beim ersten Start ggf. „Weitere Informationen → Trotzdem ausführen“)</span>
            </li>
            <li><b>League Client starten und einloggen.</b> Das Spiel selbst muss nicht laufen.</li>
            <li>
              <b>Uploader starten.</b> Beim ersten Start fragt er nach Server-Adresse und Upload-Token und merkt sich beides
              in <code>primestats-uploader.ini</code> neben der EXE.
            </li>
            <li>
              <b>Fertig:</b> Der Uploader liest die Match-History, fragt den Server, welche Custom Games schon bekannt sind,
              und lädt nur neue Spiele samt Timeline hoch. Sie werden automatisch allen passenden Teams zugeordnet.
            </li>
          </ol>
        </div>
        <div className="card stack">
          <h2>Verbindungsdaten</h2>
          <label className="field">Server-Adresse
            <input className="input" readOnly value={server} onFocus={(e) => e.target.select()} />
          </label>
          <label className="field">Upload-Token
            <input className="input" readOnly value="bekommst du vom Server-Admin" />
          </label>
          <p className="muted small">
            Ein Teammitglied reicht, wenn es bei (fast) allen Scrims mitspielt – es sieht in seiner History alle 10 Spieler.
            Spiele, die es verpasst hat, kann jedes andere Mitglied zusätzlich hochladen; doppelte Spiele werden erkannt.
          </p>
          <p className="muted small">
            Der Client hält nur eine begrenzte Match-History vor. Am besten nach jedem Scrim-Abend oder mindestens einmal pro
            Woche hochladen, damit keine Spiele herausrutschen.
          </p>
        </div>
      </section>
    </>
  );
}
