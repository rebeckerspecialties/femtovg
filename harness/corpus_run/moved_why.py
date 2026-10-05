#!/usr/bin/env python3
"""moved_why.py KEY_SUBSTRING FRAMING [BUILD...]  - the pixels where the second build is beyond 20/255 of the area
reference and the first is not: how many, their bounding rows/columns, and what each build named has there."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
from common import *
R = OUT
files_ = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
sub, framing = sys.argv[1], sys.argv[2]
builds = sys.argv[3:] or ['master', 'cvh', 'cgl']
key = next((k for k in files_ if k.endswith('__' + sub)), None) or next(k for k in files_ if sub in k)
def frame(b):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{R}/{d}/{b}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    binary, extra = BUILDS[b]; fr, z = FRAMINGS[framing]
    p = f'{R}/png_changed/{b}_{key}_{framing}.png'; ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, files_[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra}, capture_output=True)
    Image.open(ppm).save(p); os.remove(ppm)
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
ref = np.asarray(Image.open(f'{R}/refs/id_{key}_{framing}.png').convert('RGB'), dtype=np.int16)
imgs = {b: frame(b) for b in builds}
far = {b: np.abs(imgs[b] - ref).max(axis=2) > 20 for b in builds}
a, b = builds[0], builds[1]
new = far[b] & ~far[a]; gone = far[a] & ~far[b]
print(f'{key} {framing}: beyond 20/255 of the area: ' + ', '.join(f'{x} {int(far[x].sum())}' for x in builds))
print(f'  {b} far where {a} is not: {int(new.sum())} px; {a} far where {b} is not: {int(gone.sum())} px')
ys, xs = np.nonzero(new)
if len(ys):
    rows = np.bincount(ys, minlength=ref.shape[0]); cols = np.bincount(xs, minlength=ref.shape[1])
    print('  rows with most:', [(int(y), int(rows[y])) for y in np.argsort(rows)[::-1][:4] if rows[y]], 'columns with most:', [(int(x), int(cols[x])) for x in np.argsort(cols)[::-1][:4] if cols[x]])
    for x in builds[2:]:
        print(f'  of those {int(new.sum())} px, {x} is beyond 20/255 on {int((far[x] & new).sum())}')
    refs = {}
    for r in ('chg', 'chr', 'wk', 'ff'):
        p = f'{R}/refs/{r}_{key}_{framing}.png'
        if os.path.exists(p):
            im = np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
            if im.shape == ref.shape:
                refs[r] = im
                print(f'  of those, {r} is beyond 20/255 of the area on {int(((np.abs(im - ref).max(axis=2) > 20) & new).sum())}, within 12/255 of {b} on {int(((np.abs(im - imgs[b]).max(axis=2) <= 12) & new).sum())}')
    i = np.argmax(np.where(new, np.abs(imgs[b] - ref).max(axis=2), 0)); y, x = divmod(int(i), ref.shape[1])
    print(f'  worst at ({x},{y}): area {tuple(int(v) for v in ref[y, x])} ' + ' '.join(f'{n}={tuple(int(v) for v in im[y, x])}' for n, im in {**imgs, **refs}.items()))
