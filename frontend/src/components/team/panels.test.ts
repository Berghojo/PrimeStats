import { describe, expect, it } from "vitest";

import { cleanPanels, defaultPanels } from "./panels";

describe("panels", () => {
  it("jungle only in the team view, timeline only when scouting", () => {
    expect(defaultPanels("team")).toContain("jungle");
    expect(defaultPanels("team")).not.toContain("timeline");
    expect(defaultPanels("scout")).toContain("timeline");
    expect(defaultPanels("scout")).not.toContain("jungle");
  });

  it("keeps order, drops unknown and duplicate keys", () => {
    expect(cleanPanels(["games", "jungle", "evil", "overview", "games"], "scout")).toEqual(["games", "overview"]);
  });
});
