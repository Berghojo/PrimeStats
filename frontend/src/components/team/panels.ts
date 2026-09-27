/** Bausteine eines Reports. Auf den Scouting-Seiten frei ein-/ausblendbar und sortierbar. */
export interface PanelDef {
  key: string;
  label: string;
  /** halbe Breite: zwei aufeinanderfolgende halbe Panels teilen sich eine Zeile */
  half?: boolean;
  /** nur im Team-Dashboard bzw. nur beim Scouting */
  only?: "team" | "scout";
}

export const PANELS: PanelDef[] = [
  { key: "overview", label: "Kennzahlen" },
  { key: "gold", label: "Golddifferenz im Spielverlauf", half: true },
  { key: "objectives", label: "Objectives", half: true },
  { key: "players", label: "Spieler" },
  { key: "champions", label: "Champion-Picks" },
  { key: "pools", label: "Champion-Pools" },
  { key: "draft", label: "Draft" },
  { key: "jungle", label: "Jungle", only: "team" },
  { key: "ganks", label: "Ganks & Roams" },
  { key: "trend", label: "Formkurve" },
  { key: "timeline", label: "Zeitverlauf", only: "scout" },
  { key: "games", label: "Spiele" },
];

export type ReportKind = "team" | "scout";

export const panelsFor = (kind: ReportKind) => PANELS.filter((p) => !p.only || p.only === kind);

export const defaultPanels = (kind: ReportKind) => panelsFor(kind).map((p) => p.key);

/** Nur bekannte Panels, ohne Doppelte, in der angegebenen Reihenfolge. */
export function cleanPanels(keys: string[], kind: ReportKind): string[] {
  const known = new Set(panelsFor(kind).map((p) => p.key));
  return [...new Set(keys)].filter((k) => known.has(k));
}
