export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details: string[] = [],
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | (string | number)[] | null | undefined>;

export function buildQuery(params: Query = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function errorMessage(detail: unknown): { message: string; details: string[] } {
  if (typeof detail === "string") return { message: detail, details: [] };
  if (Array.isArray(detail)) {
    // FastAPI-Validierungsfehler
    const details = detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`);
    return { message: "Ungültige Eingabe.", details };
  }
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; errors?: string[] };
    return { message: d.message ?? "Fehler", details: d.errors ?? [] };
  }
  return { message: "Unbekannter Fehler", details: [] };
}

export async function api<T>(path: string, init: RequestInit & { query?: Query } = {}): Promise<T> {
  const { query, ...rest } = init;
  const resp = await fetch(`/api${path}${buildQuery(query)}`, {
    ...rest,
    credentials: "same-origin",
    // Der Server verlangt diesen Header für ändernde Anfragen (Schutz gegen CSRF)
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Requested-With": "PrimeStats",
      ...rest.headers,
    },
  });
  if (!resp.ok) {
    let body: { detail?: unknown } = {};
    try {
      body = await resp.json();
    } catch {
      /* kein JSON */
    }
    const { message, details } = errorMessage(body.detail ?? resp.statusText);
    throw new ApiError(resp.status, message, details);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}
