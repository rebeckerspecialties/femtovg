#!/usr/bin/env python3
"""Chromium references with GPU rasterization (ANGLE on Metal), next to the software-rasterized ones refs.py makes:
refs/chg_KEY_FRAMING.png. Chromium's software rasterizer snaps a path's edges to quarter pixels vertically; its
GPU rasterizer, the one a desktop Chrome draws with, does not, so a clip's edge differs between the two.
  refs_gpu.py [group=NAME]... [keys=FILE] [framings=z1,z2,z4,hd]"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from common import *

GPU = ['--enable-gpu', '--use-angle=metal', '--enable-gpu-rasterization', '--ignore-gpu-blocklist']


def shoot(job):
    f, framing = job
    png = ref_png('chg', f['key'], framing)
    if os.path.exists(png):
        return 'kept'
    fr, z = FRAMINGS[framing]
    html = f'{REFS}/{f["key"]}_{framing}_chg.html'
    r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', f['path'], str(z)], capture_output=True, text=True, env={**os.environ, **fr})
    if r.returncode != 0 or '<svg' not in r.stdout:
        return 'unframed'
    open(html, 'w').write(r.stdout)
    subprocess.run([CHR, '--headless', *GPU, '--hide-scrollbars', '--force-device-scale-factor=1',
                    f'--window-size={fr["FRAME_W"]},{fr["FRAME_H"]}', '--default-background-color=FFFFFFFF',
                    f'--screenshot={png}', f'file://{html}'], capture_output=True, timeout=180)
    os.remove(html)
    if not os.path.exists(png):
        return 'failed'
    w, h = int(fr['FRAME_W']), int(fr['FRAME_H'])
    im = Image.open(png).convert('RGB')
    if im.size != (w, h):
        im.crop((0, 0, w, h)).save(png)
    return 'made'


fs = files()
framings, groups, keys = DEFAULT_FRAMINGS, set(), None
for arg in sys.argv[1:]:
    k, v = arg.split('=', 1)
    if k == 'framings':
        framings = v.split(',')
    elif k == 'group':
        groups.add(v)
    elif k == 'keys':
        keys = set(json.load(open(v)))
fs = [f for f in fs if (not groups or f['group'] in groups) and (keys is None or f['key'] in keys)]
counts = {}
with ThreadPoolExecutor(4) as ex:
    for r in ex.map(shoot, [(f, fr) for f in fs for fr in framings]):
        counts[r] = counts.get(r, 0) + 1
print(f'chromium gpu done: {counts}', flush=True)
