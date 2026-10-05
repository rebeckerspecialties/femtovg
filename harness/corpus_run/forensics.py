#!/usr/bin/env python3
"""forensics.py KEY_SUBSTRING FRAMING [BUILD=cv] [REF=id] [threshold=20]  - where a build is beyond the threshold from a
reference: clusters of such pixels (8-connected), with the values every build and reference has at each cluster's worst pixel."""
import json, os, sys
import numpy as np
from PIL import Image
from common import *
R = OUT
os.makedirs(f'{R}/tmp/forensics', exist_ok=True)
files_ = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
sub, framing = sys.argv[1], sys.argv[2]
build = sys.argv[3] if len(sys.argv) > 3 else 'cv'
ref = sys.argv[4] if len(sys.argv) > 4 else 'id'
thr = int(sys.argv[5]) if len(sys.argv) > 5 else 20
key = next((k for k in files_ if k.endswith('__' + sub)), None) or next(k for k in files_ if sub in k)
def frame(b):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{R}/{d}/{b}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    import subprocess
    binary, extra = BUILDS[b]; fr, z = FRAMINGS[framing]
    p = f'{R}/png_changed/{b}_{key}_{framing}.png'; ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, files_[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra}, capture_output=True)
    Image.open(ppm).save(p); os.remove(ppm)
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
def refimg(b):
    p = f'{R}/refs/{b}_{key}_{framing}.png'
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16) if os.path.exists(p) else None
imgs = {'master': frame('master'), build: frame(build)}
for b in ('id', 'chg', 'chr', 'wk', 'ff'):
    im = refimg(b)
    if im is not None: imgs[b] = im
a, r = imgs[build], imgs[ref]
h, w = min(a.shape[0], r.shape[0]), min(a.shape[1], r.shape[1])
d = np.abs(a[:h, :w] - r[:h, :w]).max(axis=2)
bad = d > thr
print(key, framing, f'{build} vs {ref}: beyond {thr}: {bad.sum()} px ({100*bad.mean():.3f} %), 9-20: {((d>8)&(d<=20)).sum()} px; frame {w}x{h}')
# clusters
lab = np.zeros((h, w), dtype=np.int32); n = 0; clusters = []
ys, xs = np.nonzero(bad)
for y0, x0 in zip(ys, xs):
    if lab[y0, x0]: continue
    n += 1; stack = [(y0, x0)]; lab[y0, x0] = n; pts = []
    while stack:
        y, x = stack.pop(); pts.append((y, x))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and bad[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; stack.append((yy, xx))
    clusters.append(pts)
clusters.sort(key=len, reverse=True)
print(len(clusters), 'clusters; the largest:')
for pts in clusters[:int(os.environ.get('TOP', 14))]:
    ys_, xs_ = [p[0] for p in pts], [p[1] for p in pts]
    wy, wx = max(pts, key=lambda p: d[p])
    vals = ' '.join(f"{b}={tuple(int(v) for v in im[wy, wx])}" for b, im in imgs.items() if wy < im.shape[0] and wx < im.shape[1])
    print(f"  {len(pts):5d} px  x {min(xs_)}..{max(xs_)}  y {min(ys_)}..{max(ys_)}  worst {int(d[wy, wx])} at ({wx},{wy}): {vals}")
np.save(f'{R}/tmp/forensics/last_bad.npy', bad)
