/** Darstellungsstil der Oberfläche: "prime" (Esports, Standard) oder "analytics" (nüchtern, dicht). */
export type UiStyle = "prime" | "analytics";

const KEY = "ps-style";

export function storedStyle(): UiStyle {
  try {
    return localStorage.getItem(KEY) === "analytics" ? "analytics" : "prime";
  } catch {
    return "prime";
  }
}

export function applyStyle(style: UiStyle) {
  document.documentElement.dataset.style = style;
  try {
    localStorage.setItem(KEY, style);
  } catch {
    /* ohne Speicher gilt die Wahl nur bis zum Neuladen */
  }
}
