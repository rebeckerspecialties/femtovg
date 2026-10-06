"""worse_than_browsers.py BUILD BASE ROW...  (ROW = KEY_SUBSTRING:FRAMING) - of BUILD's pixels beyond 20/255 of the area,
those where some browser is nearer the area by more than 12/255: split by whether BASE draws the same there (fill) or
not (clip), and per browser how many of them it is nearer on. Everything else is at the browsers' level."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
from common import *
R = OUT
fs = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
build, base = sys.argv[1:3]
def frame(b, key, framing):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{R}/{d}/{b}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    binary, extra = BUILDS[b]; fr, z = FRAMINGS[framing]
    p = f'{R}/png_changed/{b}_{key}_{framing}.png'; ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, fs[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra}, capture_output=True)
    Image.open(ppm).save(p); os.remove(ppm)
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
print(f"{'frame':40s} {'far':>6s} {'at browsers':>11s} {'worse: fill':>11s} {'clip':>5s} | nearer on: chg chr wk ff")
for row in sys.argv[3:]:
    sub, framing = row.split(':')
    key = next(k for k in fs if k.endswith('__' + sub))
    ref = lambda b: np.asarray(Image.open(f'{R}/refs/{b}_{key}_{framing}.png').convert('RGB'), dtype=np.int16)
    area, a, m = ref('id'), frame(build, key, framing), frame(base, key, framing)
    d = np.abs(a - area).max(axis=2)
    far = d > 20
    nearer = {}
    worse = np.zeros_like(far)
    for b in ('chg', 'chr', 'wk', 'ff'):
        if os.path.exists(f'{R}/refs/{b}_{key}_{framing}.png'):
            db = np.abs(ref(b) - area).max(axis=2)
            nearer[b] = far & (db < d - 12)
            worse |= nearer[b]
    same = np.abs(a - m).max(axis=2) <= 2
    print(f"{sub[:28] + ' ' + framing:40s} {int(far.sum()):6d} {int((far & ~worse).sum()):11d} {int((worse & same).sum()):11d} {int((worse & ~same).sum()):5d} | " + ' '.join(f'{int(v.sum())}' for v in nearer.values()))
