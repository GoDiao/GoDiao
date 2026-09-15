#!/usr/bin/env python3
"""Build the employer logo tiles used by the Experience table.

Run once; the output is committed. Re-run only if a logo changes.

    python3 scripts/build_logo_tiles.py

Each tile is a fixed-size SVG: a white rounded plate with the logo scaled to
fit and centred. Two reasons for the plate rather than bare logos:

  * GitHub renders a README in the viewer's own theme. Huawei's wordmark is
    black and Infineon's is dark blue, so on the dark theme both would sit
    invisible against a near-black page.
  * The source logos run from 1:1 to 3:1 in aspect ratio. At a fixed height
    they would render between 28px and 82px wide and the column would look
    ragged; a fixed plate keeps every row identical.

Sources are each company's own published logo (Wikimedia Commons for
Infineon), used to identify past employers.
"""

import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "profile" / "logos"

# Tile geometry, in SVG user units.
TILE_W, TILE_H, RADIUS, PAD = 132, 44, 6, 7
# Raster width for SVG sources before embedding; 3x keeps the plate crisp on
# HiDPI without pushing the committed file into the hundreds of kilobytes.
RASTER_W = TILE_W * 3

SOURCES = [
    ("garena", "https://official.garena.com/sg/v1/assets/garena_logo_horizontal.svg"),
    # The horizontal lockup, not the stacked logo_400x200: at 2:1 the stacked
    # one is height-constrained on this plate and renders visibly smaller
    # than its neighbours.
    ("huawei", "https://www.huawei.com/-/media/hcomponent-header/1.0.1.20260908162100/component/img/huawei_logo.png"),
    ("kingdee", "https://global.kingdee.com/sg/wp-content/uploads/sites/4/2025/07/logo-scaled.png"),
    ("infineon", "https://upload.wikimedia.org/wikipedia/commons/b/bb/Infineon-Logo.svg"),
]

UA = "profile-readme-logo-builder/1.0"


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    if dest.stat().st_size < 500:
        sys.exit("{} came back too small to be a logo ({} bytes)".format(url, dest.stat().st_size))


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        sys.exit("{} failed: {}".format(cmd[0], proc.stderr.decode()[:300]))


def svg_geometry(markup):
    """Intrinsic width and height of an SVG, from viewBox or width/height."""
    root = re.search(r"<svg\b[^>]*>", markup, re.I)
    if not root:
        sys.exit("no <svg> element found")
    attrs = root.group(0)
    box = re.search(r'viewBox\s*=\s*"([^"]+)"', attrs, re.I)
    if box:
        nums = [float(v) for v in re.split(r"[ ,]+", box.group(1).strip())]
        if len(nums) == 4:
            return nums[2], nums[3]
    size = []
    for axis in ("width", "height"):
        found = re.search(axis + r'\s*=\s*"([\d.]+)', attrs, re.I)
        if not found:
            sys.exit("SVG has neither viewBox nor numeric " + axis)
        size.append(float(found.group(1)))
    return size[0], size[1]


def svg_body(markup):
    """Inner markup plus the root presentation attributes that must ride along.

    The logo is inlined rather than rasterised: qlmanage renders SVG onto an
    opaque white square, which defeated the transparent-margin trim and left
    Garena's mark a speck in the middle of its plate.
    """
    root = re.search(r"<svg\b[^>]*>", markup, re.I)
    body = markup[root.end():]
    body = re.sub(r"</svg\s*>\s*$", "", body.strip(), flags=re.I)
    carried = []
    for attr in ("fill", "stroke", "fill-rule", "clip-rule"):
        found = re.search(attr + r'\s*=\s*"([^"]*)"', root.group(0), re.I)
        if found:
            carried.append('{}="{}"'.format(attr, found.group(1)))
    return body, " ".join(carried)


def png_size(path):
    proc = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        capture_output=True, text=True,
    )
    dims = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            key, _, value = line.strip().partition(":")
            if key in ("pixelWidth", "pixelHeight"):
                dims[key] = int(value)
    return dims["pixelWidth"], dims["pixelHeight"]


def trim_transparent(path, work, name):
    """Crop fully transparent margins so every logo fills its plate evenly."""
    out = work / ("trim_" + name + ".png")
    script = (
        'import sys;from PIL import Image;'
        'i=Image.open(sys.argv[1]).convert("RGBA");b=i.split()[3].getbbox();'
        'i.crop(b).save(sys.argv[2]) if b else i.save(sys.argv[2])'
    )
    proc = subprocess.run([sys.executable, "-c", script, str(path), str(out)],
                          capture_output=True)
    return out if proc.returncode == 0 and out.exists() else path


def downscale(path, work, name):
    """Cap the embedded raster at the plate's 3x width.

    The Kingdee source is 2560px wide; embedding it untouched made a 111 KB
    tile for a logo that renders 118px across.
    """
    w, _ = png_size(path)
    if w <= RASTER_W:
        return path
    out = work / ("small_" + name + ".png")
    run(["sips", "-Z", str(RASTER_W), "--out", str(out), str(path)])
    return out


def fit(w, h):
    """Scale and centre a w x h logo inside the plate's padded area."""
    scale = min((TILE_W - 2 * PAD) / w, (TILE_H - 2 * PAD) / h)
    draw_w, draw_h = w * scale, h * scale
    return scale, (TILE_W - draw_w) / 2, (TILE_H - draw_h) / 2, draw_w, draw_h


def plate(name, inner):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="{tw}" height="{th}" viewBox="0 0 {tw} {th}" role="img" aria-label="{n}">'
        "<title>{n}</title>"
        '<rect width="{tw}" height="{th}" rx="{r}" fill="#ffffff"/>'
        "{inner}</svg>"
    ).format(tw=TILE_W, th=TILE_H, r=RADIUS, n=name, inner=inner)


def tile_from_svg(name, markup):
    w, h = svg_geometry(markup)
    scale, x, y, _, _ = fit(w, h)
    body, carried = svg_body(markup)
    group = '<g transform="translate({x:.3f},{y:.3f}) scale({s:.5f})" {c}>{b}</g>'.format(
        x=x, y=y, s=scale, c=carried, b=body
    )
    return plate(name, group)


def tile_from_png(name, png):
    w, h = png_size(png)
    _, x, y, draw_w, draw_h = fit(w, h)
    data = base64.b64encode(png.read_bytes()).decode()
    image = (
        '<image x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        'xlink:href="data:image/png;base64,{d}"/>'
    ).format(x=x, y=y, w=draw_w, h=draw_h, d=data)
    return plate(name, image)


def main():
    if not shutil.which("sips"):
        sys.exit("needs macOS sips")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="logo-tiles-"))
    try:
        for name, url in SOURCES:
            src = work / (name + os.path.splitext(url.split("?")[0])[1])
            fetch(url, src)
            if src.suffix.lower() == ".svg":
                body = tile_from_svg(name, src.read_text(encoding="utf-8"))
            else:
                png = downscale(trim_transparent(src, work, name), work, name)
                body = tile_from_png(name, png)
            out = OUT_DIR / (name + ".svg")
            out.write_text(body, encoding="utf-8")
            print("wrote {} ({:,} bytes)".format(out.name, out.stat().st_size))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
