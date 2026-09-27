import { splitRiotId } from "./format";

export interface ImportedTeam {
  name: string;
  riotIds: string[];
  /** Einträge, die keine Riot-ID sind */
  invalid: string[];
}

const MAX_PLAYERS = 5;

/**
 * Liest mehrere Teams aus eingefügtem Text. Zwei Schreibweisen, auch gemischt:
 *
 *   Teamname: Spieler#EUW, Spieler2#EUW, …        (ein Team pro Zeile)
 *
 *   Teamname                                       (Block: erste Zeile ohne „#“ = Name,
 *   Spieler#EUW                                     danach eine Riot-ID pro Zeile,
 *   Spieler2#EUW                                    Blöcke durch Leerzeile getrennt)
 */
export function parseTeams(text: string): ImportedTeam[] {
  const teams: ImportedTeam[] = [];
  let block: ImportedTeam | null = null;
  const push = (t: ImportedTeam | null) => {
    if (t && (t.riotIds.length || t.invalid.length)) teams.push(t);
  };
  const addIds = (team: ImportedTeam, raw: string) => {
    for (const part of raw.split(/[,;\t|]/).map((s) => s.trim()).filter(Boolean)) {
      const id = splitRiotId(part);
      if (!id) team.invalid.push(part);
      else if (team.riotIds.length < MAX_PLAYERS) {
        const riotId = `${id[0]}#${id[1]}`;
        if (!team.riotIds.some((r) => r.toLowerCase() === riotId.toLowerCase())) team.riotIds.push(riotId);
      }
    }
  };
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      push(block);
      block = null;
      continue;
    }
    const colon = line.indexOf(":");
    const hash = line.indexOf("#");
    if (colon > 0 && (hash < 0 || colon < hash)) {
      // „Teamname: IDs“ – eigenes Team in einer Zeile
      push(block);
      block = null;
      const team = { name: line.slice(0, colon).trim(), riotIds: [], invalid: [] };
      addIds(team, line.slice(colon + 1));
      push(team);
    } else if (hash < 0) {
      // Zeile ohne Riot-ID beginnt einen neuen Block (Teamname)
      push(block);
      block = { name: line, riotIds: [], invalid: [] };
    } else {
      block ??= { name: "", riotIds: [], invalid: [] };
      addIds(block, line);
    }
  }
  push(block);
  return teams;
}
