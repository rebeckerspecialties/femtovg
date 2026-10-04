#!/usr/bin/env python3
"""Clip-edge evidence from a corpus run (CORPUS_RUN_OUT, frames kept with accuracy.py png=DIR): one row per
name:framing, a window on the clip's edge (where the two builds differ most toward the upper right) magnified with
nearest-neighbour: before | after | Chromium | Firefox, and the after-build's
difference from each browser. The caption has px > 20/255 of the whole frame for both builds against both browsers and
the browsers against each other. A fourth field puts the window's centre at a frame pixel instead.
  clip_sheet.py OUT.png <before> <after> name:framing[:WxH[:CX,CY]] ..."""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import OUT as R
files = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
font = lambda s: ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', s)
out, before, after = sys.argv[1:4]
def frame(build, k, fr):
    for d in ('png_wpt', 'png_nyt', 'png'):  # the directories accuracy.py png= was given
        p = f'{R}/{d}/{build}_{k}_{fr}.png'
        if os.path.exists(p): return Image.open(p).convert('RGB')
    raise SystemExit(f'no frame {build} {k} {fr}')
def pct(a, b): return 100 * (np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2) > 20).mean()
def heat(a, b):
    d = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    h = np.full(d.shape + (3,), 255, np.uint8); h[(d > 0) & (d <= 20)] = [255, 190, 110]; h[d > 20] = [220, 30, 30]
    return Image.fromarray(h)
rows = []
for spec in sys.argv[4:]:
    parts = spec.split(':'); name, fr = parts[0], parts[1]
    cw, ch = (int(v) for v in parts[2].split('x')) if len(parts) > 2 else (44, 30)
    k = [k for k in files if k.endswith('__' + name)][0]
    b, a = frame(before, k, fr), frame(after, k, fr)
    c = Image.open(f'{R}/refs/chr_{k}_{fr}.png').convert('RGB'); f = Image.open(f'{R}/refs/ff_{k}_{fr}.png').convert('RGB')
    d = np.abs(np.asarray(b, dtype=np.int16) - np.asarray(a, dtype=np.int16)).max(axis=2)
    ys, xs = np.nonzero(d > 0)
    if len(xs) == 0: raise SystemExit(f'{name} {fr}: the builds do not differ')
    i = np.argmax(xs - ys); cx, cy = int(xs[i]), int(ys[i])
    if len(parts) > 3: cx, cy = (int(v) for v in parts[3].split(','))
    W, H = b.size
    x0 = min(max(cx - cw // 2, 0), W - cw); y0 = min(max(cy - ch // 2, 0), H - ch); box = (x0, y0, x0 + cw, y0 + ch)
    s = 6
    panels = [im.crop(box).resize((cw * s, ch * s), Image.NEAREST) for im in (b, a, c, f, heat(a, c), heat(a, f))]
    label = (f'{name} at {fr}: px > 20/255 of the frame  vs Chromium {pct(b, c):.2f} % -> {pct(a, c):.2f} %,  vs Firefox {pct(b, f):.2f} % -> {pct(a, f):.2f} %,'
             f'  Chromium vs Firefox {pct(c, f):.2f} %')
    rows.append((label, panels)); print(label)
gap, cap = 8, 34
pw, ph = rows[0][1][0].size
width = max(len(r[1]) for r in rows) * (pw + gap) + gap
sheet = Image.new('RGB', (width, sum(r[1][0].size[1] + cap + gap for r in rows) + gap), 'white'); dr = ImageDraw.Draw(sheet); y = gap
names = ['master (stencil clip)', 'this PR', 'Chromium 131', 'Firefox', 'PR vs Chromium', 'PR vs Firefox']
for label, panels in rows:
    dr.text((gap, y), label, fill=(0, 0, 0), font=font(13)); x = gap
    for p, n in zip(panels, names):
        dr.text((x, y + 18), n, fill=(90, 90, 90), font=font(11)); sheet.paste(p, (x, y + cap)); dr.rectangle([x - 1, y + cap - 1, x + p.size[0], y + cap + p.size[1]], outline=(200, 200, 200)); x += p.size[0] + gap
    y += panels[0].size[1] + cap + gap
sheet.save(out); print(out, sheet.size)
