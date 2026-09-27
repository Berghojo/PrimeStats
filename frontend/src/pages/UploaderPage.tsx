import { Link } from "react-router-dom";

import { useMe, useMeta } from "../api/hooks";

export function UploaderPage() {
  const { data: meta } = useMeta();
  const { data: me } = useMe();
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

      <section className="grid two">
        <div className="card stack">
          <h2>So geht&apos;s</h2>
          <ol className="steps">
            <li>
              <b>Konto erstellen</b> –{" "}
              {me?.user ? <>erledigt, du bist als <b>{me.user.username}</b> angemeldet.</> : (
                <Link to="/login?mode=register&next=/account">jetzt registrieren</Link>
              )}
            </li>
            <li>
              <b>Uploader herunterladen:</b>{" "}
              <a href={meta?.uploader_url} target="_blank" rel="noreferrer">PrimeStats-Uploader.exe</a>{" "}
              <span className="muted small">(Windows; beim ersten Start ggf. „Weitere Informationen → Trotzdem ausführen“)</span>
            </li>
            <li><b>League Client starten und einloggen.</b> Das Spiel selbst muss nicht laufen.</li>
            <li>
              <b>Uploader starten.</b> Beim ersten Start mit einem Riot-Account fragt er nach einem Code: Den erzeugst du
              unter <Link to="/account">Konto → „Riot-Account verknüpfen“</Link>. Danach ist der Account mit deinem Konto
              verbunden und der Uploader lädt bei jedem Start ohne Rückfrage hoch.
            </li>
            <li>
              <b>Fertig:</b> Neue Custom Games werden samt Timeline hochgeladen und automatisch allen passenden Teams
              zugeordnet.
            </li>
          </ol>
        </div>
        <div className="card stack">
          <h2>Gut zu wissen</h2>
          <p className="muted small">
            Hochgeladen werden nur Spiele, in denen der im Client eingeloggte Riot-Account mitgespielt hat. Scrims sind privat:
            Sie sehen nur Spieler, die mitgespielt haben, und Mitglieder der zugeordneten Teams (bzw. alle, wenn das Team
            öffentlich ist).
          </p>
          <p className="muted small">
            Ein Teammitglied reicht, wenn es bei (fast) allen Scrims mitspielt – jedes Spiel enthält alle 10 Spieler. Spiele,
            die es verpasst hat, kann jedes andere Mitglied zusätzlich hochladen; doppelte Spiele werden erkannt.
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
