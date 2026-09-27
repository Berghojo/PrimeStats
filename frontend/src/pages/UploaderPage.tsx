import { Link } from "react-router-dom";

import { useMe, useMeta } from "../api/hooks";
import { InfoTip } from "../components/InfoTip";

export function UploaderPage() {
  const { data: meta } = useMeta();
  const { data: me } = useMe();
  return (
    <>
      <section>
        <h1>
          Scrims hochladen
          <InfoTip>
            Die Riot-API liefert Custom Games nur, wenn sie mit einem Turniercode erstellt wurden (z.B. Prime-League-Spiele).
            Normale Custom-Lobbys – also die meisten Scrims – kennt nur der League Client. Der PrimeStats-Uploader liest sie
            dort aus und lädt alles hoch, was noch nicht auf dem Server ist.
          </InfoTip>
        </h1>
      </section>

      <section>
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
              <InfoTip>Windows; beim ersten Start ggf. „Weitere Informationen → Trotzdem ausführen“.</InfoTip>
            </li>
            <li><b>League Client starten und einloggen.</b> Das Spiel selbst muss nicht laufen.</li>
            <li>
              <b>Uploader starten.</b> Beim ersten Start mit einem Riot-Account fragt er nach einem Code: Den erzeugst du
              unter <Link to="/account">Konto → „Riot-Account verknüpfen“</Link>. Danach ist der Account mit deinem Konto
              verbunden und der Uploader lädt bei jedem Start ohne Rückfrage hoch.
              <InfoTip>
                Der Client gibt nur die letzten ~20 Spiele heraus. Damit keine Scrims herausrutschen, das Tool am besten im
                Hintergrund laufen lassen: <code>PrimeStats-Uploader.exe --watch</code> lädt neue Custom Games direkt nach
                Spielende hoch, <code>--autostart on</code> startet das automatisch mit Windows.
              </InfoTip>
            </li>
            <li>
              <b>Fertig:</b> Neue Custom Games werden samt Timeline hochgeladen und automatisch allen passenden Teams
              zugeordnet.
              <InfoTip>
                Hochgeladen werden nur Spiele, in denen der im Client eingeloggte Riot-Account mitgespielt hat. Scrims sind
                privat: Sie sehen ausschließlich Spieler, deren verknüpfter Riot-Account im Kader eines Teams steht, dem das
                Spiel zugeordnet ist. Ein Teammitglied reicht, wenn es bei (fast) allen Scrims mitspielt – jedes Spiel
                enthält alle 10 Spieler; doppelte Uploads werden erkannt.
              </InfoTip>
            </li>
          </ol>
        </div>
      </section>
    </>
  );
}
