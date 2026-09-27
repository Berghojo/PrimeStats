import { Link, useParams, useSearchParams } from "react-router-dom";

import { useMatch, useTeam } from "../api/hooks";
import { ChampIcon } from "../components/ChampIcon";
import { ErrorBox, Loading, TournamentBadge } from "../components/ui";
import { dt, duration, num, pct } from "../lib/format";
import { useGameData } from "../lib/meta";

export function MatchPage() {
  const { matchId = "" } = useParams();
  const [params] = useSearchParams();
  const teamId = params.get("team") ? Number(params.get("team")) : undefined;
  const { data: match, error, isPending } = useMatch(matchId);
  const { data: team } = useTeam(teamId);
  const { champion, position } = useGameData();

  if (isPending) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const focus = new Set(team?.members.map((m) => m.puuid) ?? []);
  const minutes = Math.max(match.duration / 60, 1 / 60);
  const analysisLink = `/analysis?m=${encodeURIComponent(match.match_id)}${teamId ? `&team=${teamId}` : ""}`;

  return (
    <>
      <section className="row between">
        <div>
          <h1>Scoreboard</h1>
          <div className="muted row">
            <span>{dt(match.created)} · {duration(match.duration)} · Patch {match.version}</span>
            <TournamentBadge code={!!match.tournament_code} />
            <span className="small">{match.match_id}</span>
          </div>
        </div>
        <Link className="btn" to={analysisLink}>Zeitverlauf</Link>
      </section>
      {[match.blue, match.red].map((side) => (
        <section className="card" key={side.team_id}>
          <div className={`team-strip ${side.side}`}>
            <span>{side.side === "blue" ? "Blue" : "Red"} Side · {side.win ? "Sieg" : "Niederlage"}</span>
            <span className="nowrap">
              {side.kills} Kills · {side.towers} Türme · {side.dragons} Drachen · {side.barons} Barone · {side.grubs} Grubs
            </span>
          </div>
          <div className="row small muted" style={{ margin: ".5rem 0" }}>
            Bans: {side.bans.length ? side.bans.map((b, i) => <ChampIcon key={i} id={b} size="sm" ban />) : "–"}
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th className="left">Spieler</th><th>Rolle</th><th>K / D / A</th><th>KDA</th><th>CS</th><th>CS/min</th>
                  <th>Gold</th><th>Schaden</th><th>Sch.-Anteil</th><th>Vision</th><th>Kontrollwards</th>
                </tr>
              </thead>
              <tbody>
                {side.players.map((p) => (
                  <tr key={p.puuid} className={focus.has(p.puuid) ? "focus" : ""}>
                    <td className="left">
                      <div className="champ-cell">
                        <ChampIcon id={p.champion_id} />
                        <div><b>{p.name}</b><div className="muted small">{champion(p.champion_id).name} · Lvl {p.level}</div></div>
                      </div>
                    </td>
                    <td>{position(p.position)}</td>
                    <td>{p.kills} / {p.deaths} / {p.assists}</td>
                    <td>{num(p.kda, 2)}</td>
                    <td>{p.cs}</td>
                    <td>{num(p.cs / minutes, 1)}</td>
                    <td>{num(p.gold, 0)}</td>
                    <td>{num(p.damage, 0)}</td>
                    <td>{pct(side.damage ? p.damage / side.damage : null)}</td>
                    <td>{p.vision_score}</td>
                    <td>{p.control_wards}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </>
  );
}
