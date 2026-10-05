#!/usr/bin/env python3
"""classify.py BUILD ROW...  (ROW = KEY_SUBSTRING:FRAMING) - what the pixels of BUILD beyond 20/255 of the area reference are:
shared   every browser at one device pixel (WebKit, GPU and software Chromium, Firefox) is as far from the area as the build
         there, within 12/255 of the build: one coverage per draw at one sample per pixel (conflation)
fill     master is the same as the build there (within 2/255): the fill or stroke rasterization, not the clip
clip     the rest: the clip's own residual"""
import json, os, sys
import numpy as np
from PIL import Image
from common import *
R = OUT
os.makedirs(f'{R}/tmp/forensics', exist_ok=True)
files_ = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
build = sys.argv[1]
def frame(b, key, framing):
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
def ref(b, key, framing):
    p = f'{R}/refs/{b}_{key}_{framing}.png'
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16) if os.path.exists(p) else None
dist = lambda a, b: np.abs(a - b).max(axis=2)
print(f"{'frame':46s} {'px':>7s} | beyond 20/255 of the area: master {build:>4s} | of {build}'s: shared  fill  clip | browsers: chg chr wk ff")
for row in sys.argv[2:]:
    sub, framing = row.split(':')
    key = next((k for k in files_ if k.endswith('__' + sub)), None) or next(k for k in files_ if sub in k)
    m, a, idr = frame('master', key, framing), frame(build, key, framing), ref('id', key, framing)
    h, w = idr.shape[:2]
    m, a = m[:h, :w], a[:h, :w]
    bad = dist(a, idr) > 20
    br = {b: ref(b, key, framing)[:h, :w] for b in ('chg', 'chr', 'wk', 'ff')}
    near_all = np.ones((h, w), bool)
    for b, im in br.items():
        near_all &= dist(a, im) <= 12
    shared = bad & near_all
    fill = bad & ~shared & (dist(a, m) <= 2)
    clip = bad & ~shared & ~fill
    bb = ' '.join(f"{(dist(im, idr) > 20).sum():5d}" for im in br.values())
    print(f"{sub[:38] + ' ' + framing:46s} {h*w:7d} | {(dist(m, idr) > 20).sum():6d} {bad.sum():6d} | {shared.sum():6d} {fill.sum():5d} {clip.sum():5d} | {bb}")
    np.save(f'{R}/tmp/forensics/clip_{sub}_{framing}.npy', clip)
