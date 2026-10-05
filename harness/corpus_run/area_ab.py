#!/usr/bin/env python3
"""area_ab.py BEFORE AFTER [refs=id,wk,chg,chr,ff]  - two builds against the area reference (and others), over every frame that has
an area reference: pixels beyond 20/255 and beyond 8/255 summed, frames nearer and further, and the same for the browsers."""
import collections, json, os, subprocess, sys
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from common import *
R = OUT
before, after = sys.argv[1:3]
fs = {f['key']: f for f in files()}
ids = sorted(n[3:-4] for n in os.listdir(f'{R}/refs') if n.startswith('id_') and n.endswith('.png'))
def split(name):
    key, framing = name.rsplit('_', 1)
    return key, framing
def frame(b, key, framing):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{R}/{d}/{b}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    binary, extra = BUILDS[b]; fr, z = FRAMINGS[framing]
    p = f'{R}/png_changed/{b}_{key}_{framing}.png'; ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, fs[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra}, capture_output=True)
    if not os.path.exists(ppm): return None
    Image.open(ppm).save(p); os.remove(ppm)
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
def ref(b, key, framing):
    p = f'{R}/refs/{b}_{key}_{framing}.png'
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16) if os.path.exists(p) else None
def one(name):
    key, framing = split(name)
    if key not in fs: return None
    idr = ref('id', key, framing)
    a, b = frame(before, key, framing), frame(after, key, framing)
    if idr is None or a is None or b is None: return None
    h, w = idr.shape[:2]
    d = lambda im: np.abs(im[:h, :w] - idr).max(axis=2)
    da, db = d(a), d(b)
    out = {'name': name, 'group': fs[key]['group'], 'a20': int((da > 20).sum()), 'b20': int((db > 20).sum()), 'a8': int((da > 8).sum()), 'b8': int((db > 8).sum()),
           'same': bool((a[:h, :w] == b[:h, :w]).all())}
    for br in ('wk', 'chg', 'chr', 'ff'):
        im = ref(br, key, framing)
        if im is not None:
            out[br + '20'] = int((d(im) > 20).sum()); out[br + '8'] = int((d(im) > 8).sum())
    return out
with ThreadPoolExecutor(4) as ex:
    rows = [r for r in ex.map(one, ids) if r]
json.dump(rows, open(f'{R}/tmp/area_ab_{before}_{after}.json', 'w'))
ch = [r for r in rows if not r['same']]
print(f'{len(rows)} frames with an area reference; {len(ch)} differ between {before} and {after}')
for label, sel in (('all', rows), ('changed', ch)):
    s = lambda k: sum(r.get(k, 0) for r in sel)
    print(f'  {label}: beyond 20/255 of the area {s("a20")} -> {s("b20")} px; beyond 8/255 {s("a8")} -> {s("b8")} px | WebKit {s("wk20")} / {s("wk8")}, GPU Chromium {s("chg20")} / {s("chg8")}, software Chromium {s("chr20")} / {s("chr8")}, Firefox {s("ff20")} / {s("ff8")}')
nearer = sum(r['b20'] < r['a20'] for r in ch); further = sum(r['b20'] > r['a20'] for r in ch)
print(f'  frames nearer the area {nearer}, further {further}, same count {len(ch) - nearer - further}')
g = collections.defaultdict(lambda: [0, 0, 0])
for r in ch:
    x = g[r['group']]; x[0] += r['a20']; x[1] += r['b20']; x[2] += 1
for name, (a, b, n) in sorted(g.items(), key=lambda kv: kv[1][1] - kv[1][0]):
    print(f'    {name}: {n} frames, {a} -> {b} px')
worst = sorted(ch, key=lambda r: r['b20'] - r['a20'])
print('  most improved:', [(r['name'].split('__')[-1], r['a20'], r['b20']) for r in worst[:6]])
print('  most worsened:', [(r['name'].split('__')[-1], r['a20'], r['b20']) for r in worst[-6:]])
