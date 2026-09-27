// Spiegelt die Pydantic-Schemas in backend/primestats/schemas.py

export type Side = "blue" | "red";
export type Label = "" | "official" | "scrim";

export interface Champion { id: string; name: string }

export interface Meta {
  demo: boolean;
  /** Riot-API verfügbar – sonst nur hochgeladene Spiele */
  configured: boolean;
  uploader_url: string;
  ddragon_version: string;
  champions: Record<string, Champion>;
  positions: Record<string, string>;
  labels: Record<string, string>;
}

export interface Player {
  participant_id: number;
  puuid: string;
  name: string;
  tag: string;
  team_id: number;
  position: string;
  champion_id: number;
  win: boolean;
  kills: number;
  deaths: number;
  assists: number;
  kda: number;
  cs: number;
  gold: number;
  damage: number;
  damage_taken: number;
  vision_score: number;
  wards_placed: number;
  wards_killed: number;
  control_wards: number;
  level: number;
  first_blood: boolean;
  items: number[];
  spells: [number, number];
}

export interface TeamSide {
  team_id: number;
  side: Side;
  win: boolean;
  bans: number[];
  kills: number;
  towers: number;
  inhibitors: number;
  dragons: number;
  barons: number;
  heralds: number;
  grubs: number;
  atakhan: number;
  first_blood: boolean;
  first_tower: boolean;
  first_dragon: boolean;
  first_baron: boolean;
  first_herald: boolean;
  first_grubs: boolean;
  gold: number;
  damage: number;
  players: Player[];
}

export interface Match {
  match_id: string;
  created: string;
  duration: number;
  version: string;
  game_type: string;
  queue_id: number;
  tournament_code: string;
  blue: TeamSide;
  red: TeamSide;
}

export interface PlayerGames {
  account: { puuid: string; game_name: string; tag_line: string };
  games: Match[];
}

export interface Analysis {
  stats: { key: string; label: string }[];
  players: { puuid: string; name: string; games: number; position: string; focus: boolean }[];
  series: Record<string, Record<string, (number | null)[]>>;
  minutes: number;
  matches: Match[];
}

export interface Member {
  puuid: string;
  game_name: string;
  tag_line: string;
  role: string;
  riot_id: string;
}

export interface Team {
  id: number;
  name: string;
  tag: string;
  min_members: number;
  created_at: string;
  last_synced: string | null;
  members: Member[];
  public: boolean;
  can_edit: boolean;
  can_delete: boolean;
  /** Scrims sind nur für Spieler im Kader sichtbar */
  can_see_scrims: boolean;
}

export interface TeamInput {
  name: string;
  tag: string;
  min_members: number;
  public: boolean;
  members: { riot_id: string; role: string }[];
}

export interface SyncJob {
  status: "running" | "done" | "error";
  message: string;
  done: number;
  total: number;
  percent: number;
  new_games: number;
  error: string;
}

export interface Overview {
  games: number;
  wins: number;
  losses: number;
  winrate: number | null;
  blue_games: number;
  blue_wins: number;
  blue_winrate: number | null;
  red_games: number;
  red_wins: number;
  red_winrate: number | null;
  duration: number | null;
  duration_win: number | null;
  duration_loss: number | null;
  kills: number | null;
  deaths: number | null;
  towers: number | null;
  towers_lost: number | null;
  gd10: number | null;
  gd15: number | null;
  timeline_games: number;
  first_blood: number | null;
  first_tower: number | null;
  first_dragon: number | null;
  first_herald: number | null;
  first_grubs: number | null;
  first_baron: number | null;
}

export interface ChampionStat {
  champion_id: number;
  games: number;
  wins: number;
  winrate: number;
  kills: number;
  deaths: number;
  assists: number;
  kda: number;
}

export interface PlayerReport {
  puuid: string;
  name: string;
  member: boolean;
  position: string;
  games: number;
  wins: number;
  winrate: number;
  kills: number;
  deaths: number;
  assists: number;
  kda: number;
  cspm: number;
  gpm: number;
  dpm: number;
  dtpm: number;
  vspm: number;
  wards: number;
  wards_killed: number;
  control_wards: number;
  kp: number | null;
  damage_share: number | null;
  gold_share: number | null;
  first_blood: number;
  gd10: number | null;
  gd15: number | null;
  csd15: number | null;
  xpd15: number | null;
  champions: ChampionStat[];
}

export interface PickStat { champion_id: number; games: number; wins: number; winrate: number; players: string[] }
export interface BanStat { champion_id: number; count: number }

export interface MonsterStat {
  key: string;
  label: string;
  us: number;
  them: number;
  share: number | null;
  us_avg: number;
  them_avg: number;
  first_time: number | null;
}

export interface Curve { values: (number | null)[]; counts: number[] }

export interface TrendPoint { match_id: string; date: string; win: boolean; gd15: number | null; kills: number; deaths: number }

export interface Report {
  overview: Overview;
  players: PlayerReport[];
  picks: PickStat[];
  enemy_picks: PickStat[];
  our_bans: BanStat[];
  enemy_bans: BanStat[];
  monsters: MonsterStat[];
  gold_curves: Record<"all" | "win" | "loss", Curve>;
  trend: TrendPoint[];
}

export interface HistoryRow {
  match_id: string;
  date: string;
  duration: number;
  patch: string;
  win: boolean;
  side: Side;
  us: TeamSide;
  them: TeamSide;
  opponent: string;
  gold_diff: number;
  gd15: number | null;
  label: Label;
  included: boolean;
  tournament: boolean;
  selected: boolean;
}

export interface Filters {
  label: "all" | Label;
  side: "all" | Side;
  patch: string;
  opponent: string;
  last: number;
}

export interface TeamReport {
  team: Team;
  filters: Filters;
  report: Report;
  history: HistoryRow[];
  patches: string[];
  opponents: string[];
  job: SyncJob | null;
}

export interface User { id: number; username: string; created_at: string }

export interface RiotLink {
  puuid: string;
  game_name: string;
  tag_line: string;
  riot_id: string;
  linked_at: string;
  last_upload_at: string | null;
}

export interface Me { user: User | null; riot_accounts: RiotLink[] }

export interface LinkCode { code: string; expires_at: string }

export interface RosterPlayer { puuid: string; game_name: string; tag_line: string; games: number; position: string }

export interface ScoutSummary {
  puuid: string;
  game_name: string;
  tag_line: string;
  team_tag: string;
  games: number;
  roster: RosterPlayer[];
  updated_at: string;
}

export interface ScoutReport {
  player: { puuid: string; game_name: string; tag_line: string };
  team_tag: string;
  roster: RosterPlayer[];
  min_members: number;
  updated_at: string;
  filters: Filters;
  report: Report;
  history: HistoryRow[];
  patches: string[];
  opponents: string[];
  job: SyncJob | null;
}
