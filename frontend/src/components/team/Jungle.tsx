import { type ReactNode, createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { Jungle, JungleEvent, JunglePath, Side } from "../../api/types";
import { dt, duration } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { type Clear, firstFullClear, reconstruct } from "../../lib/jungleRoute";
import { type Point, interpolate, wallPolygons } from "../../lib/navgrid";
import { InfoTip } from "../InfoTip";
import { MapPanel, OptionList, RailSection } from "./MapPanel";

/** Kartengröße in Spielkoordinaten (Summoner's Rift, Ursprung unten links) */
const MAP_W = 14870;
const MAP_H = 14980;
export const SIZE = 512;
/** Bereich, den das offizielle Kartenbild (Data Dragon, map11.png) abdeckt – laut Riot-Doku */
const IMG_MIN = -120;
const IMG_MAX_X = 14870;
const IMG_MAX_Y = 14980;

export const px = (x: number) => ((x - IMG_MIN) / (IMG_MAX_X - IMG_MIN)) * SIZE;
export const py = (y: number) => SIZE - ((y - IMG_MIN) / (IMG_MAX_Y - IMG_MIN)) * SIZE;

/** Darstellung der Karte (Wände, Abgleich mit dem echten Kartenbild) – gilt für Heatmap und Pathing. */
interface MapSettings {
  walls: boolean;
  /** Abgleich: echtes Kartenbild voll sichtbar, Wände nur als Umriss */
  calibrate: boolean;
  imageOpacity: number;
  onImage: (state: "ok" | "failed") => void;
}
const MapContext = createContext<MapSettings>({ walls: true, calibrate: false, imageOpacity: 0.55, onImage: () => {} });

const SIDE_COLOR: Record<Side, string> = { blue: "#4c8dff", red: "#ff4d5e" };

/** Camps der blauen Seite; die rote Seite ist punktgespiegelt. */
const CAMPS: [string, number, number][] = [
  ["Red Buff", 7860, 4110], ["Krugs", 8400, 2730], ["Raptors", 6940, 5420],
  ["Wolves", 3780, 6500], ["Blue Buff", 3870, 7900], ["Gromp", 2110, 8370],
];

function nearestCamp(point: [number, number], side: Side): string {
  const [x, y] = side === "blue" ? point : [MAP_W - point[0], MAP_H - point[1]];
  let best = "", dist = Infinity;
  for (const [name, cx, cy] of CAMPS) {
    const d = (cx - x) ** 2 + (cy - y) ** 2;
    if (d < dist) [best, dist] = [name, d];
  }
  return dist < 2200 ** 2 ? best : "Sonstiges";
}

/** Grobe Kartenzone eines Ereignisses (aus Sicht des eigenen Teams). */
export function zone(x: number, y: number, side: Side): string {
  const u = x / MAP_W, v = y / MAP_H;
  if ((u < 0.2 && v < 0.2) || (u > 0.8 && v > 0.8)) return "Basis";
  if ((u < 0.2 && v > 0.45) || (v > 0.8 && u < 0.55)) return "Toplane";
  if ((v < 0.2 && u > 0.45) || (u > 0.8 && v < 0.55)) return "Botlane";
  if (Math.abs(u - v) < 0.09) return "Midlane";
  if (Math.abs(u + v - 1) < 0.07) return "Fluss";
  const blueHalf = u + v < 1;
  return blueHalf === (side === "blue") ? "Eigener Jungle" : "Gegnerischer Jungle";
}

const ZONES = ["Toplane", "Midlane", "Botlane", "Fluss", "Eigener Jungle", "Gegnerischer Jungle", "Basis"];

/** Summoner's Rift als schlichte Vektorgrafik – Hintergrund, falls das Kartenbild nicht lädt. */
/** Wände als ein SVG-Pfad (Pixelkoordinaten); Umrisse aus dem Raster, kantig vereinfacht */
// Der Kartenrand zählt als Wand: Rechteck um alles, darin die Umrisse (Spielfeld = Loch, Wände darin = Fläche)
const WALL_PATH = `M0 0H${SIZE}V${SIZE}H0Z` + wallPolygons()
  .map((poly) => `M${poly.map(([x, y]) => `${px(x).toFixed(1)} ${py(y).toFixed(1)}`).join("L")}Z`)
  .join("");

/** Lanes (Mitte bei ≈1250 bzw. ≈13 700) und Basen für den Kartenhintergrund */
const LANE_LOW = 1250;
const LANE_HIGH_X = MAP_W - 1250;
const LANE_HIGH_Y = MAP_H - 1250;

export function MapBase(_: { walls?: boolean }) {
  const { mapUrl } = useGameData();
  const { walls, calibrate, imageOpacity, onImage } = useContext(MapContext);
  const [failed, setFailed] = useState(false);
  return (
    <>
      <rect width={SIZE} height={SIZE} fill="#0e1a16" />
      <path d={`M${px(0)} ${py(MAP_H)} L${px(MAP_W)} ${py(0)}`} stroke="#12303a" strokeWidth={34} />
      <g fill="none" stroke="#24302c" strokeWidth={14} strokeLinecap="round" strokeLinejoin="round">
        <path d={`M${px(LANE_LOW)} ${py(LANE_LOW)} L${px(LANE_LOW)} ${py(LANE_HIGH_Y)} L${px(LANE_HIGH_X)} ${py(LANE_HIGH_Y)}`} />
        <path d={`M${px(LANE_LOW)} ${py(LANE_LOW)} L${px(LANE_HIGH_X)} ${py(LANE_LOW)} L${px(LANE_HIGH_X)} ${py(LANE_HIGH_Y)}`} />
        <path d={`M${px(LANE_LOW)} ${py(LANE_LOW)} L${px(LANE_HIGH_X)} ${py(LANE_HIGH_Y)}`} />
      </g>
      <circle cx={px(700)} cy={py(700)} r={30} fill="#16233d" />
      <circle cx={px(MAP_W - 700)} cy={py(MAP_H - 700)} r={30} fill="#3a1820" />
      {mapUrl && !failed && (
        <image href={mapUrl} width={SIZE} height={SIZE} opacity={imageOpacity}
          onLoad={() => onImage("ok")}
          onError={() => {
            setFailed(true);
            onImage("failed");
          }} />
      )}
      {(walls || calibrate) && <path className={calibrate ? "walls outline" : "walls"} d={WALL_PATH} fillRule="evenodd" />}
    </>
  );
}

/** Heatmap: Punkte aufsummieren (Alpha), dann einfarbig einfärben – hell = häufig. */
export function Heat({ points, rgb, radius = 32, intensity = 1 }: {
  points: { x: number; y: number }[];
  rgb: [number, number, number];
  /** Größe eines Punkts in Pixeln (bei 512 px Kartenbreite) */
  radius?: number;
  /** Faktor auf die Deckkraft je Punkt */
  intensity?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, SIZE, SIZE);
    if (!points.length) return;
    const strength = Math.min(0.9, Math.min(0.45, Math.max(0.1, 2.5 / Math.sqrt(points.length))) * intensity);
    for (const p of points) {
      const g = ctx.createRadialGradient(px(p.x), py(p.y), 0, px(p.x), py(p.y), radius);
      g.addColorStop(0, `rgba(0,0,0,${strength})`);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(px(p.x) - radius, py(p.y) - radius, radius * 2, radius * 2);
    }
    const img = ctx.getImageData(0, 0, SIZE, SIZE);
    const d = img.data;
    for (let i = 0; i < d.length; i += 4) {
      const a = d[i + 3] / 255;
      if (!a) continue;
      // eine Farbe: mit steigender Dichte deckender und heller (Richtung Weiß)
      const light = Math.max(0, a - 0.55) / 0.45;
      d[i] = rgb[0] + (255 - rgb[0]) * light;
      d[i + 1] = rgb[1] + (255 - rgb[1]) * light;
      d[i + 2] = rgb[2] + (255 - rgb[2]) * light;
      d[i + 3] = Math.min(230, Math.pow(a, 0.75) * 320);
    }
    ctx.putImageData(img, 0, 0);
  }, [points, rgb, radius, intensity]);
  return <canvas ref={ref} width={SIZE} height={SIZE} className="map-layer" aria-hidden />;
}

type View = "heat" | "path";
type HeatType = "involved" | "death";

/** Schieberegler mit Beschriftung und aktuellem Wert */
export function Slider({ label, value, min, max, step = 1, format, onChange }: {
  label: string; value: number; min: number; max: number; step?: number;
  format?: (v: number) => string; onChange: (v: number) => void;
}) {
  return (
    <label className="slider">
      <span className="slider-head"><span>{label}</span><b>{format ? format(value) : value}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}
export const KILL_RGB: [number, number, number] = [0, 220, 192];
export const DEATH_RGB: [number, number, number] = [255, 77, 94];

function Segmented<T extends string | number>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" role="radio" aria-checked={o.value === value}
          className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

function HeatView({ events, games, walls, shared }: { events: JungleEvent[]; games: number; walls: boolean; shared: ReactNode }) {
  const [type, setType] = useState<HeatType>("involved");
  const lastMinute = Math.max(15, Math.ceil(Math.max(0, ...events.map((e) => e.t)) / 60));
  const [from, setFrom] = useState(0);
  const [to, setTo] = useState(15);
  const [radius, setRadius] = useState(32);
  const [intensity, setIntensity] = useState(1);
  const upto = Math.min(to, lastMinute);
  const shown = useMemo(
    () => events.filter((e) => e.t >= from * 60 && e.t <= upto * 60
      && (type === "death" ? e.type === "death" : e.type !== "death")),
    [events, from, upto, type],
  );
  const byZone = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of shown) counts.set(zone(e.x, e.y, e.side), (counts.get(zone(e.x, e.y, e.side)) ?? 0) + 1);
    return ZONES.map((z) => ({ zone: z, n: counts.get(z) ?? 0 })).filter((z) => z.n > 0);
  }, [shown]);
  const kills = shown.filter((e) => e.type === "kill").length;

  const inRange = events.filter((e) => e.t >= from * 60 && e.t <= upto * 60);
  return (
    <MapPanel
      rail={(
        <>
          <RailSection title="Ereignisse">
            <OptionList label="Ereignisse" selected={type} onToggle={setType} options={[
              { value: "involved", label: "Kills + Assists", count: inRange.filter((e) => e.type !== "death").length },
              { value: "death", label: "Tode", count: inRange.filter((e) => e.type === "death").length },
            ]} />
          </RailSection>
          <RailSection title="Zeitraum">
            <Slider label="Von Minute" value={from} min={0} max={lastMinute} onChange={(v) => {
              setFrom(v);
              if (v > upto) setTo(v);
            }} />
            <Slider label="Bis Minute" value={upto} min={0} max={lastMinute} onChange={(v) => {
              setTo(v);
              if (v < from) setFrom(v);
            }} />
          </RailSection>
          <RailSection title="Darstellung">
            <Slider label="Punktgröße" value={radius} min={12} max={64} onChange={setRadius} format={(v) => `${v} px`} />
            <Slider label="Intensität" value={intensity} min={0.25} max={2} step={0.05} onChange={setIntensity}
              format={(v) => `${Math.round(v * 100)} %`} />
          </RailSection>
          {shared}
        </>
      )}
      map={(
        <div className="map">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="map-layer"><MapBase walls={walls} /></svg>
          <Heat points={shown} rgb={type === "death" ? DEATH_RGB : KILL_RGB} radius={radius} intensity={intensity} />
        </div>
      )}
      side={(
        <>
          <div className="kpis">
            <div className="kpi">
              <div className="label">{type === "death" ? "Tode" : "Kill-Beteiligungen"}</div>
              <div className="value">{shown.length}</div>
              <div className="hint">Ø {games ? (shown.length / games).toFixed(1) : "–"} pro Spiel</div>
            </div>
            {type === "involved" && (
              <div className="kpi">
                <div className="label">Kills / Assists</div>
                <div className="value">{kills} / {shown.length - kills}</div>
                <div className="hint">Minute {from}–{upto}</div>
              </div>
            )}
          </div>
          <table className="data">
            <thead><tr><th className="left">Zone</th><th>Anzahl</th><th>Anteil</th></tr></thead>
            <tbody>
              {byZone.map((z) => (
                <tr key={z.zone}>
                  <td className="left">{z.zone}</td>
                  <td>{z.n}</td>
                  <td>{Math.round((z.n / shown.length) * 100)}%</td>
                </tr>
              ))}
              {!byZone.length && <tr><td className="left muted" colSpan={3}>Keine Ereignisse in diesem Zeitraum.</td></tr>}
            </tbody>
          </table>
        </>
      )}
    />
  );
}

/** Route eines Spiels: mit Jungle-CS über die geräumten Camps, sonst direkt zwischen den Minutenpositionen */
function buildRoute(p: JunglePath, minutes: number, realistic: boolean) {
  const minutePts = p.points.slice(0, minutes + 1).map((pt, m) => (m >= 1 && pt ? (pt as Point) : null));
  if (realistic && p.jungle_cs?.length) {
    const r = reconstruct(p.points as (Point | null)[], p.jungle_cs, minutes, 1, true, p.side);
    return { line: r.path, minutePts, clears: r.clears };
  }
  const pts = minutePts.filter((pt): pt is Point => !!pt);
  return { line: realistic ? interpolate(pts).path : pts, minutePts, clears: [] as Clear[] };
}

function PathView({ paths, maxMinutes, walls, shared }: {
  paths: JunglePath[]; maxMinutes: number; walls: boolean; shared: ReactNode;
}) {
  const { champion } = useGameData();
  const [minutes, setMinutes] = useState(Math.min(6, maxMinutes));
  const [side, setSide] = useState<"all" | Side>("all");
  const [realistic, setRealistic] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const shown = paths.filter((p) => side === "all" || p.side === side);
  const hovered = shown.find((p) => p.match_id === hover);
  const routes = useMemo(
    () => new Map(shown.map((p) => [p.match_id, buildRoute(p, minutes, realistic)])),
    [shown, minutes, realistic],
  );
  // Startroute unabhängig vom Regler: die ersten drei geräumten Camps (volle Pfadlänge)
  const openings = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of shown) {
      const clears = p.jungle_cs?.length ? reconstruct(p.points as (Point | null)[], p.jungle_cs, maxMinutes, 1, false, p.side).clears : [];
      const first = p.points[1];
      const key = clears.length
        ? clears.slice(0, 3).map((c) => c.camp.name).join(" → ")
        : first ? nearestCamp(first, p.side) : "";
      if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [shown, maxMinutes]);
  const hoveredRoute = hovered ? routes.get(hovered.match_id) : undefined;
  // Erster Full Clear je Spiel (aus den rekonstruierten Camps, Zeiten interpoliert)
  const fullClears = useMemo(() => new Map(shown.map((p) => [p.match_id, p.jungle_cs?.length
    ? firstFullClear(reconstruct(p.points as (Point | null)[], p.jungle_cs, 7, 1, false, p.side).clears, p.side)
    : null])), [shown]);
  const clearStats = useMemo(() => {
    const withCs = shown.filter((p) => p.jungle_cs?.length);
    const times = withCs.map((p) => fullClears.get(p.match_id)).filter((t): t is number => t != null);
    return {
      avg: times.length ? times.reduce((a, b) => a + b, 0) / times.length : null,
      fastest: times.length ? Math.min(...times) : null,
      share: withCs.length ? times.length / withCs.length : null,
      n: times.length,
    };
  }, [shown, fullClears]);
  const fmt = (t: number | null) => (t === null ? "–" : duration(Math.round(t)));

  return (
    <MapPanel
      rail={(
        <>
          <RailSection title="Seite">
            <OptionList label="Seite" selected={side} onToggle={setSide} options={[
              { value: "all", label: "Beide Seiten", count: paths.length },
              { value: "blue", label: "Blau", count: paths.filter((p) => p.side === "blue").length },
              { value: "red", label: "Rot", count: paths.filter((p) => p.side === "red").length },
            ]} />
          </RailSection>
          <RailSection title="Zeitraum">
            <Slider label="Bis Minute" value={minutes} min={2} max={maxMinutes} onChange={setMinutes} />
          </RailSection>
          <RailSection title="Laufwege" action={(
            <InfoTip>
              Aus dem Anstieg der Jungle-CS zwischen zwei Minuten ergibt sich die Zahl der geräumten Camps (4 CS je Camp).
              Gewählt werden die Camps, die zu der Zeit stehen (Spawn 1:30, Scuttle 3:30, Respawn 2:15 bzw. 5:00 bei den
              Buffs) und den kürzesten begehbaren Weg zwischen den beiden Positionen ergeben.
            </InfoTip>
          )}>
            <OptionList multi label="Laufwege" selected={new Set(realistic ? ["on"] : [])}
              onToggle={() => setRealistic((r) => !r)}
              options={[{ value: "on", label: "Über geräumte Camps" }]} />
          </RailSection>
          {shared}
        </>
      )}
      map={(
        <div className="map">
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="map-layer" onMouseLeave={() => setHover(null)}>
              <MapBase walls={walls} />
              {shown.map((p) => {
                const r = routes.get(p.match_id)!;
                const line = r.line.map(([x, y]) => `${px(x)},${py(y)}`).join(" ");
                const dim = hover && hover !== p.match_id;
                const last = r.minutePts.reduce((n, pt, i) => (pt ? i : n), 0);
                return (
                  <g key={p.match_id} opacity={dim ? 0.12 : hover ? 1 : 0.6} onMouseEnter={() => setHover(p.match_id)}
                    style={{ cursor: "pointer" }}>
                    <polyline points={line} fill="none" stroke="transparent" strokeWidth={12} />
                    <polyline points={line} fill="none"
                      stroke={SIDE_COLOR[p.side]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                    {r.clears.map((c) => (
                      <rect key={`c${c.order}`} x={px(c.camp.pos[0]) - 4} y={py(c.camp.pos[1]) - 4} width={8} height={8}
                        transform={`rotate(45 ${px(c.camp.pos[0])} ${py(c.camp.pos[1])})`}
                        className="camp-mark" />
                    ))}
                    {r.minutePts.map((pt, i) => pt && (
                      <circle key={i} cx={px(pt[0])} cy={py(pt[1])} r={i === last ? 5 : 3}
                        fill={SIDE_COLOR[p.side]} stroke="#07090d" strokeWidth={2} />
                    ))}
                    {hover === p.match_id && r.minutePts.map((pt, i) => pt && (
                      <text key={`t${i}`} x={px(pt[0]) + 7} y={py(pt[1]) - 6} className="map-label">{i}</text>
                    ))}
                  </g>
                );
              })}
            </svg>
          </div>
      )}
      caption={(
        <>
          {hovered ? (
            <>
              {dt(hovered.date)} · {champion(hovered.champion_id).name} · {hovered.side === "blue" ? "Blau" : "Rot"} ·{" "}
              {hovered.win ? "Sieg" : "Niederlage"}
              {hovered.jungle_cs?.length > 0 && (
                <> · {fullClears.get(hovered.match_id) != null
                  ? <>erster Full Clear {fmt(fullClears.get(hovered.match_id)!)}</> : "kein Full Clear"}</>
              )}
              {!!hoveredRoute?.clears.length && (
                <><br />Camps: {hoveredRoute.clears.map((c) => `${c.camp.name} (~${duration(c.t)})`).join(" → ")}</>
              )}
            </>
          ) : <>Punkte = Position je Minute (Zahl = Minute), Rauten = geräumte Camps. Linie überfahren für Details.</>}
        
        </>
      )}
      side={(
        <>
          <div className="row small">
            <span className="legend-dot" style={{ background: SIDE_COLOR.blue }} /> Blaue Seite
            <span className="legend-dot" style={{ background: SIDE_COLOR.red }} /> Rote Seite
          </div>
        <div className="kpis">
          <div className="kpi">
            <div className="label">
              Erster Full Clear (Ø)
              <InfoTip>
                Ende des allerersten Full Clears: alle 6 eigenen Camps geräumt, bevor ein Camp ein zweites Mal genommen
                wird, spätestens bis 6:00 (Scuttle und Invades zwischendurch zählen mit). Die Zeit stammt aus dem
                zwischen den Minutenwerten interpolierten Jungle-CS-Verlauf; Camps spawnen bei 1:30.
              </InfoTip>
            </div>
            <div className="value">{fmt(clearStats.avg)}</div>
            <div className="hint">schnellster {fmt(clearStats.fastest)}</div>
          </div>
          <div className="kpi">
            <div className="label">Full Clear gespielt</div>
            <div className="value">{clearStats.share === null ? "–" : `${Math.round(clearStats.share * 100)} %`}</div>
            <div className="hint">{clearStats.n} Spiele · sonst Half Clear / früher Gank</div>
          </div>
        </div>
        <table className="data">
          <thead><tr><th className="left">Startroute (erste 3 Camps)</th><th>Spiele</th><th>Anteil</th></tr></thead>
          <tbody>
            {openings.map(([name, n]) => (
              <tr key={name}><td className="left wrap">{name}</td><td>{n}</td><td>{Math.round((n / shown.length) * 100)}%</td></tr>
            ))}
            {!openings.length && <tr><td className="left muted" colSpan={3}>Keine Positionsdaten.</td></tr>}
          </tbody>
        </table>
        </>
      )}
    />
  );
}

/** Jungle-Auswertung: Gank-Heatmap und Pathing des eigenen Junglers. */
export function JungleCard({ jungle }: { jungle: Jungle }) {
  const [view, setView] = useState<View>("heat");
  const [walls, setWalls] = useState(true);
  const [calibrate, setCalibrate] = useState(false);
  const [imageOpacity, setImageOpacity] = useState(1);
  const [image, setImage] = useState<"ok" | "failed" | null>(null);
  const settings: MapSettings = { walls, calibrate, imageOpacity: calibrate ? imageOpacity : 0.55, onImage: setImage };
  const [off, setOff] = useState<Set<string>>(new Set());
  if (!jungle.players.length) return null;
  const active = (puuid: string) => !off.has(puuid);
  const events = jungle.events.filter((e) => active(e.puuid));
  const paths = jungle.paths.filter((p) => active(p.puuid));
  const games = jungle.players.filter((p) => active(p.puuid)).reduce((n, p) => n + p.games, 0);

  const toggleJungler = (puuid: string) => setOff((s) => {
    const next = new Set(s);
    if (next.has(puuid)) next.delete(puuid);
    else next.add(puuid);
    return next;
  });
  // Abschnitte, die Heatmap und Pathing teilen: Jungler-Auswahl und Kartenoptionen
  const shared = (
    <>
      {jungle.players.length > 1 && (
        <RailSection title="Jungler">
          <OptionList multi label="Jungler" selected={new Set(jungle.players.map((p) => p.puuid).filter(active))}
            onToggle={toggleJungler}
            options={jungle.players.map((p) => ({ value: p.puuid, label: p.name, count: p.games }))} />
        </RailSection>
      )}
      <RailSection title="Karte" action={(
        <InfoTip>
          Kartenabgleich: das echte Kartenbild (Riot Data Dragon) mit den Wänden als gestrichelte Umrisse – so lässt sich
          prüfen, ob die Wände passen, die PrimeStats für die Laufwege verwendet.
        </InfoTip>
      )}>
        <OptionList multi label="Karte" selected={new Set([walls && "walls", calibrate && "calibrate"].filter(Boolean) as string[])}
          onToggle={(v) => (v === "walls" ? setWalls((w) => !w) : setCalibrate((c) => !c))}
          options={[{ value: "walls", label: "Wände" }, { value: "calibrate", label: "Kartenabgleich" }]} />
        {calibrate && (
          <Slider label="Kartenbild" value={imageOpacity} min={0} max={1} step={0.05} onChange={setImageOpacity}
            format={(v) => `${Math.round(v * 100)} %`} />
        )}
        {calibrate && image === "failed" && (
          <p className="muted small" style={{ margin: 0 }}>Kartenbild von Riot nicht erreichbar.</p>
        )}
      </RailSection>
    </>
  );

  return (
    <section className="card stack">
      <div className="panel-head">
        <h2>
          Jungle
          <InfoTip>
            Gank-Heatmap und Pathing des Junglers aus {games} Spielen mit Timeline.
            <br /><br />
            <b>Heatmap:</b> Orte, an denen der Jungler an Kills beteiligt war bzw. gestorben ist. Frühe Kills auf einer
            Lane sind meist Ganks.
            <br /><br />
            <b>Pathing:</b> Die Timeline enthält nur eine Position pro Minute (Punkte). Dazwischen zeichnet PrimeStats den
            kürzesten begehbaren Weg über die Karte – plausibel, aber nicht der exakte Laufweg.
          </InfoTip>
        </h2>
        <Segmented label="Ansicht" value={view} onChange={setView}
          options={[{ value: "heat", label: "Gank-Heatmap" }, { value: "path", label: "Pathing" }]} />
      </div>
      <MapContext.Provider value={settings}>
        {view === "heat"
          ? <HeatView events={events} games={games} walls={walls} shared={shared} />
          : <PathView paths={paths} maxMinutes={jungle.path_minutes} walls={walls} shared={shared} />}
      </MapContext.Provider>
    </section>
  );
}
