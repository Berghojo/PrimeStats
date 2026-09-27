import { Link } from "react-router-dom";

import type { Match } from "../api/types";
import { dt, duration } from "../lib/format";
import { TeamSideView } from "./TeamSideView";
import { ResultBadge, TournamentBadge } from "./ui";

interface Props {
  match: Match;
  focus: string;
  selected: boolean;
  onToggle: () => void;
}

export function GameCard({ match, focus, selected, onToggle }: Props) {
  const me = [...match.blue.players, ...match.red.players].find((p) => p.puuid === focus);
  const win = me?.win ?? false;
  const focusSet = new Set([focus]);
  return (
    <div
      className={`game ${win ? "win" : "loss"}${selected ? " selected" : ""}`}
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest("a, input")) onToggle();
      }}
    >
      <input type="checkbox" checked={selected} onChange={onToggle} aria-label="Spiel auswählen" />
      <div className="meta">
        <ResultBadge win={win} />
        <span>{dt(match.created)}</span>
        <span className="muted">{duration(match.duration)} · Patch {match.version}</span>
        <TournamentBadge code={!!match.tournament_code} />
      </div>
      <TeamSideView team={match.blue} focus={focusSet} />
      <div className="versus">
        <span className="badge blue">{match.blue.kills}</span> vs <span className="badge red">{match.red.kills}</span>
        <div><Link className="small" to={`/match/${match.match_id}`}>Details</Link></div>
      </div>
      <TeamSideView team={match.red} focus={focusSet} right />
    </div>
  );
}
