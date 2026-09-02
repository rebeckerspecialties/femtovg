#!/usr/bin/env python3
"""Build a Chromium/Firefox reference page for one SVG at one pivot zoom.

The page reproduces the femtovg harness framing exactly: a 460x260 canvas,
pivot zoom about (230,130), then the SVG fitted into a 200x200 box at (130,30)
with xMinYMin meet - so femtovg's `translate(230,130) scale(s) translate(-230,-130);
translate(130,30) scale(200/max(w,h))` and the browser land on the same pixels.

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
if vb:
    vb = vb.group(1)
else:  # no viewBox: use width/height as the user space
    w = re.search(r'width="([\d.]+)', attrs).group(1); h = re.search(r'height="([\d.]+)', attrs).group(1)
    vb = f"0 0 {w} {h}"
# Carry root presentation attributes (fill="none" etc.) onto the nested svg -
# dropping them once produced a 48% false diff.
keep = " ".join(a for a in re.findall(r'\b(?:fill|stroke|fill-rule|opacity|style)="[^"]*"', attrs))
print(f'''<!doctype html><body style="margin:0;background:#fff">
<svg width="460" height="260" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<g transform="translate(230,130) scale({scale}) translate(-230,-130)"><svg x="130" y="30" width="200" height="200" viewBox="{vb}" preserveAspectRatio="xMinYMin meet" {keep}>
{inner}
</svg></g></svg>''')
