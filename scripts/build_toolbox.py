#!/usr/bin/env python3
"""Build the technology icon row used by the Toolbox section.

Run once; the output is committed. Re-run only when TOOLS changes.

    python3 scripts/build_toolbox.py

This exists so the README does not hot-link a shared icon renderer. The row
used to come from skillicons.dev, which contradicted the rule the card
generator already follows: nothing on this page should depend on a third-party
service staying up or staying unmetered.

Icon geometry and brand colours come from Simple Icons, fetched at build time
and embedded in a single SVG. Simple Icons ships every glyph on a 24x24 grid
with no fill attribute, so each path takes the brand hex directly.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "profile" / "toolbox.svg"

CDN = "https://cdn.jsdelivr.net/npm/simple-icons@15"
DATA = CDN + "/data/simple-icons.json"

# (Simple Icons slug, label used for the tooltip). Order is the render order.
TOOLS = [
    ("python", "Python"),
    ("typescript", "TypeScript"),
    ("rust", "Rust"),
    ("cplusplus", "C++"),
    ("pytorch", "PyTorch"),
    ("react", "React"),
    ("tauri", "Tauri"),
    ("fastapi", "FastAPI"),
    ("nodedotjs", "Node.js"),
    ("docker", "Docker"),
    ("kubernetes", "Kubernetes"),
    ("postgresql", "PostgreSQL"),
    ("linux", "Linux"),
    ("git", "Git"),
]

PER_ROW = 7

# Tile geometry, in SVG user units. ICON is the drawn size of the 24x24 glyph.
TILE, GAP, RADIUS, ICON = 52, 12, 10, 26

# The tiles carry no colour of their own. A neutral at low alpha lifts them
# off whichever canvas GitHub is painting -- #f0f0f0 over the light one,
# #1b1e24 over the dark -- so one file serves both themes. This mirrors the
# palette in generate_readme_cards.py; keep the two in step.
NEUTRAL = "#808080"
PANEL_OP = "0.10"
BORDER_OP = "0.30"

# Brand colours that fall off one canvas or the other, replaced by a tone of
# the same brand that holds on both. The bar is roughly 3:1 against #ffffff
# and against #0d1117: an icon is not text, but below about 2:1 the glyph
# stops reading as a shape.
#
#   rust       #000000 is the brand mark and disappeared on dark, so the row
#              already overrode it to #f5f5f5 -- which disappears on light.
#              #CE422B is Rust's own orange: 4.73:1 and 4.00:1.
#   linux      #FCC624 is 1.59:1 on white. Darkened to 3.25:1, still Tux.
#   react      #61DAFB is 1.62:1 on white. #087EA4 is React's own darker
#              brand blue, 4.64:1 and 4.08:1.
#   tauri      #24C8D8 is 2.03:1 on white. Darkened to 3.04:1.
#   nodedotjs  unchanged; it was already the brand's light-canvas green.
OVERRIDES = {
    "rust": "#CE422B",
    "linux": "#B8860B",
    "react": "#087EA4",
    "tauri": "#1AA3B0",
    "nodedotjs": "#5fa04e",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-toolbox"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def main():
    try:
        index = {row["slug"]: row for row in json.loads(fetch(DATA))}
    except urllib.error.URLError as err:
        sys.exit("cannot reach Simple Icons: {}".format(err))

    rows = (len(TOOLS) + PER_ROW - 1) // PER_ROW
    width = PER_ROW * TILE + (PER_ROW - 1) * GAP
    height = rows * TILE + (rows - 1) * GAP

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" role="img" aria-label="Technology toolbox">'.format(
            w=width, h=height
        )
    ]

    for position, (slug, label) in enumerate(TOOLS):
        if slug not in index:
            sys.exit("unknown Simple Icons slug: {}".format(slug))
        colour = OVERRIDES.get(slug, "#" + index[slug]["hex"])

        svg = fetch("{}/icons/{}.svg".format(CDN, slug))
        paths = re.findall(r"<path\b[^>]*\bd=\"([^\"]+)\"", svg)
        if not paths:
            sys.exit("no path data in {}.svg".format(slug))

        col, row = position % PER_ROW, position // PER_ROW
        x = col * (TILE + GAP)
        y = row * (TILE + GAP)
        # Centre the 24-unit glyph inside the tile at the drawn ICON size.
        scale = ICON / 24.0
        ox = x + (TILE - ICON) / 2.0
        oy = y + (TILE - ICON) / 2.0

        parts.append(
            '<g><title>{t}</title>'
            '<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="{r}" '
            'fill="{n}" fill-opacity="{p}" stroke="{n}" '
            'stroke-opacity="{b}" stroke-width="1"/>'.format(
                t=label, x=x, y=y, s=TILE, r=RADIUS,
                n=NEUTRAL, p=PANEL_OP, b=BORDER_OP
            )
        )
        parts.append(
            '<g transform="translate({ox:.2f},{oy:.2f}) scale({s:.5f})" '
            'fill="{c}">'.format(ox=ox, oy=oy, s=scale, c=colour)
        )
        for d in paths:
            parts.append('<path d="{}"/>'.format(d))
        parts.append("</g></g>")

    parts.append("</svg>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(parts), encoding="utf-8")
    print("wrote", OUT.relative_to(OUT.parent.parent), len(TOOLS), "icons")


if __name__ == "__main__":
    main()
