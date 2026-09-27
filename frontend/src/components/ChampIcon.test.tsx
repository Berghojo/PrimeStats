import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "../test/utils";
import { ChampIcon } from "./ChampIcon";

describe("ChampIcon", () => {
  it("nutzt die Data-Dragon-ID für das Bild und fällt bei Fehlern auf Initialen zurück", () => {
    renderWithProviders(<ChampIcon id={62} />);
    const img = screen.getByAltText("Wukong");
    expect(img).toHaveAttribute("src", "https://ddragon.leagueoflegends.com/cdn/15.13.1/img/champion/MonkeyKing.png");
    fireEvent.error(img);
    expect(screen.queryByAltText("Wukong")).toBeNull();
    expect(screen.getByTitle("Wukong")).toHaveTextContent("Wu");
  });
});
