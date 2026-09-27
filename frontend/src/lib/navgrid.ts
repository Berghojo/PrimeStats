/**
 * Begehbare Fläche von Summoner's Rift als Raster (aus einem Kartenbild erzeugt, siehe
 * scripts/build_navgrid.py) und kürzeste Wege darauf (A*, 8 Nachbarn, danach geglättet).
 *
 * Koordinaten: Spielkoordinaten, Ursprung unten links (blaue Basis).
 */
import { GRID_BITS, GRID_SIZE } from "./navgridData";

export type Point = [number, number];

export const MAX_X = 14870;
export const MAX_Y = 14980;
const N = GRID_SIZE;
const CW = MAX_X / N;
const CH = MAX_Y / N;

function decode(): Uint8Array {
  const bin = atob(GRID_BITS);
  const cells = new Uint8Array(N * N);
  for (let k = 0; k < N * N; k++) cells[k] = (bin.charCodeAt(k >> 3) >> (7 - (k & 7))) & 1;
  return cells;
}

/** 1 = begehbar; Index = Zeile * N + Spalte, Zeile 0 oben */
export const WALKABLE = decode();

const col = (x: number) => Math.min(N - 1, Math.max(0, Math.floor(x / CW)));
const row = (y: number) => Math.min(N - 1, Math.max(0, Math.floor((MAX_Y - y) / CH)));
const center = (k: number): Point => [((k % N) + 0.5) * CW, MAX_Y - (Math.floor(k / N) + 0.5) * CH];

export const isWalkable = ([x, y]: Point) => WALKABLE[row(y) * N + col(x)] === 1;

/** Nächste begehbare Zelle (Breitensuche) – Positionen aus der Timeline liegen manchmal in Wänden. */
function nearestWalkable(k: number): number {
  if (WALKABLE[k]) return k;
  const seen = new Uint8Array(N * N);
  const queue = [k];
  seen[k] = 1;
  for (let q = 0; q < queue.length; q++) {
    const cur = queue[q];
    if (WALKABLE[cur]) return cur;
    const r = Math.floor(cur / N), c = cur % N;
    for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const rr = r + dr, cc = c + dc;
      if (rr >= 0 && rr < N && cc >= 0 && cc < N && !seen[rr * N + cc]) {
        seen[rr * N + cc] = 1;
        queue.push(rr * N + cc);
      }
    }
  }
  return k;
}

/** Freie Sicht zwischen zwei Zellen (keine Wandzelle auf der Linie)? */
function lineOfSight(a: number, b: number): boolean {
  let r0 = Math.floor(a / N), c0 = a % N;
  const r1 = Math.floor(b / N), c1 = b % N;
  const dr = Math.abs(r1 - r0), dc = Math.abs(c1 - c0);
  const sr = r0 < r1 ? 1 : -1, sc = c0 < c1 ? 1 : -1;
  let err = dc - dr;
  for (;;) {
    if (!WALKABLE[r0 * N + c0]) return false;
    if (r0 === r1 && c0 === c1) return true;
    const e2 = 2 * err;
    // Diagonalschritte nicht zwischen zwei Wandecken hindurch
    if (e2 > -dr && e2 < dc && (!WALKABLE[r0 * N + c0 + sc] || !WALKABLE[(r0 + sr) * N + c0])) return false;
    if (e2 > -dr) { err -= dr; c0 += sc; }
    if (e2 < dc) { err += dc; r0 += sr; }
  }
}

/** Min-Heap über (Priorität, Zelle) */
class Heap {
  private items: [number, number][] = [];
  get size() { return this.items.length; }
  push(item: [number, number]) {
    const a = this.items;
    a.push(item);
    for (let i = a.length - 1; i > 0;) {
      const p = (i - 1) >> 1;
      if (a[p][0] <= a[i][0]) break;
      [a[p], a[i]] = [a[i], a[p]];
      i = p;
    }
  }
  pop(): [number, number] {
    const a = this.items;
    const top = a[0];
    const last = a.pop()!;
    if (a.length) {
      a[0] = last;
      for (let i = 0; ;) {
        const l = 2 * i + 1, r = l + 1;
        let m = i;
        if (l < a.length && a[l][0] < a[m][0]) m = l;
        if (r < a.length && a[r][0] < a[m][0]) m = r;
        if (m === i) break;
        [a[m], a[i]] = [a[i], a[m]];
        i = m;
      }
    }
    return top;
  }
}

const DIRS: [number, number, number][] = [
  [0, 1, 1], [0, -1, 1], [1, 0, 1], [-1, 0, 1],
  [1, 1, Math.SQRT2], [1, -1, Math.SQRT2], [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2],
];

/** A* von Zelle a nach b; liefert die Zellen des Weges (oder null, wenn unerreichbar). */
function astar(a: number, b: number): number[] | null {
  const g = new Float64Array(N * N).fill(Infinity);
  const prev = new Int32Array(N * N).fill(-1);
  const closed = new Uint8Array(N * N);
  const br = Math.floor(b / N), bc = b % N;
  const h = (k: number) => {
    const dr = Math.abs(Math.floor(k / N) - br), dc = Math.abs((k % N) - bc);
    return Math.max(dr, dc) + (Math.SQRT2 - 1) * Math.min(dr, dc);
  };
  const open = new Heap();
  g[a] = 0;
  open.push([h(a), a]);
  while (open.size) {
    const [, cur] = open.pop();
    if (cur === b) break;
    if (closed[cur]) continue;
    closed[cur] = 1;
    const r = Math.floor(cur / N), c = cur % N;
    for (const [dr, dc, cost] of DIRS) {
      const rr = r + dr, cc = c + dc;
      if (rr < 0 || rr >= N || cc < 0 || cc >= N) continue;
      const next = rr * N + cc;
      if (!WALKABLE[next] || closed[next]) continue;
      if (dr && dc && (!WALKABLE[r * N + cc] || !WALKABLE[rr * N + c])) continue; // keine Ecken schneiden
      const ng = g[cur] + cost;
      if (ng < g[next]) {
        g[next] = ng;
        prev[next] = cur;
        open.push([ng + h(next), next]);
      }
    }
  }
  if (a !== b && prev[b] === -1) return null;
  const path = [b];
  while (path[0] !== a) path.unshift(prev[path[0]]);
  return path;
}

/** Wegpunkte ausdünnen: jeweils den weitesten Punkt mit freier Sicht nehmen. */
function smooth(cells: number[]): number[] {
  const out = [cells[0]];
  let i = 0;
  while (i < cells.length - 1) {
    let j = cells.length - 1;
    while (j > i + 1 && !lineOfSight(cells[i], cells[j])) j--;
    out.push(cells[j]);
    i = j;
  }
  return out;
}

const cache = new Map<string, Point[]>();

/** Kürzester begehbarer Weg von a nach b (Start- und Endpunkt bleiben erhalten). */
export function route(a: Point, b: Point): Point[] {
  const key = `${Math.round(a[0])},${Math.round(a[1])}|${Math.round(b[0])},${Math.round(b[1])}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const ka = nearestWalkable(row(a[1]) * N + col(a[0]));
  const kb = nearestWalkable(row(b[1]) * N + col(b[0]));
  let result: Point[];
  if (ka === kb || lineOfSight(ka, kb)) result = [a, b];
  else {
    const cells = astar(ka, kb);
    result = cells ? [a, ...smooth(cells).slice(1, -1).map(center), b] : [a, b];
  }
  if (cache.size > 5000) cache.clear();
  cache.set(key, result);
  return result;
}

/** Ganze Route aus Minutenpositionen; minuteIndex = Index jeder Minutenposition im Weg. */
export function interpolate(points: Point[]): { path: Point[]; minuteIndex: number[] } {
  if (!points.length) return { path: [], minuteIndex: [] };
  const path: Point[] = [points[0]];
  const minuteIndex = [0];
  for (let i = 1; i < points.length; i++) {
    path.push(...route(points[i - 1], points[i]).slice(1));
    minuteIndex.push(path.length - 1);
  }
  return { path, minuteIndex };
}

/** Wandflächen als Rechtecke (je Zeile zusammengefasste Zellen) in Spielkoordinaten: [x0, y0, x1, y1]. */
export function wallRects(): [number, number, number, number][] {
  const out: [number, number, number, number][] = [];
  for (let r = 0; r < N; r++) {
    let start = -1;
    for (let c = 0; c <= N; c++) {
      const wall = c < N && !WALKABLE[r * N + c];
      if (wall && start < 0) start = c;
      if (!wall && start >= 0) {
        out.push([start * CW, MAX_Y - (r + 1) * CH, c * CW, MAX_Y - r * CH]);
        start = -1;
      }
    }
  }
  return out;
}
