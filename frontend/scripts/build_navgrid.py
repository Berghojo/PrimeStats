"""Erzeugt src/lib/navgridData.ts (begehbare Fläche von Summoner's Rift) aus einem Kartenbild.

    python scripts/build_navgrid.py <karte.png> --simple --base-walls --x-left 24.5 --x-right 274 --y-top 23.5 --y-bottom 275
    python scripts/build_navgrid.py <screenshot.jpg> --x-left 152 --x-right 487 --y-top 12 --y-bottom 318

Das Bild ist eine Draufsicht (blau unten links). ``--simple``: schematische Karte, alles Nicht-Dunkle
(Wege, Fluss, Basen) ist begehbar. Sonst: gerenderte Karte, Wände = dunkle Baumwände, begehbar =
heller Boden und Wasser. Ausgerichtet wird über die Mitten der äußeren Lanes (Pixel im Bild) – im Spiel liegen
Top-/Botlane bei x bzw. y ≈ 1250 und 13 800 (Turmpositionen). Weil die Karte punktsymmetrisch ist, wird
jede Zelle mit ihrer gespiegelten Zelle gemittelt; das glättet Lichter und Effekte im Bild.
Benötigt: pillow, numpy.
"""

import argparse
import base64
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

MX, MY, N = 14870, 14980, 150
LANE_LOW, LANE_HIGH_X, LANE_HIGH_Y = 1250, 14870 - 1250, 13800


#: Rand der Basisfläche (Abstand zur Kartenecke) je Winkel, gemessen an der schematischen Karte
BASE_EDGE = {10: 5400, 15: 5600, 20: 5450, 25: 5600, 30: 5750, 35: 5850, 40: 5900, 45: 6100, 50: 5900,
             55: 5850, 60: 5800, 65: 5650, 70: 5500, 75: 5650, 80: 5400}
#: Lane-Ausgänge der Basis (Winkel von der Ecke aus) und halbe Breite der Lücke in Spieleinheiten
BASE_EXITS = (12.4, 45.0, 77.6)
EXIT_HALF_WIDTH = 750
BASE_WALL = (-550, 150)   # Mauer von Rand-550 bis Rand+150


def add_base_walls(soft: np.ndarray) -> None:
    """Mauer entlang des Basisrands (beide Basen), offen nur an den drei Lanes."""
    import math
    angles = sorted(BASE_EDGE)
    for j in range(N):
        for i in range(N):
            x, y = MX * (i + 0.5) / N, MY * (1 - (j + 0.5) / N)
            for bx, by in ((x, y), (MX - x, MY - y)):          # blaue Basis, rote Basis (gespiegelt)
                r = math.hypot(bx, by)
                deg = math.degrees(math.atan2(by, bx))
                if not angles[0] <= deg <= angles[-1]:
                    continue
                lo = max(a for a in angles if a <= deg)
                hi = min(a for a in angles if a >= deg)
                edge = BASE_EDGE[lo] if lo == hi else BASE_EDGE[lo] + (BASE_EDGE[hi] - BASE_EDGE[lo]) * (deg - lo) / (hi - lo)
                if not edge + BASE_WALL[0] <= r <= edge + BASE_WALL[1]:
                    continue
                if any(abs(math.radians(deg - ex)) * r < EXIT_HALF_WIDTH for ex in BASE_EXITS):
                    continue
                soft[j, i] = 0.0


def wall_loops(walk: np.ndarray, tolerance: float = 0.9) -> list[list[int]]:
    """Umrisse der Wandflächen als geschlossene Polygone (Gitterpunkte), vereinfacht (Douglas-Peucker).

    Richtung: Wand links der Kante. Zusammen mit fill-rule="evenodd" ergeben die Umrisse (inkl. äußerem
    Rand) genau die Wandflächen; Inseln in Wänden werden zu Löchern.
    """
    n = walk.shape[0]
    wall = np.ones((n + 2, n + 2), bool)
    wall[1:-1, 1:-1] = ~walk
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for r in range(n + 2):
        for c in range(n + 2):
            if not wall[r, c]:
                continue
            if r > 0 and not wall[r - 1, c]:
                add((c + 1, r), (c, r))
            if r < n + 1 and not wall[r + 1, c]:
                add((c, r + 1), (c + 1, r + 1))
            if c > 0 and not wall[r, c - 1]:
                add((c, r), (c, r + 1))
            if c < n + 1 and not wall[r, c + 1]:
                add((c + 1, r + 1), (c + 1, r))

    loops = []
    while edges:
        start = next(iter(edges))
        loop, cur = [start], start
        while True:
            nxt = edges[cur].pop()
            if not edges[cur]:
                del edges[cur]
            if nxt == start:
                break
            loop.append(nxt)
            cur = nxt
            if cur not in edges:
                break
        if len(loop) >= 4:
            loops.append(loop)

    def rdp(points, eps):
        if len(points) < 3:
            return points
        (x0, y0), (x1, y1) = points[0], points[-1]
        dx, dy = x1 - x0, y1 - y0
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        dists = [abs(dy * (x - x0) - dx * (y - y0)) / norm for x, y in points[1:-1]]
        i = int(np.argmax(dists)) + 1
        if dists[i - 1] > eps:
            return rdp(points[: i + 1], eps)[:-1] + rdp(points[i:], eps)
        return [points[0], points[-1]]

    out = []
    for loop in loops:
        # geschlossenen Ring am entferntesten Punktepaar aufteilen und beide Hälften vereinfachen
        far = max(range(len(loop)), key=lambda i: (loop[i][0] - loop[0][0]) ** 2 + (loop[i][1] - loop[0][1]) ** 2)
        a = rdp(loop[: far + 1], tolerance)
        b = rdp(loop[far:] + [loop[0]], tolerance)
        pts = a[:-1] + b[:-1]
        if len(pts) >= 3:
            # Gitterpunkte ohne Rand-Polster (−1)
            out.append([v - 1 for p in pts for v in p])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--x-left", type=float, default=152)
    ap.add_argument("--x-right", type=float, default=487)
    ap.add_argument("--y-top", type=float, default=12)
    ap.add_argument("--y-bottom", type=float, default=318)
    ap.add_argument("--simple", action="store_true", help="schematische Karte (dunkel = Wand)")
    ap.add_argument("--base-walls", action="store_true",
                    help="Basismauern ergänzen (in schematischen Karten ist die Basis eine einheitliche Fläche)")
    args = ap.parse_args()

    a = np.asarray(Image.open(args.image).convert("RGB")).astype(float)
    h, w = a.shape[:2]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if args.simple:
        walk = lum > 55
    else:
        water = (b > r + 25) & (g > r + 10) & (lum > 45)
        walk = (lum > 95) | ((b > 110) & (g > 110) & (lum > 80)) | water

    sx = (args.x_right - args.x_left) / (LANE_HIGH_X - LANE_LOW)
    sy = (args.y_bottom - args.y_top) / (LANE_HIGH_Y - LANE_LOW)

    def to_img(x: float, y: float) -> tuple[float, float]:
        return args.x_left + sx * (x - LANE_LOW), args.y_top + sy * (LANE_HIGH_Y - y)

    soft = np.full((N, N), np.nan)
    for j in range(N):
        for i in range(N):
            xa, ya = to_img(MX * i / N, MY * (1 - j / N))
            xb, yb = to_img(MX * (i + 1) / N, MY * (1 - (j + 1) / N))
            vals = [walk[y, x] for y in range(int(ya), int(np.ceil(yb)) + 1)
                    for x in range(int(xa), int(np.ceil(xb)) + 1) if 0 <= x < w and 0 <= y < h]
            if vals:
                soft[j, i] = np.mean(vals)
    if args.base_walls:
        add_base_walls(soft)
    mir = soft[::-1, ::-1]
    both = np.where(np.isnan(soft), mir, np.where(np.isnan(mir), soft, (soft + mir) / 2))
    grid = np.nan_to_num(both, nan=0.0) > 0.5

    def components(mask):
        seen = np.zeros_like(mask, bool)
        for j in range(N):
            for i in range(N):
                if mask[j, i] and not seen[j, i]:
                    queue, cells = deque([(j, i)]), []
                    seen[j, i] = True
                    while queue:
                        y, x = queue.popleft()
                        cells.append((y, x))
                        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < N and 0 <= xx < N and mask[yy, xx] and not seen[yy, xx]:
                                seen[yy, xx] = True
                                queue.append((yy, xx))
                    yield cells

    # Inseln (z.B. Camp-Lichtungen, deren Eingang schmaler als eine Zelle ist) mit der Hauptfläche
    # verbinden: kürzester Durchbruch durch die Wand. Winzige Inseln (Lichter, Effekte) verwerfen.
    parts = sorted(components(grid), key=len, reverse=True)
    main = np.zeros_like(grid)
    for y, x in parts[0]:
        main[y, x] = True
    for cells in parts[1:]:
        if len(cells) < 6:
            for y, x in cells:
                grid[y, x] = False
            continue
        prev = {c: None for c in cells}
        queue = deque(cells)
        hit = None
        while queue and hit is None:
            y, x = queue.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < N and 0 <= xx < N and (yy, xx) not in prev:
                    prev[(yy, xx)] = (y, x)
                    if main[yy, xx]:
                        hit = (yy, xx)
                        break
                    queue.append((yy, xx))
        if hit is None or len(prev) > N * N:
            continue
        cur = prev[hit]
        while cur is not None and prev[cur] is not None:   # Durchbruch begehbar machen
            grid[cur] = True
            cur = prev[cur]
        for y, x in cells:
            main[y, x] = True
        c = prev[hit]
        while c is not None:
            main[c] = True
            c = prev[c]
    grid = main
    for cells in list(components(~grid)):             # kleine Wandflecken (Lichter, Effekte) füllen
        if len(cells) < 5:
            for y, x in cells:
                grid[y, x] = True

    loops = wall_loops(grid)
    bits = np.packbits(grid.astype(np.uint8).ravel())
    data = base64.b64encode(bits.tobytes()).decode()
    out = Path(__file__).resolve().parents[1] / "src" / "lib" / "navgridData.ts"
    out.write_text(
        "// Automatisch erzeugt von scripts/build_navgrid.py – nicht von Hand bearbeiten.\n"
        f"/** Rastergröße (Zellen je Seite); Zeile 0 = oben (rote Seite), Spalte 0 = links */\n"
        f"export const GRID_SIZE = {N};\n"
        "/** Begehbar-Bits, zeilenweise, base64 */\n"
        f'export const GRID_BITS = "{data}";\n'
        "/** Wandumrisse als Polygone in Gitterpunkten [x0, y0, x1, y1, …] (x = Spalte, y = Zeile von oben) */\n"
        f"export const WALL_LOOPS: number[][] = {json.dumps(loops, separators=(',', ':'))};\n", encoding="utf-8")
    print(f"{grid.sum()} von {N * N} Zellen begehbar, {len(loops)} Wandumrisse -> {out}")


if __name__ == "__main__":
    main()
