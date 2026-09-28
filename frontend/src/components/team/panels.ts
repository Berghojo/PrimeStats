/** Bausteine eines Reports. Auf den Scouting- und Team-Seiten frei ein-/ausblendbar und sortierbar. */
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
  { key: "gold", label: "Golddifferenz", half: true },
  { key: "objectives", label: "Objectives", half: true },
  { key: "players", label: "Spieler" },
  { key: "champions", label: "Champion-Picks" },
  { key: "pools", label: "Champion-Pools" },
  { key: "draft", label: "Draft" },
  { key: "jungle", label: "Jungle", only: "team" },
  { key: "kills", label: "Kills" },
  { key: "deaths", label: "Deaths" },
  { key: "trend", label: "Formkurve" },
  { key: "timeline", label: "Zeitverlauf" },
];

export type ReportKind = "team" | "scout";

export const panelsFor = (kind: ReportKind) => PANELS.filter((p) => !p.only || p.only === kind);

export const defaultPanels = (kind: ReportKind) => panelsFor(kind).map((p) => p.key);

/** Umbenannte Panels (ältere geteilte Links und gespeicherte Ansichten) */
const RENAMED: Record<string, string[]> = { ganks: ["kills", "deaths"] };

/** Nur bekannte Panels, ohne Doppelte, in der angegebenen Reihenfolge. */
export function cleanPanels(keys: string[], kind: ReportKind): string[] {
  const known = new Set(panelsFor(kind).map((p) => p.key));
  return [...new Set(keys.flatMap((k) => RENAMED[k] ?? [k]))].filter((k) => known.has(k));
}
