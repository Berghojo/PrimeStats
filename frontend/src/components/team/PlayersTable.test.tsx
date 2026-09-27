import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PlayerReport } from "../../api/types";
import { renderWithProviders } from "../../test/utils";
import { PlayersTable } from "./PlayersTable";

const player = (name: string, kda: number, member = true): PlayerReport => ({
  puuid: name, name, tag: "EUW", member, position: "MIDDLE", games: 10, wins: 5, winrate: 0.5, kills: 3, deaths: 2, assists: 4,
  kda, cspm: 8, gpm: 400, dpm: 600, dtpm: 500, vspm: 1, wards: 8, wards_killed: 2, control_wards: 2, kp: 0.5,
  damage_share: 0.25, gold_share: 0.2, first_blood: 0.1, gd10: null, gd15: 120, csd15: -3, xpd15: null, champions: [],
});

const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

describe("PlayersTable", () => {
  it("sortiert per Klick auf die Spaltenüberschrift", () => {
    renderWithProviders(<PlayersTable players={[player("A", 2), player("B", 4), player("C", 3, false)]} />);
    expect(names()).toEqual(["A", "B", "C Aushilfe"]);
    fireEvent.click(screen.getByText("KDA"));
    expect(names()).toEqual(["B", "C Aushilfe", "A"]);
    fireEvent.click(screen.getByText("KDA"));
    expect(names()).toEqual(["A", "C Aushilfe", "B"]);
  });

  it("zeigt Rollen und Differenzen formatiert an", () => {
    renderWithProviders(<PlayersTable players={[player("A", 2)]} />);
    expect(screen.getByText("Mid")).toBeInTheDocument();
    const gd = screen.getByText("+120");
    expect(gd).toHaveClass("pos");
  });
});
