/** Turmpositionen von Summoner's Rift (Spielkoordinaten); identisch mit backend/primestats/fights.py. */
import type { Point } from "./navgrid";

const BLUE: Point[] = [
  [981, 10441], [1512, 6699], [1169, 4287],       // Top: außen, innen, Inhib
  [5846, 6396], [5048, 4812], [3651, 3696],       // Mid
  [10504, 1029], [6919, 1483], [4281, 1253],      // Bot
  [1748, 2270], [2177, 1807],                     // Nexus
];

export const TOWERS: { team: "blue" | "red"; pos: Point }[] = [
  ...BLUE.map((pos) => ({ team: "blue" as const, pos })),
  ...BLUE.map(([x, y]) => ({ team: "red" as const, pos: [14870 - x, 14980 - y] as Point })),
];
