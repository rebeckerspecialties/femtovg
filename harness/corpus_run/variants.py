#!/usr/bin/env python3
"""Attribution by rewritten reference: an SVG is rewritten to what femtovg actually draws (a filter
dropped, an anisotropic blur made isotropic, ...), Chromium renders the rewrite at the four framings,
and femtovg's frame of the ORIGINAL is compared with it. A small residual means the whole deviation
is the rewritten feature. Prints a table: variant, framing, femtovg vs original ref, femtovg vs
rewritten ref, original ref vs rewritten ref (the feature's own weight).

  variants.py [variant ...]      femtovg frames are read from $CORPUS_RUN_OUT/png, as accuracy.py png=DIR
                                 writes them (BUILD=mm by default); rewrites and their references go to
                                 $CORPUS_RUN_OUT/variants."""
import os, re, subprocess, sys
import numpy as np
from PIL import Image
from common import *

VAR = f'{OUT}/variants'
PNG = os.environ.get('FEMTOVG_PNG', f'{OUT}/png')
os.makedirs(VAR, exist_ok=True)


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def compare(a, b):
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    dm = np.abs(a[:h, :w] - b[:h, :w]).max(axis=2)
    over20 = dm > 20
    return {'px8': round(100 * float((dm > 8).mean()), 2), 'px20': round(100 * float(over20.mean()), 2),
            'struct': round(100 * float(erode(over20).mean()), 3), 'max': int(dm.max())}


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def chromium_ref(svg, framing, png):
    if os.path.exists(png):
        return png
    fr, z = FRAMINGS[framing]
    r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', svg, str(z)], capture_output=True, text=True, env={**os.environ, **fr})
    html = png[:-4] + '.html'
    open(html, 'w').write(r.stdout)
    subprocess.run([CHR, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                    f'--window-size={fr["FRAME_W"]},{fr["FRAME_H"]}', '--default-background-color=FFFFFFFF',
                    f'--screenshot={png}', f'file://{html}'], capture_output=True, timeout=180)
    os.remove(html)
    im = Image.open(png).convert('RGB')
    w, h = int(fr['FRAME_W']), int(fr['FRAME_H'])
    if im.size != (w, h):
        im.crop((0, 0, w, h)).save(png)
    return png


# variant name -> (source key, rewrite function on the SVG text)
def drop_filter_attrs(t):
    return re.sub(r'\s+filter="url\(#[^"]*\)"', '', t)


def isotropic_max(t):
    def fix(m):
        v = m.group(1).replace(',', ' ').split()
        if len(v) == 2:
            s = max(float(v[0]), float(v[1]))
            return f'stdDeviation="{s:g} {s:g}"'
        return m.group(0)
    return re.sub(r'stdDeviation="([^"]*)"', fix, t)


def drop_morphology(t):
    # The Sketch shadow chain: feMorphology(SourceAlpha) -> feOffset(in=spread) -> blur -> matrix.
    t = re.sub(r'<feMorphology[^>]*/>', '', t)
    return t.replace('in="shadowSpreadOuter1"', 'in="SourceAlpha"')


VARIANTS = {
    'toggle-nofilter': ('corpus__firefox-com__Toggle_DNTkMhH.width-1000', drop_filter_attrs),
    'enterprise-nofilter': ('corpus__firefox-com__firefox-enterprise-browser-img.52254889d4cf', drop_filter_attrs),
    'enterprise-nomorphology': ('corpus__firefox-com__firefox-enterprise-browser-img.52254889d4cf', drop_morphology),
    'directional-isotropic': ('corpus__wpt-fill-blur-reftests__08-gaussian-blur-edge-and-kernel__blur-axis-zero-directional', isotropic_max),
}


def main():
    fs = {f['key']: f for f in files()}
    names = sys.argv[1:] or list(VARIANTS)
    build = os.environ.get('BUILD', 'mm')
    print(f'{"variant":26s} {"fr":3s} | fv vs ref: px8 px20 struct max | fv vs rewritten: px8 px20 struct max | ref vs rewritten: px8 px20 max')
    for name in names:
        key, rewrite = VARIANTS[name]
        svg = f'{VAR}/{name}.svg'
        open(svg, 'w').write(rewrite(open(fs[key]['path']).read()))
        for framing in FRAMINGS:
            fv = f'{PNG}/{build}_{key}_{framing}.png'
            if not os.path.exists(fv):
                print(name, framing, 'no femtovg frame', fv)
                continue
            a = load(fv)
            ref = load(ref_png('chr', key, framing))
            rw = load(chromium_ref(svg, framing, f'{VAR}/{name}_{framing}.png'))
            x, y, z = compare(a, ref), compare(a, rw), compare(ref, rw)
            print(f'{name:26s} {framing:3s} | {x["px8"]:5.2f} {x["px20"]:5.2f} {x["struct"]:6.3f} {x["max"]:3d} | {y["px8"]:5.2f} {y["px20"]:5.2f} {y["struct"]:6.3f} {y["max"]:3d} | {z["px8"]:5.2f} {z["px20"]:5.2f} {z["max"]:3d}')


main()
