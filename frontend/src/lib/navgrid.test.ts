import { describe, expect, it } from "vitest";

import { MAX_X, MAX_Y, type Point, WALKABLE, interpolate, isWalkable, route, wallRects } from "./navgrid";

const mirror = ([x, y]: Point): Point => [MAX_X - x, MAX_Y - y];
const length = (pts: Point[]) => pts.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]), 0);

/** Prüft jeden Abschnitt fein abgetastet auf Wandzellen */
function crossesWall(path: Point[]): boolean {
  for (let i = 1; i < path.length; i++) {
    const [a, b] = [path[i - 1], path[i]];
    const steps = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 25);
    for (let s = 1; s < steps; s++) {
      const t = s / steps;
      if (!isWalkable([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])) return true;
    }
  }
  return false;
}

const BLUE_FOUNTAIN: Point = [1000, 1100];
const RED_FOUNTAIN = mirror(BLUE_FOUNTAIN);
const CAMPS: Record<string, Point> = {
  wolves: [3800, 6500], raptors: [6823, 5508], red: [7765, 4020], krugs: [8482, 2760], blue: [3821, 8101], gromp: [2090, 8428],
};

describe("navgrid", () => {
  it("lanes, bases and camps are walkable, the map border is not", () => {
    for (const p of [BLUE_FOUNTAIN, RED_FOUNTAIN, [1250, 7000], [7000, 1250], [7435, 7490]] as Point[]) {
      expect(isWalkable(p)).toBe(true);
    }
    expect(isWalkable([100, 7000])).toBe(false);
    expect(WALKABLE.reduce((a, b) => a + b, 0)).toBeGreaterThan(10000);
    expect(wallRects().length).toBeGreaterThan(100);
  });

  it("finds routes that never cross a wall", () => {
    const names = Object.keys(CAMPS);
    for (const a of names) {
      for (const b of names) {
        if (a === b) continue;
        const path = route(CAMPS[a], CAMPS[b]);
        expect(crossesWall(path.slice(1, -1))).toBe(false);
      }
    }
    const base = route(BLUE_FOUNTAIN, RED_FOUNTAIN);
    expect(crossesWall(base)).toBe(false);
  });

  it("walks around walls: route is longer than the straight line but not absurdly", () => {
    const path = route(CAMPS.wolves, CAMPS.raptors);
    const straight = Math.hypot(CAMPS.raptors[0] - CAMPS.wolves[0], CAMPS.raptors[1] - CAMPS.wolves[1]);
    expect(length(path)).toBeGreaterThanOrEqual(straight);
    expect(length(path)).toBeLessThan(straight * 2.2);
  });

  it("keeps each minute position on the route", () => {
    const pts: Point[] = [CAMPS.red, CAMPS.krugs, CAMPS.raptors];
    const { path, minuteIndex } = interpolate(pts);
    expect(minuteIndex.map((i) => path[i])).toEqual(pts);
  });
});

describe("distanceField", () => {
  it("reaches every walkable cell and matches the route length roughly", async () => {
    const { distanceField, cellOf } = await import("./navgrid");
    const f = distanceField([3800, 6500]);
    let reached = 0;
    for (let k = 0; k < f.length; k++) if (WALKABLE[k] && Number.isFinite(f[k])) reached++;
    expect(reached).toBe(WALKABLE.reduce((a, b) => a + b, 0));
    const d = f[cellOf([6823, 5508])];
    const r = length(route([3800, 6500], [6823, 5508]));
    expect(Math.abs(d - r) / r).toBeLessThan(0.25);
  });
});
