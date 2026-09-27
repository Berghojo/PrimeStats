const TZ = "Europe/Berlin";

const numberFormats = new Map<number, Intl.NumberFormat>();
function nf(digits: number) {
  let f = numberFormats.get(digits);
  if (!f) {
    f = new Intl.NumberFormat("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    numberFormats.set(digits, f);
  }
  return f;
}

export const num = (value: number | null | undefined, digits = 1) =>
  value === null || value === undefined || Number.isNaN(value) ? "–" : nf(digits).format(value);

export const pct = (value: number | null | undefined, digits = 0) =>
  value === null || value === undefined ? "–" : `${nf(digits).format(value * 100)}%`;

export const signed = (value: number | null | undefined, digits = 0) =>
  value === null || value === undefined ? "–" : `${value > 0 ? "+" : ""}${num(value, digits)}`;

export function duration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return "–";
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

const dateTime = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, dateStyle: "medium", timeStyle: "short" });
const shortDate = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, day: "2-digit", month: "2-digit" });
const relative = new Intl.RelativeTimeFormat("de-DE", { numeric: "auto" });

export const dt = (iso: string) => dateTime.format(new Date(iso));
export const shortDt = (iso: string) => shortDate.format(new Date(iso));

export function ago(iso: string, now = Date.now()) {
  const diff = (new Date(iso).getTime() - now) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, secs] of units) {
    if (Math.abs(diff) >= secs) return relative.format(Math.round(diff / secs), unit);
  }
  return "gerade eben";
}

/** CSS-Klasse für positive/negative Werte relativ zu einem neutralen Wert. */
export function tone(value: number | null | undefined, neutral = 0) {
  if (value === null || value === undefined || value === neutral) return "";
  return value > neutral ? "pos" : "neg";
}

export function splitRiotId(value: string): [string, string] | null {
  const idx = value.lastIndexOf("#");
  if (idx <= 0) return null;
  const name = value.slice(0, idx).trim();
  const tag = value.slice(idx + 1).trim();
  return name && tag ? [name, tag] : null;
}
