import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChampionRow } from "../../api/types";
import { renderWithProviders } from "../../test/utils";
import { ChampionTable } from "./ChampionTable";

const row = (id: number, picks: number, position: string, extra: Partial<ChampionRow> = {}): ChampionRow => ({
  champion_id: id, picks, wins: Math.floor(picks / 2), winrate: picks ? Math.floor(picks / 2) / picks : null,
  kda: picks ? 3 : null, kills: 1, deaths: 1, assists: 1, cspm: 7, dpm: 500, position,
  positions: picks ? [{ position, games: picks }] : [],
  players: picks ? [{ name: "Spieler", games: picks, wins: 1 }] : [], bans_by_us: 0, bans_against: 0,
  presence: 0.5, ...extra,
});

const champs = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

describe("ChampionTable", () => {
  const rows = [
    row(266, 3, "TOP", { positions: [{ position: "TOP", games: 2 }, { position: "MIDDLE", games: 1 }] }),
    row(62, 5, "JUNGLE"),
    row(266 + 1000, 0, "", { bans_against: 4 }),
  ];

  it("sortiert nach Picks, filtert Rolle und blendet reine Bans optional ein", () => {
    renderWithProviders(<ChampionTable rows={rows} />);
    expect(champs()).toEqual(["WuWukong", "AaAatrox"]);
    expect(screen.getByText("Top (2), Mid (1)")).toBeInTheDocument();   // mehrere Rollen in einer Zeile
    fireEvent.change(screen.getByLabelText("Rolle filtern"), { target: { value: "MIDDLE" } });
    expect(champs()).toEqual(["AaAatrox"]);                               // Filter greift auch für Nebenrollen
    fireEvent.change(screen.getByLabelText("Rolle filtern"), { target: { value: "" } });
    fireEvent.click(screen.getByLabelText("auch nur gebannte"));
    expect(screen.getAllByRole("row")).toHaveLength(4);
    expect(screen.getByText("nur gebannt")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Bans (Gegner)"));
    expect(champs()[0]).toContain("#1266");
  });
});
