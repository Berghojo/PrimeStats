import { describe, expect, it } from "vitest";

import { parseTeams } from "./teamImport";

describe("parseTeams", () => {
  it("reads one team per line", () => {
    expect(parseTeams("Nordlicht: NLE Polaris#EUW, NLE Kompass#EUW\nBerserker: BSK Skalde#EUW; BSK Drakkar #EUW")).toEqual([
      { name: "Nordlicht", riotIds: ["NLE Polaris#EUW", "NLE Kompass#EUW"], invalid: [] },
      { name: "Berserker", riotIds: ["BSK Skalde#EUW", "BSK Drakkar#EUW"], invalid: [] },
    ]);
  });

  it("reads blocks with the name on the first line", () => {
    expect(parseTeams("Alpenrausch\nALP Enzian#EUW\nALP Firn#EUW\n\nHafenkante\nHFK Kogge#EUW")).toEqual([
      { name: "Alpenrausch", riotIds: ["ALP Enzian#EUW", "ALP Firn#EUW"], invalid: [] },
      { name: "Hafenkante", riotIds: ["HFK Kogge#EUW"], invalid: [] },
    ]);
  });

  it("allows unnamed teams, drops duplicates, caps at five and reports invalid ids", () => {
    const [team] = parseTeams("a#1, A#1, b#1, c#1, d#1, e#1, f#1, kein-tag");
    expect(team.name).toBe("");
    expect(team.riotIds).toEqual(["a#1", "b#1", "c#1", "d#1", "e#1"]);
    expect(team.invalid).toEqual(["kein-tag"]);
  });

  it("a name line directly followed by a new name starts a new team", () => {
    expect(parseTeams("Team A\nx#1\nTeam B\ny#1").map((t) => [t.name, t.riotIds])).toEqual([
      ["Team A", ["x#1"]], ["Team B", ["y#1"]],
    ]);
  });
});
