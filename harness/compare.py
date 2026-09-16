#!/usr/bin/env python3
"""Pixel comparison used for every femtovg-vs-browser claim.

  compare.py fvg.ppm chr.png [out_overlay.png] [--threshold N] [--exact]

Prints: percent of pixels whose max channel delta exceeds the threshold
(default 20/255), and the same after a 2-px binary erosion of the diff mask
("structural") - edge anti-aliasing ribbons are one to two pixels wide and
vanish under erosion, so structural ~0 means "only AA differs". Writes an
overlay with differing pixels painted red and a femtovg / reference / overlay
strip when out is given.

--threshold N  sweep threshold; 20 for corpus sweeps, 8 for subtle-hue
               classes (gradient interpolation space) and for low-opacity
               content, where a whole displaced layer at opacity 0.14 moves
               a pixel by at most ~36/255 and mostly by far less.
--exact        also count every pixel that differs at all (delta >= 1), with
               the bounding box of those pixels and of the >threshold set:
               a displacement or a dropped layer shows up as a box the size
               of the content even when nothing survives 20/255 + erosion.

Conventions: 460x260 canvases; crop the reference to [:260,:460] because a
browser screenshot can come back one row/column larger.
"""
import argparse

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("a")
ap.add_argument("b")
ap.add_argument("overlay", nargs="?")
ap.add_argument("--threshold", type=int, default=20, help="max-channel delta above which a pixel counts (default 20)")
ap.add_argument("--exact", action="store_true", help="also report every differing pixel and bounding boxes")
args = ap.parse_args()
thr = args.threshold

a = np.asarray(Image.open(args.a).convert("RGB"), dtype=int)
c = np.asarray(Image.open(args.b).convert("RGB"), dtype=int)
# Compare over the common area: a browser screenshot can come back a row or column larger.
h, w = min(a.shape[0], c.shape[0]), min(a.shape[1], c.shape[1])
a, c = a[:h, :w], c[:h, :w]


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def bbox(m):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return "none"
    return f"({xs.min()},{ys.min()})-({xs.max()},{ys.max()}) {xs.max() - xs.min() + 1}x{ys.max() - ys.min() + 1}"


delta = np.abs(a - c).max(axis=2)
d = delta > thr
print(f"px>{thr}: {100 * d.mean():.2f}%   structural (2px erosion): {100 * erode(d).mean():.3f}%   max delta: {delta.max()}")
if args.exact:
    any_diff = delta > 0
    n = int(any_diff.sum())
    print(
        f"exact: {n} px differ ({100 * any_diff.mean():.2f}%)   mean delta over them: "
        f"{(delta[any_diff].mean() if n else 0):.2f}   bbox: {bbox(any_diff)}   bbox px>{thr}: {bbox(d)}"
    )
if args.overlay:
    o = a.copy().astype(np.uint8)
    o[d] = [255, 0, 0]
    Image.fromarray(np.concatenate([a.astype(np.uint8), c.astype(np.uint8), o], axis=0)).save(args.overlay)
