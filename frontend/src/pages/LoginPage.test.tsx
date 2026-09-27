import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../test/utils";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("prüft bei der Registrierung die Passwort-Wiederholung, bevor etwas gesendet wird", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ user: null, riot_accounts: [] })));
    renderWithProviders(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    fireEvent.change(screen.getByLabelText("Benutzername oder E-Mail"), { target: { value: "spieler" } });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "geheim123" } });
    fireEvent.change(screen.getByLabelText("Passwort wiederholen"), { target: { value: "anders123" } });
    fireEvent.submit(screen.getByLabelText("Benutzername oder E-Mail").closest("form")!);
    expect(screen.getByRole("alert")).toHaveTextContent("stimmen nicht überein");
    expect(fetchSpy.mock.calls.filter(([url]) => String(url).includes("/auth/register"))).toHaveLength(0);
    fetchSpy.mockRestore();
  });
});
