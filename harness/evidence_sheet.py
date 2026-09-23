#!/usr/bin/env python3
"""Evidence sheet from full-resolution renders (FRAME_W=1840 FRAME_H=1040
BOX=800 BOX_X=520 BOX_Y=120, zoom 1): per row the frame at half size, then
a 1:1 crop of the 480x270 window where the PR fixes the most pixels.
Columns: before, this PR, Chromium 131, before vs Chromium, this PR vs
Chromium (pixels beyond THRESHOLD/255 in red).
  evidence_sheet.py OUT.png DIR BEFORE_LABEL THRESHOLD NAME[:PREFIX]...
Files: DIR/{PREFIX}before_NAME.ppm, DIR/{PREFIX}after_NAME.ppm, DIR/chr_NAME.png."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
out, base, before_label, thr = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
font = ImageFont.load_default()
CW, CH = 480, 270
def load(p): return Image.open(p).convert('RGB')
def diff(a, b):
    d = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2) > thr
    o = np.asarray(a).copy(); o[d] = [255, 0, 0]; return Image.fromarray(o), d
rows = []
for spec in sys.argv[5:]:
    name, prefix = (spec.split(':') + [''])[:2]
    before, after, chr_ = load(f'{base}/{prefix}before_{name}.ppm'), load(f'{base}/{prefix}after_{name}.ppm'), load(f'{base}/chr_{name}.png')
    db, mb = diff(before, chr_); da, ma = diff(after, chr_)
    W, H = before.size
    half = [im.resize((W // 2, H // 2), Image.LANCZOS) for im in (before, after, chr_, db, da)]
    rows.append((f'{name}', half, f'{mb.mean()*100:.2f} % -> {ma.mean()*100:.2f} % of pixels beyond {thr}/255'))
    fixed = mb & ~ma; best = None
    for y in range(0, H - CH, 30):
        for x in range(0, W - CW, 40):
            n = (fixed[y:y+CH, x:x+CW].sum(), mb[y:y+CH, x:x+CW].sum())
            if best is None or n > best[0]: best = (n, x, y)
    _, x, y = best
    rows.append((f'{name} 1:1 at ({x},{y})', [im.crop((x, y, x + CW, y + CH)) for im in (before, after, chr_, db, da)], ''))
cols = [before_label, 'this PR', 'Chromium 131', f'before vs Chromium', f'this PR vs Chromium']
cw = max(im.width for r in rows for im in r[1]); label_w = 170
sheet = Image.new('RGB', (label_w + 5 * (cw + 8), 20 + sum(max(im.height for im in r[1]) + 10 for r in rows)), 'white')
d = ImageDraw.Draw(sheet)
for i, c in enumerate(cols): d.text((label_w + i * (cw + 8) + 2, 4), c, fill='black', font=font)
yy = 20
for label, ims, note in rows:
    d.text((4, yy + 2), label, fill='black', font=font)
    if note: d.text((4, yy + 16), note, fill=(160, 0, 0), font=font)
    for i, im in enumerate(ims): sheet.paste(im, (label_w + i * (cw + 8), yy))
    yy += max(im.height for im in ims) + 10
sheet.save(out); print('sheet', sheet.size)
