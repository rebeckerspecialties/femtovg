#!/usr/bin/env python3
"""Evidence sheet with red diffs: diffsheet.py OUT.png REF.png 'label=path' ... [--crop x0,y0,x1,y1] [--zoom N] [--thr 8]
The first panel is the reference; every other panel is followed by its diff against it (pixels beyond thr/255 in red)."""
import sys
import numpy as np
from PIL import Image, ImageDraw
args = sys.argv[1:]; out = args.pop(0); ref_path = args.pop(0); crop = None; zoom = 1; thr = 8
for flag, cast in (('--crop', lambda v: tuple(int(x) for x in v.split(','))), ('--zoom', int), ('--thr', int)):
    while flag in args:
        i = args.index(flag); val = cast(args[i + 1]); del args[i:i + 2]
        crop, zoom, thr = (val, zoom, thr) if flag == '--crop' else (crop, val, thr) if flag == '--zoom' else (crop, zoom, val)
def load(p):
    im = Image.open(p).convert('RGB')
    return im.crop(crop) if crop else im
ref = load(ref_path)
cells = [('Chromium 131', ref)]
for spec in args:
    label, path = spec.split('=', 1); im = load(path)
    d = np.abs(np.asarray(im, dtype=np.int16) - np.asarray(ref, dtype=np.int16)).max(axis=2) > thr
    o = np.asarray(im).copy(); o[d] = [255, 0, 0]
    cells.append((label, im)); cells.append((f'{label} vs Chromium ({100 * d.mean():.2f} % red)', Image.fromarray(o)))
if zoom > 1:
    cells = [(l, im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)) for l, im in cells]
w, h = cells[0][1].size
sheet = Image.new('RGB', (len(cells) * (w + 10) - 10, h + 18), 'white'); d = ImageDraw.Draw(sheet)
for i, (label, im) in enumerate(cells):
    d.text((i * (w + 10) + 2, 2), label, fill='black'); sheet.paste(im, (i * (w + 10), 18))
sheet.save(out); print(out, sheet.size)
