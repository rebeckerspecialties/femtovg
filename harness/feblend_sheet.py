#!/usr/bin/env python3
"""Evidence sheet for the feBlend PR: for each named file, one row per zoom
with master / this PR / Chromium 131 / diff before / diff after (pixels
differing by more than the threshold in red), plus a zoomed crop row of the
region where the two renders differ most.
  sheet.py OUT.png NAME[,NAME...] ZOOMS THRESHOLD [BEFORE_LABEL]
A NAME is `file`, `dir:file` (before_/after_/chr_ files in that directory
under the blend work dir) and may end in `@ZOOM` to use that zoom alone."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
B = '/Users/matt/src/femtovg-wt/blend'
out, names, zooms, thr = sys.argv[1], sys.argv[2].split(','), [z for z in sys.argv[3].split(',')], int(sys.argv[4])
before_label = sys.argv[5] if len(sys.argv) > 5 else 'master 1334764'
font = ImageFont.load_default()
def load(path): return Image.open(path).convert('RGB')
def diff(a, b):
    d = (np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2) > thr)
    o = np.asarray(a).copy(); o[d] = [255, 0, 0]; return Image.fromarray(o), d
cols = [before_label, 'this PR', 'Chromium 131', f'before vs Chromium (>{thr}/255 red)', f'this PR vs Chromium (>{thr}/255 red)']
W, H = 460, 260
label_w = 150
rows = []
for name in names:
    name, own_zoom = name.split('@') if '@' in name else (name, None)
    for z in ([own_zoom] if own_zoom else zooms):
        if ':' in name:
            d, n = name.split(':', 1)
            before = load(f'{B}/{d}/before_{n}_{z}.ppm'); after = load(f'{B}/{d}/after_{n}_{z}.ppm'); chr_ = load(f'{B}/{d}/chr_{n}_{z}.png')
            name = f'{d}/{n}'
        else:
            before = load(f'{B}/before/{name}_{z}.ppm'); after = load(f'{B}/after/{name}_{z}.ppm'); chr_ = load(f'{B}/refs/chr_{name}_{z}.png')
        db, mb = diff(before, chr_); da, ma = diff(after, chr_)
        rows.append((f'{name} @{z}x', [before, after, chr_, db, da], f'{mb.mean()*100:.2f} % -> {ma.mean()*100:.2f} %'))
        # crop: the 96x64 window where this PR fixes the most pixels (before
        # wrong, after right), falling back to where before differs most
        fixed = mb & ~ma
        best = None
        for y in range(0, H - 64, 8):
            for x in range(0, W - 96, 8):
                n = (fixed[y:y+64, x:x+96].sum(), mb[y:y+64, x:x+96].sum())
                if best is None or n > best[0]: best = (n, x, y)
        _, x, y = best
        S = 3
        crops = [im.crop((x, y, x + 96, y + 64)).resize((96 * S, 64 * S), Image.NEAREST) for im in (before, after, chr_, db, da)]
        rows.append((f'{name} @{z}x crop ({x},{y})', crops, ''))
cw = max(im.width for r in rows for im in r[1]); ch = max(im.height for r in rows for im in r[1])
sheet = Image.new('RGB', (label_w + 5 * (cw + 6), 18 + sum(max(im.height for im in r[1]) + 8 for r in rows)), 'white')
d = ImageDraw.Draw(sheet)
for i, c in enumerate(cols): d.text((label_w + i * (cw + 6) + 2, 3), c, fill='black', font=font)
yy = 18
for label, ims, note in rows:
    d.text((4, yy + 2), label, fill='black', font=font)
    if note: d.text((4, yy + 16), note, fill=(160, 0, 0), font=font)
    for i, im in enumerate(ims):
        sheet.paste(im, (label_w + i * (cw + 6), yy))
    yy += max(im.height for im in ims) + 8
sheet.save(out); print('sheet', sheet.size)
