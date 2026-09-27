import type { TeamSide } from "../api/types";
import { ChampIcon } from "./ChampIcon";

export function TeamSideView({ team, focus, right }: { team: TeamSide; focus?: Set<string>; right?: boolean }) {
  return (
    <div className={`side${right ? " red" : ""}`}>
      <div className="champ-row">
        {team.players.map((p) => <ChampIcon key={p.puuid} id={p.champion_id} />)}
        <span className="muted small">&nbsp;Bans</span>
        {team.bans.map((b, i) => <ChampIcon key={i} id={b} size="sm" ban />)}
      </div>
      <div className="names">
        {team.players.map((p, i) => (
          <span key={p.puuid}>
            {focus?.has(p.puuid) ? <b>{p.name}</b> : p.name}
            {i < team.players.length - 1 ? " · " : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
