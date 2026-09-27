"""Erzeugt src/lib/navgridData.ts (begehbare Fläche von Summoner's Rift) aus einem Kartenbild.

    python scripts/build_navgrid.py <karte.png> --simple --x-left 24.5 --x-right 274 --y-top 23.5 --y-bottom 275
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
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

MX, MY, N = 14870, 14980, 150
LANE_LOW, LANE_HIGH_X, LANE_HIGH_Y = 1250, 14870 - 1250, 13800


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--x-left", type=float, default=152)
    ap.add_argument("--x-right", type=float, default=487)
    ap.add_argument("--y-top", type=float, default=12)
    ap.add_argument("--y-bottom", type=float, default=318)
    ap.add_argument("--simple", action="store_true", help="schematische Karte (dunkel = Wand)")
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

    largest = max(components(grid), key=len)          # nur die zusammenhängende Spielfläche
    grid = np.zeros_like(grid)
    for y, x in largest:
        grid[y, x] = True
    for cells in list(components(~grid)):             # kleine Wandflecken (Lichter, Effekte) füllen
        if len(cells) < 5:
            for y, x in cells:
                grid[y, x] = True

    bits = np.packbits(grid.astype(np.uint8).ravel())
    data = base64.b64encode(bits.tobytes()).decode()
    out = Path(__file__).resolve().parents[1] / "src" / "lib" / "navgridData.ts"
    out.write_text(
        "// Automatisch erzeugt von scripts/build_navgrid.py – nicht von Hand bearbeiten.\n"
        f"/** Rastergröße (Zellen je Seite); Zeile 0 = oben (rote Seite), Spalte 0 = links */\n"
        f"export const GRID_SIZE = {N};\n"
        "/** Begehbar-Bits, zeilenweise, base64 */\n"
        f'export const GRID_BITS = "{data}";\n', encoding="utf-8")
    print(f"{grid.sum()} von {N * N} Zellen begehbar -> {out}")


if __name__ == "__main__":
    main()
