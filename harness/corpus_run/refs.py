#!/usr/bin/env python3
"""Browser references for the full-corpus run: Chromium 131 for every file at the four framings,
Firefox at z1 (refs.py firefox framings=z1,z2,z4,hd group=NAME for more). Resumable: existing PNGs
are kept. A file make_ref.py cannot frame gets no reference."""
import os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from common import *

os.makedirs(REFS, exist_ok=True)


def page(f, framing, tag):
    fr, z = FRAMINGS[framing]
    html = f'{REFS}/{f["key"]}_{framing}_{tag}.html'
    r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', f['path'], str(z)], capture_output=True, text=True, env={**os.environ, **fr})
    if r.returncode != 0 or '<svg' not in r.stdout:
        return None
    open(html, 'w').write(r.stdout)
    return html


def crop(png, fr):
    w, h = int(fr['FRAME_W']), int(fr['FRAME_H'])
    im = Image.open(png).convert('RGB')
    if im.size != (w, h):
        im.crop((0, 0, w, h)).save(png)


def chromium(job):
    f, framing = job
    png = ref_png('chr', f['key'], framing)
    if os.path.exists(png):
        return 'kept'
    html = page(f, framing, 'chr')
    if html is None:
        return 'unframed'
    fr, _ = FRAMINGS[framing]
    subprocess.run([CHR, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                    f'--window-size={fr["FRAME_W"]},{fr["FRAME_H"]}', '--default-background-color=FFFFFFFF',
                    f'--screenshot={png}', f'file://{html}'], capture_output=True, timeout=180)
    os.remove(html)
    if not os.path.exists(png):
        return 'failed'
    crop(png, fr)
    return 'made'


def firefox(job):
    f, framing = job
    png = ref_png('ff', f['key'], framing)
    if os.path.exists(png):
        return 'kept'
    html = page(f, framing, 'ff')
    if html is None:
        return 'unframed'
    fr, _ = FRAMINGS[framing]
    prof = tempfile.mkdtemp(prefix='ffprof')
    try:
        for _attempt in range(2):
            try:
                subprocess.run([FF, '--headless', '--no-remote', '--profile', prof, f'--window-size={fr["FRAME_W"]},{fr["FRAME_H"]}',
                                '--screenshot', png, f'file://{html}'], capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                pass
            if os.path.exists(png):
                break
    finally:
        shutil.rmtree(prof, ignore_errors=True)
        if os.path.exists(html):
            os.remove(html)
    if not os.path.exists(png):
        return 'failed'
    crop(png, fr)
    return 'made'


fs = files()
which = sys.argv[1]
# Optional: framings=z1,hd and group=NAME (repeatable) narrow a run, e.g. Firefox at every framing for one group.
framings, groups = None, set()
for arg in sys.argv[2:]:
    k, v = arg.split('=', 1)
    if k == 'framings':
        framings = v.split(',')
    elif k == 'group':
        groups.add(v)
if groups:
    fs = [f for f in fs if f['group'] in groups]
if which == 'chromium':
    jobs = [(f, fr) for f in fs for fr in (framings or FRAMINGS)]
    fn, workers = chromium, 6
else:
    jobs = [(f, fr) for f in fs for fr in (framings or ['z1'])]
    fn, workers = firefox, 3
counts = {}
with ThreadPoolExecutor(workers) as ex:
    for i, r in enumerate(ex.map(fn, jobs)):
        counts[r] = counts.get(r, 0) + 1
        if (i + 1) % 200 == 0:
            print(f'{which}: {i + 1}/{len(jobs)} {counts}', flush=True)
print(f'{which} done: {counts}', flush=True)
