import { describe, expect, it } from "vitest";

import { CAMPS, reconstruct } from "./jungleRoute";

const camp = (key: string) => CAMPS.find((c) => c.key === key)!.pos;

describe("jungle route from CS", () => {
  it("visits as many camps as the CS gain allows, in the cheapest order", () => {
    // Minute 1 am Red Buff, Minute 2 bei den Raptors, dazwischen 8 CS = 2 Camps
    const points = [null, camp("b-red"), camp("b-raptors")];
    const { clears, path } = reconstruct(points, [0, 0, 8], 2);
    expect(clears.map((c) => c.camp.key)).toEqual(["b-red", "b-raptors"]);
    // nach CS-Verlauf läge das erste Camp bei 1:30 – frühestens 15 s nach dem Spawn (1:30) geräumt
    expect(clears.map((c) => c.t)).toEqual([105, 120]);
    expect(path[0]).toEqual(camp("b-red"));
    expect(path.at(-1)).toEqual(camp("b-raptors"));
  });

  it("no camps without CS gain and no camps before they spawn", () => {
    expect(reconstruct([null, camp("b-red"), camp("b-krugs")], [0, 0, 0], 2).clears).toEqual([]);
    // Scuttle spawnt erst 3:30 – vorher wird sie nicht gewählt
    const early = reconstruct([null, camp("b-blue"), camp("scuttle-top")], [0, 0, 4], 2);
    expect(early.clears.map((c) => c.camp.key)).not.toContain("scuttle-top");
  });

  it("a cleared camp is not taken again before it respawns", () => {
    const pts = [null, camp("b-red"), camp("b-red"), camp("b-red")];
    const { clears } = reconstruct(pts, [0, 0, 4, 8], 3);
    expect(clears.filter((c) => c.camp.key === "b-red")).toHaveLength(1);
    expect(clears).toHaveLength(2);
  });
});

describe("invades", () => {
  it("prefers own camps; enemy camps only when they are clearly on the way", () => {
    // blauer Jungler zwischen Blue Buff und Wolves, 1 Camp: eigener Gromp statt eines gegnerischen Camps
    const own = reconstruct([null, camp("b-blue"), camp("b-wolves")], [0, 0, 4], 2, 1, false, "blue");
    expect(own.clears[0].camp.side).toBe("blue");
    // steht er vorher und nachher im gegnerischen Jungle, räumt er dort
    const invade = reconstruct([null, camp("r-raptors"), camp("r-red")], [0, 0, 8], 2, 1, false, "blue");
    expect(invade.clears.map((c) => c.camp.key)).toEqual(["r-raptors", "r-red"]);
  });
});

describe("performance", () => {
  it("reconstructs 40 games x 15 minutes quickly", () => {
    const pts = [null, camp("b-red"), camp("b-raptors"), camp("b-wolves"), camp("b-gromp"), camp("scuttle-top"),
      camp("b-krugs"), camp("r-raptors"), camp("b-blue"), camp("b-red"), camp("b-raptors"), camp("b-wolves"),
      camp("b-gromp"), camp("b-blue"), camp("b-krugs"), camp("b-red")];
    const cs = pts.map((_, m) => Math.max(0, m - 1) * 8);
    reconstruct(pts, cs, 15);  // Distanzfelder aufwärmen
    const start = performance.now();
    for (let g = 0; g < 40; g++) {
      const jitter = pts.map((p) => (p ? [p[0] + g * 7, p[1] - g * 5] as [number, number] : null));
      const r = reconstruct(jitter, cs, 15);
      expect(r.clears.length).toBeGreaterThan(10);
    }
    expect(performance.now() - start).toBeLessThan(3000);
  });
});

describe("first clear timing", async () => {
  const { clearTime, timeToCs } = await import("./jungleRoute");
  it("interpolates between minute frames", () => {
    // 3:00 -> 8 CS, 4:00 -> 20 CS: 16 CS (4 Camps) bei 3:40
    const cs = [0, 0, 4, 8, 20, 28];
    expect(timeToCs(cs, 16)).toBe(220);
    expect(clearTime(cs, 6)).toBe(4 * 60 + 30);   // 24 CS zwischen 20 und 28
    expect(clearTime(cs, 10)).toBeNull();
    expect(timeToCs(cs, 0)).toBe(0);
  });
});
