#!/usr/bin/env python3
"""Generate the abstract duotone "plates" used as imagery in v3.

    python tools/make-plates.py

PPS has no photography: the only images the old site carried were of premises
the company has left. Rather than buy stock or fabricate an office, v3 uses a
generated set of technical compositions — node graphs, telemetry traces,
perspective grids — drawn in the brand gradient (red -> purple -> indigo) on a
deep indigo ground.

They occupy the slots a photograph would, read as deliberate brand imagery,
weigh a few kB each, and scale to any size. If real photographs arrive later,
the .plate CSS class in v3 applies the same duotone treatment to them and the
plates can simply be swapped out.

Output is deterministic: the RNG is seeded per plate, so re-running produces
byte-identical files.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "v3" / "assets" / "img" / "plates"

# Brand palette, kept in sync with v3/assets/css/style.css
GROUND = "#141a4a"      # deep indigo
GROUND_2 = "#0e1338"    # deeper, for vignette
RED = "#dc2f2a"
PURPLE = "#8e2f8c"
INDIGO = "#2f3f9e"
TINT = "#8b9bf0"        # light indigo, for hairlines


def head(w: int, h: int, title: str) -> list[str]:
    """Open an SVG with the shared gradient definitions."""
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{title}">',
        "  <defs>",
        '    <linearGradient id="g" x1="0" y1="1" x2="1" y2="0">',
        f'      <stop offset="0" stop-color="{RED}"/>',
        f'      <stop offset=".52" stop-color="{PURPLE}"/>',
        f'      <stop offset="1" stop-color="{INDIGO}"/>',
        "    </linearGradient>",
        '    <linearGradient id="gv" x1="0" y1="0" x2="0" y2="1">',
        f'      <stop offset="0" stop-color="{RED}" stop-opacity=".95"/>',
        f'      <stop offset="1" stop-color="{INDIGO}" stop-opacity=".55"/>',
        "    </linearGradient>",
        '    <radialGradient id="glow" cx="72%" cy="24%" r="62%">',
        f'      <stop offset="0" stop-color="{PURPLE}" stop-opacity=".55"/>',
        f'      <stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/>',
        "    </radialGradient>",
        '    <radialGradient id="glow2" cx="18%" cy="86%" r="58%">',
        f'      <stop offset="0" stop-color="{RED}" stop-opacity=".45"/>',
        f'      <stop offset="1" stop-color="{RED}" stop-opacity="0"/>',
        "    </radialGradient>",
        "  </defs>",
        f'  <rect width="{w}" height="{h}" fill="{GROUND}"/>',
        f'  <rect width="{w}" height="{h}" fill="url(#glow)"/>',
        f'  <rect width="{w}" height="{h}" fill="url(#glow2)"/>',
    ]


def tail() -> list[str]:
    return ["</svg>", ""]


def write(name: str, lines: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text("\n".join(lines), encoding="utf-8")
    print(f"  {name:26s} {len((OUT / name).read_bytes()):>6,} b")


# --------------------------------------------------------------------- plates

def plate_network(w=1200, h=800, seed=11) -> list[str]:
    """Node graph: distributed systems, integration, API surfaces."""
    rnd = random.Random(seed)
    pts = []
    cols, rows = 9, 6
    for i in range(cols):
        for j in range(rows):
            x = (i + .5) * w / cols + rnd.uniform(-34, 34)
            y = (j + .5) * h / rows + rnd.uniform(-30, 30)
            pts.append((x, y))

    out = head(w, h, "Graphe de noeuds")
    out.append(f'  <g stroke="{TINT}" stroke-opacity=".24" stroke-width="1" fill="none">')
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            (x1, y1), (x2, y2) = pts[a], pts[b]
            if math.dist((x1, y1), (x2, y2)) < 165:
                out.append(f'    <line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"/>')
    out.append("  </g>")

    out.append('  <g fill="url(#g)">')
    for (x, y) in pts:
        r = rnd.choice([2.5, 3, 3.5, 5, 7])
        out.append(f'    <circle cx="{x:.0f}" cy="{y:.0f}" r="{r}"/>')
    out.append("  </g>")

    # A few emphasised hubs
    out.append(f'  <g fill="none" stroke="{RED}" stroke-opacity=".7" stroke-width="1.5">')
    for (x, y) in rnd.sample(pts, 5):
        out.append(f'    <circle cx="{x:.0f}" cy="{y:.0f}" r="16"/>')
    out.append("  </g>")
    return out + tail()


def plate_telemetry(w=1200, h=800, seed=23) -> list[str]:
    """Stacked traces: monitoring, non-regression runs, load tests."""
    rnd = random.Random(seed)
    out = head(w, h, "Traces de telemetrie")

    # Baseline grid
    out.append(f'  <g stroke="{TINT}" stroke-opacity=".14" stroke-width="1">')
    for i in range(1, 12):
        x = i * w / 12
        out.append(f'    <line x1="{x:.0f}" y1="0" x2="{x:.0f}" y2="{h}"/>')
    out.append("  </g>")

    bands = 4
    for b in range(bands):
        base = (b + .72) * h / bands
        amp = 46 - b * 7
        pts = []
        v = 0.0
        for i in range(0, w + 1, 12):
            v += rnd.uniform(-1, 1)
            v = max(-1.6, min(1.6, v * .82))
            pts.append((i, base + v * amp + math.sin(i / 90 + b) * amp * .5))
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.0f} {y:.0f}" for i, (x, y) in enumerate(pts))
        area = d + f" L{w} {base + amp * 2.2:.0f} L0 {base + amp * 2.2:.0f} Z"
        out.append(f'  <path d="{area}" fill="url(#gv)" opacity=".{16 + b * 3}"/>')
        out.append(f'  <path d="{d}" fill="none" stroke="url(#g)" stroke-width="{2.4 - b * .35:.1f}"/>')

    return out + tail()


def plate_grid(w=1200, h=800, seed=5) -> list[str]:
    """Perspective grid: infrastructure, platforms, deployment."""
    out = head(w, h, "Grille en perspective")
    hz = h * .34
    vx = w * .52

    out.append(f'  <g stroke="{TINT}" stroke-opacity=".3" stroke-width="1" fill="none">')
    for i in range(-14, 15):
        x = vx + i * w / 11
        out.append(f'    <line x1="{vx:.0f}" y1="{hz:.0f}" x2="{x:.0f}" y2="{h}"/>')
    out.append("  </g>")

    out.append(f'  <g stroke="url(#g)" stroke-width="1.6" fill="none">')
    y = hz
    step = 5.0
    while y < h:
        y += step
        step *= 1.34
        out.append(f'    <line x1="0" y1="{min(y, h):.0f}" x2="{w}" y2="{min(y, h):.0f}"/>')
    out.append("  </g>")

    out.append(f'  <line x1="0" y1="{hz:.0f}" x2="{w}" y2="{hz:.0f}" stroke="{RED}" stroke-width="2"/>')
    return out + tail()


def plate_pipeline(w=1200, h=800, seed=31) -> list[str]:
    """Chevron flow: process, delivery, automation."""
    rnd = random.Random(seed)
    out = head(w, h, "Flux de traitement")
    rows = 7
    for r in range(rows):
        y = (r + .5) * h / rows
        n = 13
        for i in range(n):
            x = i * w / n + (r % 2) * (w / n / 2)
            op = .16 + (i / n) * .6
            sz = 15 + (i / n) * 12
            out.append(
                f'  <path d="M{x:.0f} {y - sz:.0f} L{x + sz * .8:.0f} {y:.0f} L{x:.0f} {y + sz:.0f}" '
                f'fill="none" stroke="url(#g)" stroke-width="2.6" opacity="{op:.2f}"/>'
            )
    # a couple of red accents
    for _ in range(6):
        r = rnd.randrange(rows)
        i = rnd.randrange(4, 13)
        y = (r + .5) * h / rows
        x = i * w / 13 + (r % 2) * (w / 13 / 2)
        out.append(
            f'  <path d="M{x:.0f} {y - 22:.0f} L{x + 18:.0f} {y:.0f} L{x:.0f} {y + 22:.0f}" '
            f'fill="none" stroke="{RED}" stroke-width="3"/>'
        )
    return out + tail()


def plate_matrix(w=1200, h=800, seed=47) -> list[str]:
    """Density field: data, models, volume."""
    rnd = random.Random(seed)
    out = head(w, h, "Champ de densite")
    step = 26
    out.append('  <g fill="url(#g)">')
    for i in range(0, w, step):
        for j in range(0, h, step):
            t = (i / w) * .6 + (1 - j / h) * .4
            if rnd.random() > t * .95:
                continue
            r = .8 + t * 4.2
            out.append(f'    <circle cx="{i + step / 2:.0f}" cy="{j + step / 2:.0f}" r="{r:.1f}"/>')
    out.append("  </g>")
    out.append(f'  <g fill="{RED}">')
    for _ in range(22):
        i = rnd.randrange(0, w, step)
        j = rnd.randrange(0, h, step)
        out.append(f'    <circle cx="{i + step / 2}" cy="{j + step / 2}" r="4"/>')
    out.append("  </g>")
    return out + tail()


def plate_hero(w=1600, h=760, seed=3) -> list[str]:
    """Wide hero composition: fine grid, drifting nodes, gradient sweep."""
    rnd = random.Random(seed)
    out = head(w, h, "Composition abstraite")

    # Fine grid
    out.append(f'  <g stroke="{TINT}" stroke-opacity=".1" stroke-width="1">')
    for i in range(0, w, 48):
        out.append(f'    <line x1="{i}" y1="0" x2="{i}" y2="{h}"/>')
    for j in range(0, h, 48):
        out.append(f'    <line x1="0" y1="{j}" x2="{w}" y2="{j}"/>')
    out.append("  </g>")

    # Sweeping diagonals
    out.append('  <g stroke="url(#g)" fill="none">')
    for i in range(9):
        y0 = h * .1 + i * 42
        out.append(
            f'    <path d="M-40 {y0:.0f} C {w * .3:.0f} {y0 - 120:.0f}, '
            f'{w * .62:.0f} {y0 + 130:.0f}, {w + 40} {y0 - 40:.0f}" '
            f'stroke-width="{1.4 + i * .18:.1f}" opacity="{.5 - i * .04:.2f}"/>'
        )
    out.append("  </g>")

    # Nodes
    pts = [(rnd.uniform(0, w), rnd.uniform(0, h)) for _ in range(46)]
    out.append('  <g fill="url(#g)">')
    for (x, y) in pts:
        out.append(f'    <circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.choice([2, 2.5, 3, 4.5])}"/>')
    out.append("  </g>")

    out.append(f'  <g fill="none" stroke="{RED}" stroke-opacity=".75" stroke-width="1.5">')
    for (x, y) in rnd.sample(pts, 4):
        out.append(f'    <circle cx="{x:.0f}" cy="{y:.0f}" r="19"/>')
    out.append("  </g>")
    return out + tail()


def main() -> int:
    print("Generating v3 plates:")
    write("plate-network.svg", plate_network())
    write("plate-telemetry.svg", plate_telemetry())
    write("plate-grid.svg", plate_grid())
    write("plate-pipeline.svg", plate_pipeline())
    write("plate-matrix.svg", plate_matrix())
    write("plate-hero.svg", plate_hero())
    print(f"\nWritten to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
