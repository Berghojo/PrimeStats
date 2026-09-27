/**
 * Vereinfachtes Wegenetz von Summoner's Rift (Lanes, Jungle-Gänge, Fluss, Camps).
 *
 * Die Timeline liefert nur eine Position pro Minute. Damit die Route nicht quer durch Wände
 * gezeichnet wird, verbinden wir zwei Positionen über den kürzesten Weg in diesem Netz.
 * Das Netz ist von Hand angenähert (keine offiziellen Navigationsdaten) – es zeigt plausible
 * Laufwege, nicht die exakten.
 *
 * Koordinaten: Spielkoordinaten, Ursprung unten links (blaue Basis). Die rote Seite ist die
 * Punktspiegelung der blauen um die Kartenmitte; definiert wird nur die blaue Hälfte.
 */

export type Point = [number, number];

const MAX_X = 14870;
const MAX_Y = 14980;

/** Punktspiegelung: blaue Seite -> rote Seite */
export const mirror = ([x, y]: Point): Point => [MAX_X - x, MAX_Y - y];

/** Knoten der blauen Hälfte. "~name" bezeichnet den gespiegelten Knoten auf der roten Seite. */
const BLUE: Record<string, Point> = {
  // Basis und Lanes (Toplane bis zur Ecke, Botlane bis kurz vor die Ecke)
  fountain: [500, 500],
  nexus: [1700, 1700],
  top1: [1200, 3900],
  top2: [1250, 6600],
  top3: [1150, 9300],
  top4: [1400, 11800],
  topCorner: [2000, 13300],
  bot1: [4000, 1150],
  bot2: [6800, 1300],
  bot3: [9700, 1150],
  bot4: [11900, 1400],
  mid1: [3500, 3550],
  mid2: [5100, 5200],
  mid3: [6300, 6350],
  // Jungle Topside (Blue Buff, Gromp, Wolves)
  westGate: [2300, 5000],
  wolves: [3800, 6450],
  westMid: [5000, 6050],
  westJunction: [3100, 7200],
  westTop: [1900, 7100],
  blue: [3850, 7950],
  gromp: [2150, 8450],
  grompTop: [1500, 8600],
  pixel: [4750, 8850],
  triPath: [2600, 10000],
  // Fluss oben und Baron
  riverMouth: [2400, 11900],
  scuttle: [4350, 9750],
  riverMid: [5900, 8700],
  baron: [5000, 10450],
  // Jungle Botside (Raptors, Red Buff, Krugs)
  southGate: [4900, 2300],
  southJunction: [6600, 2600],
  krugs: [8400, 2650],
  krugsBot: [9300, 1800],
  red: [7800, 4050],
  raptors: [6950, 5450],
  raptorsRiver: [8200, 6000],
  redRiver: [8900, 4600],
  krugsRiver: [10600, 3100],
};

/** Kanten der blauen Hälfte; werden für die rote Seite gespiegelt. "center" ist die Kartenmitte. */
const BLUE_EDGES: [string, string][] = [
  ["fountain", "nexus"],
  ["nexus", "top1"], ["top1", "top2"], ["top2", "top3"], ["top3", "top4"], ["top4", "topCorner"],
  ["topCorner", "~bot4"],
  ["nexus", "bot1"], ["bot1", "bot2"], ["bot2", "bot3"], ["bot3", "bot4"], ["bot4", "~topCorner"],
  ["nexus", "mid1"], ["mid1", "mid2"], ["mid2", "mid3"], ["mid3", "center"],
  // Topside-Jungle
  ["top1", "westGate"], ["mid1", "westGate"], ["westGate", "wolves"], ["wolves", "westMid"], ["westMid", "mid2"],
  ["westMid", "mid3"], ["wolves", "westJunction"], ["westJunction", "westTop"], ["westTop", "top2"],
  ["westJunction", "blue"], ["blue", "gromp"], ["gromp", "grompTop"], ["grompTop", "top3"],
  ["blue", "pixel"], ["pixel", "scuttle"], ["pixel", "riverMid"], ["gromp", "triPath"], ["triPath", "riverMouth"],
  ["triPath", "top3"], ["triPath", "scuttle"],
  // Fluss oben
  ["riverMouth", "top4"], ["riverMouth", "topCorner"], ["riverMouth", "scuttle"], ["scuttle", "riverMid"],
  ["riverMid", "center"], ["scuttle", "baron"], ["riverMid", "baron"],
  // Botside-Jungle, Eingänge in den unteren Fluss (= gespiegelter oberer Fluss)
  ["bot1", "southGate"], ["mid1", "southGate"], ["southGate", "southJunction"], ["southJunction", "krugs"],
  ["southJunction", "red"], ["red", "krugs"], ["krugs", "krugsBot"], ["krugsBot", "bot3"],
  ["red", "raptors"], ["raptors", "mid3"], ["raptors", "raptorsRiver"], ["raptorsRiver", "~riverMid"],
  ["red", "redRiver"], ["redRiver", "~baron"], ["redRiver", "~scuttle"],
  ["krugs", "krugsRiver"], ["krugsRiver", "~riverMouth"], ["krugsRiver", "~scuttle"],
];

const flip = (name: string) => (name === "center" ? name : name.startsWith("~") ? name.slice(1) : `~${name}`);

function build() {
  const nodes: Record<string, Point> = { center: [MAX_X / 2, MAX_Y / 2] };
  for (const [name, p] of Object.entries(BLUE)) {
    nodes[name] = p;
    nodes[`~${name}`] = mirror(p);
  }
  const adj: Record<string, Set<string>> = {};
  const link = (a: string, b: string) => {
    if (!nodes[a] || !nodes[b]) throw new Error(`Unbekannter Knoten: ${nodes[a] ? b : a}`);
    (adj[a] ??= new Set()).add(b);
    (adj[b] ??= new Set()).add(a);
  };
  for (const [a, b] of BLUE_EDGES) {
    link(a, b);
    link(flip(a), flip(b));
  }
  return { nodes, adj };
}

export const RIFT = build();

const dist = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** Alle Kanten (für die Anzeige des Wegenetzes). */
export function edges(): [Point, Point][] {
  const out: [Point, Point][] = [];
  for (const [a, set] of Object.entries(RIFT.adj)) {
    for (const b of set) if (a < b) out.push([RIFT.nodes[a], RIFT.nodes[b]]);
  }
  return out;
}

function nearest(p: Point): string {
  let best = "", d = Infinity;
  for (const [name, q] of Object.entries(RIFT.nodes)) {
    const dd = dist(p, q);
    if (dd < d) [best, d] = [name, dd];
  }
  return best;
}

/** Dijkstra im Wegenetz; liefert die Knotennamen von a nach b. */
function shortest(a: string, b: string): string[] {
  const d: Record<string, number> = { [a]: 0 };
  const prev: Record<string, string> = {};
  const open = new Set([a]);
  const done = new Set<string>();
  while (open.size) {
    let cur = "";
    for (const n of open) if (!cur || d[n] < d[cur]) cur = n;
    open.delete(cur);
    if (cur === b) break;
    done.add(cur);
    for (const next of RIFT.adj[cur] ?? []) {
      if (done.has(next)) continue;
      const nd = d[cur] + dist(RIFT.nodes[cur], RIFT.nodes[next]);
      if (nd < (d[next] ?? Infinity)) {
        d[next] = nd;
        prev[next] = cur;
        open.add(next);
      }
    }
  }
  const path = [b];
  while (path[0] !== a) {
    const p = prev[path[0]];
    if (p === undefined) return [a, b];
    path.unshift(p);
  }
  return path;
}

/** Unter dieser Entfernung wird direkt verbunden (gleiche Stelle / gleiches Camp). */
const DIRECT = 900;

/**
 * Realistischer Weg von a nach b: über die nächstgelegenen Knoten des Wegenetzes und dort den
 * kürzesten Weg. Knoten am Anfang/Ende, die nur einen Umweg bedeuten würden, fallen weg.
 */
export function route(a: Point, b: Point): Point[] {
  if (dist(a, b) < DIRECT) return [a, b];
  const names = shortest(nearest(a), nearest(b));
  const pts = names.map((n) => RIFT.nodes[n]);
  // nicht erst zum Knoten zurücklaufen, wenn der nächste schon näher liegt
  while (pts.length > 1 && dist(a, pts[1]) <= dist(a, pts[0]) + dist(pts[0], pts[1]) * 0.25) pts.shift();
  while (pts.length > 1 && dist(b, pts[pts.length - 2]) <= dist(b, pts[pts.length - 1]) + dist(pts[pts.length - 1], pts[pts.length - 2]) * 0.25) pts.pop();
  return [a, ...pts, b];
}

/** Ganze Route aus Minutenpositionen; liefert zusätzlich, bei welchem Punkt jede Minute liegt. */
export function interpolate(points: Point[]): { path: Point[]; minuteIndex: number[] } {
  if (!points.length) return { path: [], minuteIndex: [] };
  const path: Point[] = [points[0]];
  const minuteIndex = [0];
  for (let i = 1; i < points.length; i++) {
    const seg = route(points[i - 1], points[i]);
    path.push(...seg.slice(1));
    minuteIndex.push(path.length - 1);
  }
  return { path, minuteIndex };
}
