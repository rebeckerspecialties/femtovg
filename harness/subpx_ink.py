"""Ink of each sub-pixel disc and line in a probe render, against the exact area.

The probe (subpx.svg) is a 200x200 SVG at 1:1 in the harness frame (box at
130,30): white shapes on #202020. Ink = sum over a window of
(gray - bg) / (255 - bg), i.e. coverage in pixel units for a white shape.
"""
import sys
from PIL import Image
import numpy as np

radii = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
widths = [0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0]
OX, OY = 130, 30
BG = 0x20


def load(path):
    return np.asarray(Image.open(path).convert("L")).astype(float)


def ink(img, x0, y0, x1, y1):
    win = img[int(y0):int(y1), int(x0):int(x1)]
    return ((win - BG) / (255.0 - BG)).sum()


def report(paths):
    imgs = {name: load(p) for name, p in paths}
    print("discs: ink in pixel units (exact = pi r^2); 'corner' centred on a pixel corner, 'centre' on a pixel centre")
    print(f"{'r':>5} {'exact':>7} | " + " | ".join(f"{n:>22}" for n, _ in paths))
    for i, r in enumerate(radii):
        exact = np.pi * r * r
        cells = []
        for name, _ in paths:
            im = imgs[name]
            c = ink(im, OX + 20 + 25 * i - 8, OY + 30 - 8, OX + 20 + 25 * i + 8, OY + 30 + 8)
            k = ink(im, OX + 20.5 + 25 * i - 8, OY + 50.5 - 8, OX + 20.5 + 25 * i + 8, OY + 50.5 + 8)
            cells.append(f"{c:6.2f} ({c / exact:4.2f}x) {k:6.2f}")
        print(f"{r:5.2f} {exact:7.3f} | " + " | ".join(f"{c:>22}" for c in cells))
    print("\nlines: ink per unit length (exact = width); 'edge' on a pixel boundary, 'centre' through pixel centres")
    print(f"{'w':>5} {'exact':>7} | " + " | ".join(f"{n:>22}" for n, _ in paths))
    for j, w in enumerate(widths):
        cells = []
        for name, _ in paths:
            im = imgs[name]
            e = ink(im, OX + 30, OY + 80 + 12 * j - 5, OX + 170, OY + 80 + 12 * j + 5) / 140.0
            c = ink(im, OX + 30, OY + 86.5 + 12 * j - 5, OX + 170, OY + 86.5 + 12 * j + 5) / 140.0
            cells.append(f"{e:6.3f} ({e / w:4.2f}x) {c:6.3f}")
        print(f"{w:5.2f} {w:7.3f} | " + " | ".join(f"{c:>22}" for c in cells))


if __name__ == "__main__":
    args = sys.argv[1:]
    report([(args[i], args[i + 1]) for i in range(0, len(args), 2)])
