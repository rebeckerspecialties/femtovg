#!/usr/bin/env python3
"""Build a Chromium/Firefox reference page for one SVG at one pivot zoom.

The page reproduces the femtovg harness framing exactly: a 460x260 canvas,
pivot zoom about (230,130) or PIVOT, then the SVG's own viewport (its width and height,
read as usvg reads them) scaled by 200/max(w,h) into a box at (130,30) - so
femtovg's `translate(230,130) scale(s) translate(-230,-130); translate(130,30)
scale(200/max(w,h))` over usvg's tree and the browser land on the same pixels.
The nested svg keeps the file's viewBox and preserveAspectRatio, so a viewBox
whose aspect differs from the viewport's is letterboxed as usvg letterboxes it;
sizing the viewBox itself to the box misplaced 23 corpus files (SVGenius icons
with width="200" height="200" on a 1280x1024 viewBox, ember.svg) by up to 20 px.

Usage: make_ref.py logo.svg 1.3 > ref_logo_1.3.html
Then:  chrome-headless-shell --headless --disable-gpu --screenshot=chr_logo_1.3.png \
         --window-size=460,260 --default-background-color=FFFFFFFF file://$PWD/ref_logo_1.3.html
"""
import re, sys

svg_path, scale = sys.argv[1], sys.argv[2]
t = open(svg_path).read()
# Searchfox "SVG" downloads are HTML viewer pages: recover the XML if needed.
if "<code" in t and "<svg" in t:
    import html
    t = html.unescape(re.sub(r"<[^>]+>", "", "".join(re.findall(r"<code[^>]*>(.*?)</code>", t, re.S))))
    t = t[t.index("<svg"):t.rindex("</svg>") + 6]
m = re.search(r"<svg\b([^>]*)>", t)
attrs, inner = m.group(1), t[m.end():t.rindex("</svg>")]
vb = re.search(r'viewBox="([^"]*)"', attrs)
vb = vb.group(1) if vb else None
vbw, vbh = [float(v) for v in vb.replace(",", " ").split()[2:4]] if vb else (None, None)


def length(name, fallback):
    """The root width/height as usvg resolves it (usvg::parser::converter::convert_size):
    unitless or px as is, a percentage of the viewBox (100 x 100 without one), absolute
    units at 96 dpi, em/ex at the default 12 px font; None when the attribute is missing."""
    m = re.search(rf'\b{name}="\s*([\d.]+(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*"', attrs)
    if not m:
        return fallback
    n, u = float(m.group(1)), m.group(2).lower()
    if u == "%":
        return n / 100 * ((vbw if name == "width" else vbh) if vb else 100.0)
    return n * {"": 1, "px": 1, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96, "pt": 96 / 72, "pc": 16, "em": 12, "ex": 6}.get(u, 1)


w = length("width", None)
h = length("height", None)
# One missing: usvg derives it from the other through the viewBox aspect; both missing: the viewBox
# (100 x 100 without one).
if w is None and h is None:
    w, h = (vbw, vbh) if vb else (100.0, 100.0)
elif w is None:
    w = h * vbw / vbh if vb else 100.0
elif h is None:
    h = w * vbh / vbw if vb else 100.0
if not vb:  # no viewBox: the viewport is the user space
    vb = f"0 0 {w:g} {h:g}"
par = re.search(r'preserveAspectRatio="([^"]*)"', attrs)
par = par.group(1) if par else "xMidYMid meet"
# Carry root presentation attributes (fill="none" etc.) onto the nested svg -
# dropping them once produced a 48% false diff.
keep = " ".join(a for a in re.findall(r'\b(?:fill|stroke|fill-rule|opacity|style)="[^"]*"', attrs))
import os
FW = os.environ.get("FRAME_W", "460"); FH = os.environ.get("FRAME_H", "260")
BOX = os.environ.get("BOX", "200"); BX = os.environ.get("BOX_X", "130"); BY = os.environ.get("BOX_Y", "30")
# The pivot of the zoom: the frame centre, or PIVOT=x,y as the harness reads it.
PX, PY_ = (float(v) for v in os.environ["PIVOT"].split(",")) if os.environ.get("PIVOT") else (float(FW) / 2, float(FH) / 2)
fit = float(BOX) / max(w, h)
print(f'''<!doctype html><body style="margin:0;background:#fff">
<svg width="{FW}" height="{FH}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<g transform="translate({PX:g},{PY_:g}) scale({scale}) translate({-PX:g},{-PY_:g})"><svg x="{BX}" y="{BY}" width="{w * fit:.6g}" height="{h * fit:.6g}" viewBox="{vb}" preserveAspectRatio="{par}" {keep}>
{inner}
</svg></g></svg>''')
