#!/usr/bin/env python3
"""The clip-path circle and ellipse reftests against the exact area: each frame pixel's share inside the ellipse,
from 16 x 16 samples, shaded green over white as the test does; two builds' frames (kept with accuracy.py
png=png_wpt under CORPUS_RUN_OUT) and the browsers' - Chromium rasterizing in software and on the GPU, Firefox -
against that.
  ideal_clip.py [BEFORE AFTER]   (builds, default master ca)"""
import os, sys
import numpy as np
from PIL import Image
from common import OUT as R
SHAPES = {'clip-path-circle': (100, 100, 50, 50), 'clip-path-ellipse': (100, 100, 60, 35)}
FR = {'z1': (460, 260, 200, 130, 30, 1.0), 'z2': (460, 260, 200, 130, 30, 2.0), 'z4': (460, 260, 200, 130, 30, 4.0), 'hd': (1920, 1080, 1080, 420, 0, 1.0)}
N = 16
BEFORE, AFTER = sys.argv[1:3] if len(sys.argv) > 2 else ('master', 'ca')
def ideal(shape, fr):
    cx, cy, rx, ry = SHAPES[shape]; W, H, box, bx, by, z = FR[fr]; fit = box / 200.0
    sub = (np.arange(N) + 0.5) / N
    xs = (np.arange(W)[:, None] + sub[None, :]).reshape(-1); ys = (np.arange(H)[:, None] + sub[None, :]).reshape(-1)
    # device -> user: device = pivot + z * (box_origin + fit * user - pivot), pivot at the frame's centre
    ux = ((xs - W / 2) / z + W / 2 - bx) / fit; uy = ((ys - H / 2) / z + H / 2 - by) / fit
    inside = (((ux[None, :] - cx) / rx) ** 2 + ((uy[:, None] - cy) / ry) ** 2) <= 1.0
    # the SVG viewport clips at 0..200 too; the shapes sit well inside it
    cov = inside.reshape(H, N, W, N).mean(axis=(1, 3))
    green = np.array([0, 128, 0], dtype=np.float64)
    return 255.0 + cov[:, :, None] * (green - 255.0)
def load(p): return np.asarray(Image.open(p).convert('RGB'), dtype=np.float64)
print('| file | framing | renderer | px > 20/255 | max | mean abs on the edge |'); print('|---|---|---|---:|---:|---:|')
for shape in SHAPES:
    k = f'corpus__wpt-clip-path-reftests__{shape}'
    for fr in FR:
        ref = ideal(shape, fr)
        edge = (ref[:, :, 0] > 0.5) & (ref[:, :, 0] < 254.5)
        for name, p in ((BEFORE, f'{R}/png_wpt/{BEFORE}_{k}_{fr}.png'), (AFTER, f'{R}/png_wpt/{AFTER}_{k}_{fr}.png'), ('Chromium', f'{R}/refs/chr_{k}_{fr}.png'), ('Chromium GPU', f'{R}/refs/chg_{k}_{fr}.png'), ('Firefox', f'{R}/refs/ff_{k}_{fr}.png')):
            if not os.path.exists(p): continue
            d = np.abs(load(p) - ref).max(axis=2)
            print(f'| {shape} | {fr} | {name} | {100 * (d > 20).mean():.3f} % | {d.max():.0f} | {d[edge].mean():.1f} |')
