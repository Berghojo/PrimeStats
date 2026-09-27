import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InfoTip } from "./InfoTip";

describe("InfoTip", () => {
  it("zeigt den Text erst bei Hover bzw. Antippen und schließt mit Escape", () => {
    render(<InfoTip>Erklärtext</InfoTip>);
    expect(screen.queryByRole("tooltip")).toBeNull();
    const btn = screen.getByRole("button", { name: "Erklärung" });

    fireEvent.mouseEnter(btn.parentElement!);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Erklärtext");
    fireEvent.mouseLeave(btn.parentElement!);
    expect(screen.queryByRole("tooltip")).toBeNull();

    fireEvent.click(btn);  // mobil: antippen hält ihn offen
    expect(btn).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(btn, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
