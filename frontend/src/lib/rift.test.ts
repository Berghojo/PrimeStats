import { describe, expect, it } from "vitest";

import { RIFT, interpolate, mirror, route } from "./rift";

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

  it("keeps each minute position on the route", () => {
    const pts: [number, number][] = [[3800, 6400], [3900, 7900], [7700, 4100]];
    const { path, minuteIndex } = interpolate(pts);
    expect(minuteIndex.map((i) => path[i])).toEqual(pts);
    expect(path.length).toBeGreaterThan(pts.length);
  });
});
