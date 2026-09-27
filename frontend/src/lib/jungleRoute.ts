/**
 * Rekonstruiert die Jungle-Route aus Minutenpositionen und Jungle-CS.
 *
 * Aus dem CS-Zuwachs zwischen zwei Minuten ergibt sich, wie viele Camps geräumt wurden. Gewählt wird die
 * Reihenfolge verfügbarer Camps, die zwischen den beiden Positionen den kürzesten begehbaren Weg ergibt.
 * Verfügbar ist ein Camp, wenn es schon gespawnt ist und nicht kurz vorher geräumt wurde.
 */
import { type Point, MAX_X, MAX_Y, cellOf, distanceField, route, traceField } from "./navgrid";

export interface Camp {
  key: string;
  name: string;
  /** "own"/"enemy" aus Sicht der blauen Seite; Scuttle gehört niemandem */
  side: "blue" | "red" | "river";
  pos: Point;
  /** erster Spawn und Respawn in Sekunden */
  spawn: number;
  respawn: number;
}

/** Aufschlag (Spieleinheiten) für gegnerische Camps: Invades nur, wenn sie klar auf dem Weg liegen */
export const INVADE_PENALTY = 2500;

/** Mindestdauer eines Camps nach dem Spawn bzw. zwischen zwei Camps (Sekunden) */
const MIN_CLEAR = 15;
const MIN_GAP = 10;

/** CS je geräumtem Camp (Annahme: jedes Camp zählt gleich viel) */
export const CS_PER_CAMP = 4;

const mirror = ([x, y]: Point): Point => [MAX_X - x, MAX_Y - y];

const BLUE_CAMPS: [string, string, Point, number, number][] = [
  ["blue", "Blue Buff", [3821, 8101], 90, 300],
  ["gromp", "Gromp", [2090, 8428], 90, 135],
  ["wolves", "Wolves", [3800, 6500], 90, 135],
  ["raptors", "Raptors", [6823, 5508], 90, 135],
  ["red", "Red Buff", [7765, 4020], 90, 300],
  ["krugs", "Krugs", [8482, 2760], 90, 135],
];

export const CAMPS: Camp[] = [
  ...BLUE_CAMPS.map(([key, name, pos, spawn, respawn]) => ({ key: `b-${key}`, name, side: "blue" as const, pos, spawn, respawn })),
  ...BLUE_CAMPS.map(([key, name, pos, spawn, respawn]) => ({ key: `r-${key}`, name, side: "red" as const, pos: mirror(pos), spawn, respawn })),
  { key: "scuttle-top", name: "Scuttle (oben)", side: "river", pos: [4400, 9700], spawn: 210, respawn: 150 },
  { key: "scuttle-bot", name: "Scuttle (unten)", side: "river", pos: mirror([4400, 9700]), spawn: 210, respawn: 150 },
];

let fields: Float64Array[] | null = null;
/** Laufdistanzen von jedem Camp zu allen Zellen (einmalig berechnet) */
function campFields(): Float64Array[] {
  fields ??= CAMPS.map((c) => distanceField(c.pos));
  return fields;
}

export interface Clear {
  camp: Camp;
  /** geschätzte Sekunde, in der das Camp geräumt wurde */
  t: number;
  /** Reihenfolge im Spiel (1 = erstes Camp) */
  order: number;
}

export interface JungleRoute {
  path: Point[];
  minuteIndex: number[];
  clears: Clear[];
}

/**
 * Zeitpunkt (Sekunden), zu dem die Jungle-CS erstmals ``target`` erreichen – linear interpoliert zwischen
 * den Minutenwerten der Timeline. null, wenn der Wert im Zeitraum nicht erreicht wird.
 */
export function timeToCs(jungleCs: number[], target: number): number | null {
  for (let m = 0; m < jungleCs.length - 1; m++) {
    const a = jungleCs[m], b = jungleCs[m + 1];
    if (a >= target) return m * 60;
    if (b >= target && b > a) return Math.round(m * 60 + ((target - a) / (b - a)) * 60);
  }
  return null;
}

/** Dauer bis zu n geräumten Camps (z.B. 6 = Full Clear) */
export const clearTime = (jungleCs: number[], camps: number) => timeToCs(jungleCs, camps * CS_PER_CAMP);

/** Camp-Reihenfolge mit kürzestem Weg a -> c1 -> … -> ck -> b (Brute Force, k ist klein) */
function bestOrder(a: Point, b: Point, candidates: number[], k: number, side?: "blue" | "red"): number[] {
  const f = campFields();
  const extra = (i: number) => (side && CAMPS[i].side !== "river" && CAMPS[i].side !== side ? INVADE_PENALTY : 0);
  const ca = cellOf(a), cb = cellOf(b);
  const between = (i: number, j: number) => f[i][cellOf(CAMPS[j].pos)];
  let best: number[] = [], bestCost = Infinity;
  const pick = (chosen: number[], cost: number) => {
    if (cost >= bestCost) return;
    if (chosen.length === k) {
      const total = cost + f[chosen[chosen.length - 1]][cb];
      if (total < bestCost) [best, bestCost] = [[...chosen], total];
      return;
    }
    for (const c of candidates) {
      if (chosen.includes(c)) continue;
      const step = (chosen.length ? between(chosen[chosen.length - 1], c) : f[c][ca]) + extra(c);
      if (!Number.isFinite(step)) continue;
      chosen.push(c);
      pick(chosen, cost + step);
      chosen.pop();
    }
  };
  pick([], 0);
  return best;
}

/**
 * @param points Position je Minute (Index = Minute, 0 = Spielstart); null = unbekannt
 * @param jungleCs Jungle-CS je Minute (gleiche Indizes)
 * @param fromMinute erste Minute der Route (Standard 1 – der Weg aus dem Brunnen wird weggelassen)
 * @param withPath false = nur die Camps bestimmen (schneller, z.B. für Statistiken)
 * @param side Seite des Junglers – gegnerische Camps werden nur gewählt, wenn sie klar auf dem Weg liegen
 */
export function reconstruct(points: (Point | null)[], jungleCs: number[], upTo: number, fromMinute = 1,
  withPath = true, side?: "blue" | "red"): JungleRoute {
  const path: Point[] = [];
  const minuteIndex: number[] = [];
  const clears: Clear[] = [];
  const lastClear = new Map<number, number>();
  let prev: { p: Point; m: number } | null = null;
  for (let m = fromMinute; m <= Math.min(upTo, points.length - 1); m++) {
    const p = points[m];
    if (!p) continue;
    if (!prev) {
      path.push(p);
      minuteIndex[m] = 0;
      prev = { p, m };
      continue;
    }
    const t0 = prev.m * 60, t1 = m * 60;
    const gained = (jungleCs[m] ?? 0) - (jungleCs[prev.m] ?? 0);
    const k = Math.max(0, Math.min(4, Math.round(gained / CS_PER_CAMP)));
    const available = CAMPS.map((_, i) => i).filter((i) => {
      const c = CAMPS[i];
      const last = lastClear.get(i);
      // spätestens am Ende des Abschnitts gespawnt bzw. wieder da
      return c.spawn < t1 && (last === undefined || last + c.respawn < t1);
    });
    const order = k ? bestOrder(prev.p, p, available, Math.min(k, available.length), side) : [];
    order.forEach((i, n) => {
      // Zeitpunkt nach CS-Verlauf: das n-te Camp ist geräumt, wenn die CS um (n+1)·4 gestiegen sind
      const share = gained > 0 ? Math.min(1, ((n + 1) * CS_PER_CAMP) / gained) : (n + 1) / (order.length + 1);
      const previous = clears.length ? clears[clears.length - 1].t + MIN_GAP : 0;
      const t = Math.min(t1, Math.max(Math.round(t0 + share * (t1 - t0)), CAMPS[i].spawn + MIN_CLEAR, previous));
      lastClear.set(i, t);
      clears.push({ camp: CAMPS[i], t, order: clears.length + 1 });
    });
    if (withPath) {
      if (!order.length) path.push(...route(prev.p, p).slice(1));
      else {
        const f = campFields();
        // zum ersten Camp, von Camp zu Camp (je dem Feld des Ziel-Camps folgen), vom letzten Camp zur Position
        path.push(...traceField(f[order[0]], prev.p, CAMPS[order[0]].pos).slice(1));
        for (let n = 1; n < order.length; n++) {
          path.push(...traceField(f[order[n]], CAMPS[order[n - 1]].pos, CAMPS[order[n]].pos).slice(1));
        }
        const lastCamp = order[order.length - 1];
        path.push(...traceField(f[lastCamp], p, CAMPS[lastCamp].pos).reverse().slice(1));
      }
    } else path.push(p);
    minuteIndex[m] = path.length - 1;
    prev = { p, m };
  }
  return { path, minuteIndex, clears };
}
