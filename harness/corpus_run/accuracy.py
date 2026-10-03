#!/usr/bin/env python3
"""Accuracy of one build against the browser references, per file and framing.

  accuracy.py <build> [group=NAME|key=KEY|keys=FILE]... [framings=z1,z2,z4,hd] [png=DIR]

Renders every selected file of files.json at the framings with the build (SWEEP_ENV applied, as
run.py does), compares the frame with the Chromium reference and, where one exists, the Firefox
reference, and appends a row per frame to accuracy.jsonl: the frame hash, the LAYER_STATS counters,
and for each comparison the share of pixels beyond 8/255 and 20/255, the structural share (beyond
20/255 after a 2 px erosion), the largest difference and the count of pixels that differ at all.
The Chromium-vs-Firefox envelope is stored alongside. png=DIR keeps the rendered frames as PNGs.
Resumable: a (key, framing, build) already in accuracy.jsonl is skipped."""
import hashlib, json, os, re, subprocess, sys
import numpy as np
from PIL import Image
from common import *

TMP = f'{OUT}/tmp'
os.makedirs(TMP, exist_ok=True)
STATS = {
    'layers': r'layers begun: (\d+)',
    'pass_through': r'layers passed through: (\d+)',
    'skipped': r'filters skipped \(SKIP_UNSUPPORTED_FILTERS\): (\d+)',
    'invalid_dropped': r'filter attributes with invalid references dropped \(Filter Effects 5\): (\d+)',
}


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def compare(a, b):
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    dm = np.abs(a[:h, :w] - b[:h, :w]).max(axis=2)
    over20 = dm > 20
    return {'px8': round(100 * float((dm > 8).mean()), 3), 'px20': round(100 * float(over20.mean()), 3),
            'struct': round(100 * float(erode(over20).mean()), 4), 'max': int(dm.max()), 'exact': int((dm > 0).sum())}


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def render(f, framing, build):
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{TMP}/acc_{os.getpid()}.ppm'
    if os.path.exists(ppm):
        os.remove(ppm)
    env = {**os.environ, **fr, **SWEEP_ENV, **extra}
    row = {'key': f['key'], 'group': f['group'], 'framing': framing, 'build': build}
    try:
        r = subprocess.run([binary, f'{z:g}', ppm, f['path']], env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        row['error'] = 'timeout'
        return row, None
    row['rc'] = r.returncode
    for name, pattern in STATS.items():
        m = re.search(pattern, r.stderr)
        if m:
            row[name] = int(m.group(1))
    m = re.search(r'harness cfgs: (.*)', r.stderr)
    if m:
        row['cfgs'] = m.group(1).strip()
    if r.returncode != 0 or not os.path.exists(ppm):
        row['error'] = r.stderr.strip()[-400:]
        return row, None
    row['hash'] = hashlib.sha1(open(ppm, 'rb').read()).hexdigest()
    return row, ppm


def main():
    build = sys.argv[1]
    sel, framings, png_dir = [], list(FRAMINGS), None
    for arg in sys.argv[2:]:
        k, v = arg.split('=', 1)
        if k == 'group':
            sel.append(lambda f, v=v: f['group'] == v)
        elif k == 'key':
            sel.append(lambda f, v=v: f['key'] == v)
        elif k == 'keys':
            keys = set(json.load(open(v)))
            sel.append(lambda f, keys=keys: f['key'] in keys)
        elif k == 'framings':
            framings = v.split(',')
        elif k == 'png':
            png_dir = v
            os.makedirs(png_dir, exist_ok=True)
    fs = [f for f in files() if any(s(f) for s in sel)] if sel else files()
    path = f'{OUT}/accuracy.jsonl'
    done = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                r = json.loads(line)
                done.add((r['key'], r['framing'], r['build']))
            except Exception:
                pass
    out = open(path, 'a')
    n = 0
    for f in fs:
        for framing in framings:
            if (f['key'], framing, build) in done:
                continue
            row, ppm = render(f, framing, build)
            if ppm:
                a = load(ppm)
                if png_dir:
                    Image.open(ppm).save(f'{png_dir}/{build}_{f["key"]}_{framing}.png')
                os.remove(ppm)
                chr_png = ref_png('chr', f['key'], framing)
                ff_png = ref_png('ff', f['key'], framing)
                c = load(chr_png) if os.path.exists(chr_png) else None
                g = load(ff_png) if os.path.exists(ff_png) else None
                if c is not None:
                    row['vs_chr'] = compare(a, c)
                if g is not None:
                    row['vs_ff'] = compare(a, g)
                if c is not None and g is not None:
                    row['chr_vs_ff'] = compare(c, g)
            out.write(json.dumps(row) + '\n')
            out.flush()
            n += 1
    print(f'{build}: {n} frames', flush=True)


main()
