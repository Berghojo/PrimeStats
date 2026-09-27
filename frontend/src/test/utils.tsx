import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import type { Meta } from "../api/types";

export const META: Meta = {
  demo: true,
  configured: true,
  uploader_url: "https://example.org/uploader",
  ddragon_version: "15.13.1",
  champions: { "266": { id: "Aatrox", name: "Aatrox" }, "62": { id: "MonkeyKing", name: "Wukong" } },
  positions: { TOP: "Top", JUNGLE: "Jungle", MIDDLE: "Mid", BOTTOM: "ADC", UTILITY: "Support" },
  labels: { official: "Prime League", scrim: "Scrim", "": "Ohne Label" },
};

export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["meta"], META);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
