import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { Jungle, JungleEvent, JunglePath, Side } from "../../api/types";
import { dt } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { type Point, WALLS, edges, interpolate } from "../../lib/rift";
import { InfoTip } from "../InfoTip";

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
export function MapBase(_: { walls?: boolean }) {
  const { mapUrl } = useGameData();
  const { walls, calibrate, imageOpacity, onImage } = useContext(MapContext);
  const [failed, setFailed] = useState(false);
  return (
    <>
      <rect width={SIZE} height={SIZE} fill="#0e1a16" />
      <path d={`M0 0 L${SIZE} ${SIZE}`} stroke="#12303a" strokeWidth={34} />
      <g fill="none" stroke="#24302c" strokeWidth={14} strokeLinecap="round" strokeLinejoin="round">
        <path d="M38 474 L38 38 L474 38" />
        <path d="M38 474 L474 474 L474 38" />
        <path d="M38 474 L474 38" />
      </g>
      <circle cx={34} cy={478} r={30} fill="#16233d" />
      <circle cx={478} cy={34} r={30} fill="#3a1820" />
      {mapUrl && !failed && (
        <image href={mapUrl} width={SIZE} height={SIZE} opacity={imageOpacity}
          onLoad={() => onImage("ok")}
          onError={() => {
            setFailed(true);
            onImage("failed");
          }} />
      )}
      {(walls || calibrate) && (
        <g className={calibrate ? "walls outline" : "walls"}>
          {WALLS.map((w, i) => <polygon key={i} points={w.map(([x, y]) => `${px(x)},${py(y)}`).join(" ")} />)}
        </g>
      )}
    </>
  );
}

/** Heatmap: Punkte aufsummieren (Alpha), dann einfarbig einfärben – hell = häufig. */
function Heat({ points, rgb, radius = 32, intensity = 1 }: {
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
const KILL_RGB: [number, number, number] = [0, 220, 192];
const DEATH_RGB: [number, number, number] = [255, 77, 94];

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

function HeatView({ events, games, walls }: { events: JungleEvent[]; games: number; walls: boolean }) {
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

  return (
    <div className="jungle-grid">
      <div className="stack">
        <div className="row">
          <Segmented label="Ereignisse" value={type} onChange={setType}
            options={[{ value: "involved", label: "Kills + Assists" }, { value: "death", label: "Tode" }]} />
        </div>
        <div className="sliders">
          <Slider label="Von Minute" value={from} min={0} max={lastMinute} onChange={(v) => {
            setFrom(v);
            if (v > upto) setTo(v);
          }} />
          <Slider label="Bis Minute" value={upto} min={0} max={lastMinute} onChange={(v) => {
            setTo(v);
            if (v < from) setFrom(v);
          }} />
          <Slider label="Punktgröße" value={radius} min={12} max={64} onChange={setRadius} format={(v) => `${v} px`} />
          <Slider label="Intensität" value={intensity} min={0.25} max={2} step={0.05} onChange={setIntensity}
            format={(v) => `${Math.round(v * 100)} %`} />
        </div>
        <div className="map">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="map-layer"><MapBase walls={walls} /></svg>
          <Heat points={shown} rgb={type === "death" ? DEATH_RGB : KILL_RGB} radius={radius} intensity={intensity} />
        </div>
      </div>
      <div className="stack">
        <div className="kpis">
          <div className="kpi">
            <div className="label">{type === "death" ? "Tode" : "Kill-Beteiligungen"} · Min {from}–{upto}</div>
            <div className="value">{shown.length}</div>
            <div className="hint">
              Ø {games ? (shown.length / games).toFixed(1) : "–"} pro Spiel
              {type === "involved" && ` · ${kills} Kills, ${shown.length - kills} Assists`}
            </div>
          </div>
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
      </div>
    </div>
  );
}

const netEdges = edges();

function PathView({ paths, maxMinutes, walls }: { paths: JunglePath[]; maxMinutes: number; walls: boolean }) {
  const { champion } = useGameData();
  const [minutes, setMinutes] = useState(Math.min(6, maxMinutes));
  const [side, setSide] = useState<"all" | Side>("all");
  const [realistic, setRealistic] = useState(true);
  const [showNet, setShowNet] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const shown = paths.filter((p) => side === "all" || p.side === side);
  const hovered = shown.find((p) => p.match_id === hover);

  const starts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of shown) {
      const first = p.points[1];
      if (first) counts.set(nearestCamp(first, p.side), (counts.get(nearestCamp(first, p.side)) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [shown]);

  return (
    <div className="jungle-grid">
      <div className="stack">
        <div className="row">
          <Segmented label="Seite" value={side} onChange={setSide}
            options={[{ value: "all", label: "Beide Seiten" }, { value: "blue", label: "Blau" }, { value: "red", label: "Rot" }]} />
        </div>
        <div className="sliders">
          <Slider label="Bis Minute" value={minutes} min={2} max={maxMinutes} onChange={setMinutes} />
        </div>
        <div className="row small">
          <label className="check">
            <input type="checkbox" checked={realistic} onChange={(e) => setRealistic(e.target.checked)} />
            <span>Realistische Laufwege (kürzester Weg durch Jungle und Fluss)</span>
          </label>
          <label className="check">
            <input type="checkbox" checked={showNet} onChange={(e) => setShowNet(e.target.checked)} />
            <span>Wegenetz einblenden</span>
          </label>
        </div>
        <div className="map">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="map-layer" onMouseLeave={() => setHover(null)}>
            <MapBase walls={walls} />
            {showNet && (
              <g className="nav-net">
                {netEdges.map(([a, b], i) => <line key={i} x1={px(a[0])} y1={py(a[1])} x2={px(b[0])} y2={py(b[1])} />)}
              </g>
            )}
            {shown.map((p) => {
              // ab Minute 1: der Weg aus dem Brunnen würde die eigentliche Route überdecken
              const pts = p.points.slice(1, minutes + 1).filter((pt): pt is [number, number] => !!pt);
              const line = (realistic ? interpolate(pts as Point[]).path : pts)
                .map(([x, y]) => `${px(x)},${py(y)}`).join(" ");
              const dim = hover && hover !== p.match_id;
              return (
                <g key={p.match_id} opacity={dim ? 0.12 : hover ? 1 : 0.6} onMouseEnter={() => setHover(p.match_id)}
                  style={{ cursor: "pointer" }}>
                  <polyline points={line} fill="none" stroke="transparent" strokeWidth={12} />
                  <polyline points={line} fill="none"
                    stroke={SIDE_COLOR[p.side]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                  {pts.map(([x, y], i) => (
                    <circle key={i} cx={px(x)} cy={py(y)} r={i === pts.length - 1 ? 5 : 3}
                      fill={SIDE_COLOR[p.side]} stroke="#07090d" strokeWidth={2} />
                  ))}
                  {hover === p.match_id && pts.map(([x, y], i) => (
                    <text key={`t${i}`} x={px(x) + 7} y={py(y) - 6} className="map-label">{i + 1}</text>
                  ))}
                </g>
              );
            })}
          </svg>
        </div>
        <div className="muted small">
          {hovered
            ? <>{dt(hovered.date)} · {champion(hovered.champion_id).name} · {hovered.side === "blue" ? "Blau" : "Rot"} · {hovered.win ? "Sieg" : "Niederlage"}</>
            : <>Position je Minute; Linie überfahren für Details (Zahlen = Minute).</>}
        </div>
      </div>
      <div className="stack">
        <div className="row small">
          <span className="legend-dot" style={{ background: SIDE_COLOR.blue }} /> Blaue Seite
          <span className="legend-dot" style={{ background: SIDE_COLOR.red }} /> Rote Seite
        </div>
        <table className="data">
          <thead><tr><th className="left">Start (Minute 1)</th><th>Spiele</th><th>Anteil</th></tr></thead>
          <tbody>
            {starts.map(([name, n]) => (
              <tr key={name}><td className="left">{name}</td><td>{n}</td><td>{Math.round((n / shown.length) * 100)}%</td></tr>
            ))}
            {!starts.length && <tr><td className="left muted" colSpan={3}>Keine Positionsdaten.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
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

  return (
    <section className="card stack">
      <div className="row between">
        <div>
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
        </div>
        <Segmented label="Ansicht" value={view} onChange={setView}
          options={[{ value: "heat", label: "Gank-Heatmap" }, { value: "path", label: "Pathing" }]} />
      </div>
      {jungle.players.length > 1 && (
        <div className="chips">
          {jungle.players.map((p) => (
            <button type="button" key={p.puuid} className={`chip${active(p.puuid) ? " on" : ""}`}
              aria-pressed={active(p.puuid)}
              onClick={() => setOff((s) => {
                const next = new Set(s);
                if (next.has(p.puuid)) next.delete(p.puuid);
                else next.add(p.puuid);
                return next;
              })}>
              <span className="dot" />{p.name} <span className="muted small">{p.games}×</span>
            </button>
          ))}
        </div>
      )}
      <MapContext.Provider value={settings}>
        {view === "heat"
          ? <HeatView events={events} games={games} walls={walls} />
          : <PathView paths={paths} maxMinutes={jungle.path_minutes} walls={walls} />}
      </MapContext.Provider>
      <div className="row small">
        <label className="check">
          <input type="checkbox" checked={walls} onChange={(e) => setWalls(e.target.checked)} />
          <span>Wände einblenden (angenäherte Umrisse)</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={calibrate} onChange={(e) => setCalibrate(e.target.checked)} />
          <span>Kartenabgleich: echtes Kartenbild mit Wand-Umrissen</span>
        </label>
        <InfoTip>
          Gestrichelte Umrisse = angenommene Wände, gepunktete Linien („Wegenetz“ im Pathing) = angenommene Wege.
          Liegen sie neben den echten Wänden, bitte einen Screenshot schicken.
        </InfoTip>
      </div>
      {calibrate && (
        <div className="stack">
          <div className="sliders">
            <Slider label="Kartenbild" value={imageOpacity} min={0} max={1} step={0.05} onChange={setImageOpacity}
              format={(v) => `${Math.round(v * 100)} %`} />
          </div>
          {image === "failed" && (
            <p className="muted small">
              Das Kartenbild von Riot (Data Dragon) konnte nicht geladen werden – ohne Internetzugang ist kein Abgleich möglich.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
