#!/usr/bin/env python3
"""Old-vs-new A/B: render every SVG of the given corpora with two harness
binaries and report any pixel that differs (delta >= 1 on any channel).
  ab.py --a BIN_A --b BIN_B [--zooms 1,2,4] [--out DIR] DIR_OR_SVG...
Prints one line per (file, zoom) that differs and a summary; exit 1 if any
frame differs. Used to validate refactors: bit-identical means the change
touched no pixel of the corpus.
"""
import argparse, glob, os, subprocess, sys
import numpy as np
from PIL import Image
ap = argparse.ArgumentParser()
ap.add_argument('--a', required=True); ap.add_argument('--b', required=True)
ap.add_argument('--zooms', default='1,2,4'); ap.add_argument('--out', default='/tmp/ab')
ap.add_argument('paths', nargs='+')
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
files = []
for p in args.paths:
    files += sorted(glob.glob(os.path.join(p, '*.svg'))) if os.path.isdir(p) else [p]
zooms = [float(z) for z in args.zooms.split(',')]
frames = 0; differing = []
for f in files:
    name = os.path.splitext(os.path.basename(f))[0]
    for z in zooms:
        outs = []
        for tag, binary in (('a', args.a), ('b', args.b)):
            ppm = os.path.join(args.out, f'{tag}_{name}_{z:g}.ppm')
            r = subprocess.run([binary, f'{z:g}', ppm, f], capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(ppm):
                print(f'{name} {z:g}x {tag}: render failed: {r.stderr.strip()[-200:]}'); outs = None; break
            outs.append(np.asarray(Image.open(ppm).convert('RGB'), dtype=np.int16))
        if outs is None: differing.append((name, z, 'failed')); continue
        frames += 1
        if outs[0].shape != outs[1].shape:
            differing.append((name, z, 'shape')); print(f'{name} {z:g}x: shapes differ'); continue
        d = np.abs(outs[0] - outs[1]).max(axis=2)
        n = int((d > 0).sum())
        if n:
            differing.append((name, z, n)); print(f'{name} {z:g}x: {n} px differ, max delta {int(d.max())}')
print(f'{frames} frames, {len(differing)} differ')
sys.exit(1 if differing else 0)
