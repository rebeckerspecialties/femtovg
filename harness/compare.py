#!/usr/bin/env python3
"""Pixel comparison used for every femtovg-vs-browser claim.

  compare.py fvg.ppm chr.png [out_overlay.png] [--threshold 20]

Prints: percent of pixels whose max channel delta exceeds the threshold, and
the same after a 2-px binary erosion of the diff mask ("structural") - edge
anti-aliasing ribbons are one to two pixels wide and vanish under erosion,
so structural ~0 means "only AA differs". Writes an overlay with differing
pixels painted red and a femtovg / reference / overlay strip when out is given.
Conventions: 460x260 canvases; crop the reference to [:260,:460] because a
browser screenshot can come back one row/column larger; threshold 20/255 for
sweeps, 8/255 for subtle-hue classes such as gradient interpolation.
"""
import sys
import numpy as np
from PIL import Image

args = [a for a in sys.argv[1:] if not a.startswith("--")]
thr = int(sys.argv[sys.argv.index("--threshold") + 1]) if "--threshold" in sys.argv else 20
a = np.asarray(Image.open(args[0]).convert("RGB"), dtype=int)[:260, :460]
c = np.asarray(Image.open(args[1]).convert("RGB"), dtype=int)[:260, :460]

def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m

d = np.abs(a - c).max(axis=2) > thr
print(f"px>{thr}: {100 * d.mean():.2f}%   structural (2px erosion): {100 * erode(d).mean():.3f}%   max delta: {np.abs(a - c).max()}")
if len(args) > 2:
    o = a.copy().astype(np.uint8); o[d] = [255, 0, 0]
    Image.fromarray(np.concatenate([a.astype(np.uint8), c.astype(np.uint8), o], axis=0)).save(args[2])
