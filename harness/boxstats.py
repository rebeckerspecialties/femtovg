"""Diff statistics of a femtovg render against a reference, over the whole frame
and over the SVG box, with a 2-px erosion done in numpy."""
import sys
from PIL import Image
import numpy as np

def erode(m, it=2):
    for _ in range(it):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m

def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)

fvg, refs = sys.argv[1], sys.argv[2:]
bx, by, bs = [int(v) for v in __import__("os").environ.get("BOXRECT", "420,0,1080").split(",")]
f = load(fvg)
for ref in refs:
    r = load(ref)
    h, w = min(f.shape[0], r.shape[0]), min(f.shape[1], r.shape[1])
    d = np.abs(f[:h, :w] - r[:h, :w]).max(axis=2)
    box = (slice(by, by + bs), slice(bx, bx + bs))
    m = d > 20
    e = erode(m)
    print(f"{fvg} vs {ref}: px>20 {100*m.mean():.3f}% frame / {100*m[box].mean():.3f}% box | structural {100*e.mean():.3f}% frame / {100*e[box].mean():.3f}% box | mean|d| box {d[box].mean():.2f} | px>40 box {100*(d>40)[box].mean():.3f}% | px>80 box {100*(d>80)[box].mean():.3f}%")
