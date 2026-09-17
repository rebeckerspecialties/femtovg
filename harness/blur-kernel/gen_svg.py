#!/usr/bin/env python3
"""The #325 structured source as an SVG (the _chainmx.rs source, vectorised):
16 px checkerboard (60,120,220)/(240,200,60), disc at pixel (96,72) r 40
(200,30,30) -> circle centred on that pixel's centre, semi-transparent bar rows
160-200 straight (40,180,40) at 128/255. The bar *replaces* the checkerboard in
the original, so cells under it are not emitted. Variants: control, blur 3,
chain 3+3, blur 16; every filter is sRGB so it matches Canvas blur()."""
import sys, os
out = sys.argv[1]
A, B = "rgb(60,120,220)", "rgb(240,200,60)"
cells = []
for cy in range(16):
    for cx in range(16):
        y0, h = cy * 16, 16
        if 160 <= y0 < 200:
            continue
        if y0 < 200 < y0 + 16:
            y0, h = 200, y0 + 16 - 200
        col = A if (cx + cy) % 2 == 0 else B
        cells.append(f'<rect x="{cx*16}" y="{y0}" width="16" height="{h}" fill="{col}"/>')
body = "\n".join(cells) + '\n<circle cx="96.5" cy="72.5" r="40" fill="rgb(200,30,30)"/>\n' \
       '<rect x="0" y="160" width="256" height="40" fill="rgb(40,180,40)" fill-opacity="0.50196"/>'
variants = {
    "control": None,
    "blur3": '<feGaussianBlur stdDeviation="3"/>',
    "chain3x2": '<feGaussianBlur stdDeviation="3"/><feGaussianBlur stdDeviation="3"/>',
    "blur16": '<feGaussianBlur stdDeviation="16"/>',
}
for name, prims in variants.items():
    defs = f'<defs><filter id="f" color-interpolation-filters="sRGB">{prims}</filter></defs>\n' if prims else ""
    g = '<g filter="url(#f)">' if prims else "<g>"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">\n{defs}{g}\n{body}\n</g>\n</svg>\n'
    open(os.path.join(out, f"{name}.svg"), "w").write(svg)
    print(name, len(svg))
