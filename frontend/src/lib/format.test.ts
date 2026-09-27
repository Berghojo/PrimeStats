import { describe, expect, it } from "vitest";

import { buildQuery } from "../api/client";
import { duration, num, pct, signed, splitRiotId, tone } from "./format";

describe("format", () => {
  it("formatiert Zahlen deutsch", () => {
    expect(num(1234.56, 1)).toBe("1.234,6");
    expect(num(null)).toBe("–");
    expect(pct(0.537)).toBe("54%");
    expect(signed(1135)).toBe("+1.135");
    expect(signed(-3.5, 1)).toBe("-3,5");
    expect(duration(1906)).toBe("31:46");
  });

  it("bewertet Werte relativ zu einem neutralen Punkt", () => {
    expect(tone(0.6, 0.5)).toBe("pos");
    expect(tone(-1)).toBe("neg");
    expect(tone(0)).toBe("");
    expect(tone(null)).toBe("");
  });

  it("zerlegt Riot-IDs", () => {
    expect(splitRiotId("Herr Grey#6781")).toEqual(["Herr Grey", "6781"]);
    expect(splitRiotId(" a#b#EUW ")).toEqual(["a#b", "EUW"]);
    expect(splitRiotId("NoTag")).toBeNull();
    expect(splitRiotId("#EUW")).toBeNull();
  });

  it("baut Query-Strings mit Listen", () => {
    expect(buildQuery({ m: ["A", "B"], team: 3, focus: [], x: "" })).toBe("?m=A&m=B&team=3");
    expect(buildQuery({})).toBe("");
  });
});
