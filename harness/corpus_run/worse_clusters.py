"""worse_clusters.py KEY_SUBSTRING FRAMING BUILD BASE [fill|clip]  - clusters of BUILD's pixels beyond 20/255 of the area
where some browser is nearer by more than 12/255, of the kind given (fill: BASE draws the same there), largest first."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
from common import *
R = OUT
fs = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
sub, framing, build, base = sys.argv[1:5]
kind = sys.argv[5] if len(sys.argv) > 5 else 'fill'
key = next(k for k in fs if k.endswith('__' + sub))
def frame(b):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{R}/{d}/{b}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    binary, extra = BUILDS[b]; fr, z = FRAMINGS[framing]
    p = f'{R}/png_changed/{b}_{key}_{framing}.png'; ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, fs[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra}, capture_output=True)
    Image.open(ppm).save(p); os.remove(ppm)
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
ref = lambda b: np.asarray(Image.open(f'{R}/refs/{b}_{key}_{framing}.png').convert('RGB'), dtype=np.int16)
area, a, m = ref('id'), frame(build), frame(base)
d = np.abs(a - area).max(axis=2)
far = d > 20
browsers = {b: ref(b) for b in ('chg', 'chr', 'wk', 'ff') if os.path.exists(f'{R}/refs/{b}_{key}_{framing}.png')}
worse = np.zeros_like(far)
for im in browsers.values():
    worse |= far & (np.abs(im - area).max(axis=2) < d - 12)
same = np.abs(a - m).max(axis=2) <= 2
sel = worse & (same if kind == 'fill' else ~same)
H, W = sel.shape; lab = np.zeros(sel.shape, dtype=np.int32); clusters = []
for y0, x0 in zip(*np.nonzero(sel)):
    if lab[y0, x0]:
        continue
    stack = [(y0, x0)]; lab[y0, x0] = len(clusters) + 1; pts = []
    while stack:
        y, x = stack.pop(); pts.append((y, x))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and sel[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = len(clusters) + 1; stack.append((yy, xx))
    clusters.append(pts)
clusters.sort(key=len, reverse=True)
print(f'{sub} {framing} {build}: {kind} pixels worse than some browser {int(sel.sum())} in {len(clusters)} clusters; '
      f'signed mean of {build} - area over them (luma): {float(((a - area)[sel].mean(axis=1)).mean()) if sel.any() else 0:+.1f}')
for pts in clusters[:int(os.environ.get('TOP', 10))]:
    ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
    j = np.argmax(d[ys, xs]); y, x = ys[j], xs[j]
    vals = ' '.join(f'{nm}={tuple(int(v) for v in im[y, x])}' for nm, im in [('area', area), (build, a), *browsers.items()])
    print(f'  {len(pts):4d} px  x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}  worst {int(d[y, x])} at ({x},{y}): {vals}')
