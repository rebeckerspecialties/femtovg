#!/usr/bin/env python3
"""The area reference: refs/id_KEY_FRAMING.png, Chromium rasterizing on the GPU at SCALE device pixels per CSS
pixel (8; 4 for the 1080p framing), each SCALE x SCALE block averaged into one pixel. Every antialiased edge then
holds the share of the pixel the artwork covers to 1/SCALE of a pixel, whatever the renderer does where two edges
meet in one pixel - a clip's and a fill's, two clips', a fill's and its neighbour's - which is where the browsers
at one device pixel differ from one another.
  refs_ideal.py [group=NAME]... [keys=FILE] [framings=z1,z2,z4,hd] [scale=8]"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from common import *

Image.MAX_IMAGE_PIXELS = None
GPU = ['--enable-gpu', '--use-angle=metal', '--enable-gpu-rasterization', '--ignore-gpu-blocklist']
opts = dict(a.split('=', 1) for a in sys.argv[1:] if a.split('=', 1)[0] in ('scale', 'framings', 'keys'))
groups = {a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('group=')}
SCALE = int(opts.get('scale', 8))


def shoot(job):
    f, framing = job
    png = ref_png('id', f['key'], framing)
    if os.path.exists(png):
        return 'kept'
    fr, z = FRAMINGS[framing]
    w, h = int(fr['FRAME_W']), int(fr['FRAME_H'])
    scale = min(SCALE, 4) if w > 1000 else SCALE
    html = f'{REFS}/{f["key"]}_{framing}_id.html'
    big = png[:-4] + '_big.png'
    r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', f['path'], str(z)], capture_output=True, text=True, env={**os.environ, **fr})
    if r.returncode != 0 or '<svg' not in r.stdout:
        return 'unframed'
    open(html, 'w').write(r.stdout)
    subprocess.run([CHR, '--headless', *GPU, '--hide-scrollbars', f'--force-device-scale-factor={scale}',
                    f'--window-size={w},{h}', '--default-background-color=FFFFFFFF',
                    f'--screenshot={big}', f'file://{html}'], capture_output=True, timeout=300)
    os.remove(html)
    if not os.path.exists(big):
        return 'failed'
    im = np.asarray(Image.open(big).convert('RGB'), dtype=np.float64)
    os.remove(big)
    if im.shape[0] < h * scale or im.shape[1] < w * scale:
        return 'short'
    im = im[:h * scale, :w * scale].reshape(h, scale, w, scale, 3).mean(axis=(1, 3))
    Image.fromarray(np.rint(im).astype(np.uint8)).save(png)
    return 'made'


fs = files()
framings = opts['framings'].split(',') if 'framings' in opts else DEFAULT_FRAMINGS
keys = set(json.load(open(opts['keys']))) if 'keys' in opts else None
fs = [f for f in fs if (not groups or f['group'] in groups) and (keys is None or f['key'] in keys)]
counts = {}
with ThreadPoolExecutor(3) as ex:
    for r in ex.map(shoot, [(f, fr) for f in fs for fr in framings]):
        counts[r] = counts.get(r, 0) + 1
print(f'ideal done: {counts}', flush=True)
