#!/usr/bin/env python3
"""WebKit references, next to the Chromium and Firefox ones: refs/wk_KEY_FRAMING.png, from the system WebKit
(Safari's engine, rasterizing with Core Graphics) through wk_shot.swift at one device pixel per CSS pixel.
  swiftc -O wk_shot.swift -o $HARNESS_BIN/wk_shot
  refs_webkit.py [group=NAME]... [keys=FILE] [framings=z1,z2,z4,hd]"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from common import *

WK = os.environ.get('WK_SHOT', f'{BIN}/wk_shot')


def shoot(job):
    f, framing = job
    png = ref_png('wk', f['key'], framing)
    if os.path.exists(png):
        return 'kept'
    fr, z = FRAMINGS[framing]
    html = f'{REFS}/{f["key"]}_{framing}_wk.html'
    r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', f['path'], str(z)], capture_output=True, text=True, env={**os.environ, **fr})
    if r.returncode != 0 or '<svg' not in r.stdout:
        return 'unframed'
    open(html, 'w').write(r.stdout)
    try:
        subprocess.run([WK, html, png, fr['FRAME_W'], fr['FRAME_H']], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        pass
    os.remove(html)
    if not os.path.exists(png):
        return 'failed'
    Image.open(png).convert('RGB').save(png)
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
print(f'webkit done: {counts}', flush=True)
