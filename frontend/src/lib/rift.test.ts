import { describe, expect, it } from "vitest";

import { RIFT, WALLS, edges, interpolate, mirror, route } from "./rift";

type P = [number, number];
const cross = (o: P, a: P, b: P) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
const intersects = (a: P, b: P, c: P, d: P) =>
  cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0;
const inside = ([x, y]: P, poly: P[]) => {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
};

const named = (p: [number, number]) => Object.entries(RIFT.nodes).find(([, q]) => q[0] === p[0] && q[1] === p[1])?.[0];

describe("rift paths", () => {
  it("network is connected", () => {
    const seen = new Set(["fountain"]);
    const todo = ["fountain"];
    while (todo.length) for (const n of RIFT.adj[todo.pop()!] ?? []) if (!seen.has(n)) { seen.add(n); todo.push(n); }
    expect(seen.size).toBe(Object.keys(RIFT.nodes).length);
  });

  it("walks from wolves to raptors around the wall via mid, not straight through", () => {
    const names = route(RIFT.nodes.wolves, RIFT.nodes.raptors).map(named);
    expect(names[0]).toBe("wolves");
    expect(names.at(-1)).toBe("raptors");
    expect(names.some((n) => n === "westMid" || n?.startsWith("mid"))).toBe(true);
  });

  it("red side is mirrored", () => {
    expect(RIFT.nodes["~blue"]).toEqual(mirror(RIFT.nodes.blue));
    const blue = route(RIFT.nodes.gromp, RIFT.nodes.krugs).map(named);
    const red = route(RIFT.nodes["~gromp"], RIFT.nodes["~krugs"]).map(named);
    expect(red).toEqual(blue.map((n) => (n === "center" ? n : `~${n}`)));
  });

  it("no path crosses or starts inside a wall", () => {
    for (const [a, b] of edges()) {
      for (const wall of WALLS) {
        expect(inside(a, wall)).toBe(false);
        for (let i = 0; i < wall.length; i++) {
          expect(intersects(a, b, wall[i], wall[(i + 1) % wall.length])).toBe(false);
        }
      }
    }
  });

  it("keeps each minute position on the route", () => {
    const pts: [number, number][] = [[3800, 6400], [3900, 7900], [7700, 4100]];
    const { path, minuteIndex } = interpolate(pts);
    expect(minuteIndex.map((i) => path[i])).toEqual(pts);
    expect(path.length).toBeGreaterThan(pts.length);
  });
});
