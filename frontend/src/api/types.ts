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
  tag: string;
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

export interface ChampionRow {
  champion_id: number;
  picks: number;
  wins: number;
  winrate: number | null;
  kda: number | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  cspm: number | null;
  dpm: number | null;
  /** häufigste Rolle */
  position: string;
  /** alle Rollen, auf denen der Champion gespielt wurde */
  positions: { position: string; games: number }[];
  players: { name: string; games: number; wins: number }[];
  bans_by_us: number;
  bans_against: number;
  presence: number | null;
}

export interface Report {
  overview: Overview;
  players: PlayerReport[];
  picks: PickStat[];
  champion_table: ChampionRow[];
  enemy_picks: PickStat[];
  our_bans: BanStat[];
  enemy_bans: BanStat[];
  monsters: MonsterStat[];
  gold_curves: Record<"all" | "win" | "loss", Curve>;
  trend: TrendPoint[];
  jungle: Jungle;
  deaths: DeathEvent[];
  kills: KillEvent[];
}

/** Einordnung eines Kills (erste zutreffende): teamfight (Kette ≥ 3 Kills), dive (unter stehendem Turm des
 *  Opfers), skirmish (≥ 3 Angreifer), gank (Jungler beteiligt), roam (Laner einer anderen Lane), lane (1v1: nur
 *  die direkten Gegner, Bot: 2v2, auch Jungler gegen Jungler), execute (ohne gegnerischen Champion) */
export type DeathKind = "teamfight" | "dive" | "skirmish" | "gank" | "roam" | "lane" | "execute";

export interface KillEvent {
  match_id: string;
  date: string;
  win: boolean;
  side: Side;
  t: number;
  x: number;
  y: number;
  /** aus Sicht der eigenen Beteiligten: lane = 1v1 (Bot: 2v2), gank = eigener Jungler dabei, roam = Laner einer anderen Lane */
  kind: DeathKind;
  victim: { position: string; champion_id: number; name: string };
  by: { puuid: string; position: string; champion_id: number; name: string; killer: boolean }[];
}

export interface DeathEvent {
  match_id: string;
  date: string;
  win: boolean;
  side: Side;
  puuid: string;
  name: string;
  position: string;
  champion_id: number;
  t: number;
  x: number;
  y: number;
  kind: DeathKind;
  by: { position: string; champion_id: number; name: string; killer: boolean }[];
}

export interface JunglePath {
  match_id: string;
  date: string;
  win: boolean;
  side: Side;
  puuid: string;
  champion_id: number;
  /** Position je Minute (Kartenkoordinaten), null wenn unbekannt */
  points: ([number, number] | null)[];
  /** Jungle-CS je Minute – daraus werden die geräumten Camps abgeleitet */
  jungle_cs: number[];
}

export interface JungleEvent {
  match_id: string;
  win: boolean;
  side: Side;
  puuid: string;
  type: "kill" | "assist" | "death";
  /** Sekunden */
  t: number;
  x: number;
  y: number;
}

export interface Jungle {
  players: { puuid: string; name: string; games: number }[];
  paths: JunglePath[];
  events: JungleEvent[];
  path_minutes: number;
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
  /** passt zu den Filtern */
  selected: boolean;
  /** im Spiele-Tab abgewählt */
  excluded: boolean;
  /** Spiel ohne Bans (Custom-Lobby im Blind-Modus) – Bans lassen sich nachtragen */
  bans_missing: boolean;
  /** Bans wurden von Hand nachgetragen */
  bans_manual: boolean;
}

export interface Filters {
  label: "all" | Label;
  side: "all" | Side;
  patch: string;
  last: number;
  /** im Spiele-Tab abgewählte Spiele (zählen nicht in die Statistik) */
  exclude: string[];
}

export interface TeamReport {
  team: Team;
  filters: Filters;
  report: Report;
  history: HistoryRow[];
  patches: string[];
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

export interface ScoutPlayer { puuid: string; game_name: string; tag_line: string }

export interface RosterPlayer extends ScoutPlayer { games: number; position: string; searched: boolean }

/** "all" = alle gesuchten Spieler im selben Team, "any" = mindestens einer spielt mit */
export type ScoutMode = "all" | "any";

export interface ScoutSummary {
  key: string;
  mode: ScoutMode;
  players: ScoutPlayer[];
  roster: RosterPlayer[];
  games: number;
  updated_at: string;
}

export interface ScoutReport {
  key: string;
  mode: ScoutMode;
  players: ScoutPlayer[];
  roster: RosterPlayer[];
  updated_at: string;
  filters: Filters;
  /** im Report ausgewählte Spieler und wie sie verknüpft werden */
  focus: string[];
  match: ScoutMode;
  report: Report;
  history: HistoryRow[];
  patches: string[];
  job: SyncJob | null;
}

/** Gespeicherte Ansicht: sichtbare Panels in dieser Reihenfolge */
export interface SavedView { id: number; name: string; panels: string[]; is_default: boolean }

// ------------------------------------------------------- Spieler-Einzelansicht
export type QueueKey = "solo" | "flex" | "tourney" | "scrim";

export interface PlayerFilters {
  queue: QueueKey[];
  patch: string;
  last: number;
  champion: number;
  role: string;
  exclude: string[];
}

export interface PlayerBucket { key: string; games: number; wins: number; winrate: number; kills: number; deaths: number; assists: number; kda: number }

export interface PlayerChampion {
  champion_id: number; games: number; wins: number; winrate: number; kills: number; deaths: number; assists: number;
  kda: number; cspm: number; dpm: number; positions: string[];
}

export interface GameParticipant {
  puuid: string; name: string; tag: string; team_id: number; position: string; champion_id: number;
  kills: number; deaths: number; assists: number;
}

export interface PlayerGame {
  match_id: string; date: string; queue: QueueKey; champion_id: number; position: string; win: boolean;
  kills: number; deaths: number; assists: number; cs: number; duration: number; gd15: number | null;
  csd15: number | null; patch: string; side: Side; level: number; gold: number; damage: number; vision: number;
  kp: number | null; items: number[]; spells: number[]; participants: GameParticipant[]; excluded: boolean;
}

export interface PlayerStatsReport {
  overview: {
    games: number; wins: number; winrate: number | null; kills: number | null; deaths: number | null; assists: number | null;
    kda: number | null; cspm: number | null; gpm: number | null; dpm: number | null; vspm: number | null; kp: number | null;
    first_blood: number | null; gd10: number | null; gd15: number | null; csd15: number | null; xpd15: number | null;
    timeline_games: number;
  };
  champions: PlayerChampion[];
  roles: PlayerBucket[];
  queues: PlayerBucket[];
  history: PlayerGame[];
  deaths: DeathEvent[];
  kills: KillEvent[];
}

export interface PlayerReportData {
  account: ScoutPlayer;
  filters: PlayerFilters;
  report: PlayerStatsReport;
  queue_counts: Partial<Record<QueueKey, number>>;
  patches: string[];
  champions: number[];
  roles: string[];
  last_fetch: string | null;
  job: SyncJob | null;
}

// ------------------------------------------------------------------ Gruppen
export type GroupEntryKind = "team" | "scout";

export interface GroupEntry {
  kind: GroupEntryKind;
  /** Team-ID bzw. Scouting-Schlüssel */
  ref: string;
  /** eigener Anzeigename */
  name: string;
}

export interface GroupEntryOut extends GroupEntry {
  title: string;
  tag: string;
  available: boolean;
}

export interface Group {
  key: string;
  name: string;
  entries: GroupEntryOut[];
  can_edit: boolean;
  updated_at: string;
}

export interface GroupSummary { key: string; name: string; teams: string[]; updated_at: string }

export type GroupFilters = Omit<Filters, "exclude">;

export interface GroupTeamStats {
  entry: GroupEntryOut;
  syncing: boolean;
  overview: Overview | null;
  monsters: MonsterStat[];
  players: PlayerReport[];
}

export interface GroupCompare {
  group: Group;
  filters: GroupFilters;
  patches: string[];
  teams: GroupTeamStats[];
}
