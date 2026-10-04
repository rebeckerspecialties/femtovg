#!/usr/bin/env python3
"""The clip-edge probes (corpus/clip-probes) as the coverage of the pixel each side of the clip crosses, half way
along the side: left, right, top, bottom, or the two sides a probe is about. `exact` is that pixel's share inside.

  probe_edges.py BUILD[=label]... [refs=chr,chg,ff]"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image
from common import *

builds = [(a.split('=', 1) + [a])[:2] for a in sys.argv[1:] if not a.startswith('refs=')]
refs = dict(a.split('=', 1) for a in sys.argv[1:] if a.startswith('refs=')).get('refs', 'chr,chg,ff').split(',')
names = {'chr': 'Chromium software', 'chg': 'Chromium GPU', 'ff': 'Firefox'}
# probe -> (the clip's rect in its own units, the viewport, the viewBox, the sides read, framings)
SQUARE, EXPORT, TALL = (200, 200), (173, 131), (200, 221)
PROBES = [
    ('rect-fill-fractional', (20.3, 30.6, 50.5, 30.25), SQUARE, SQUARE, 'lrtb', ['z1']),
    ('rect-clip-fractional', (20.3, 30.6, 50.5, 30.25), SQUARE, SQUARE, 'lrtb', ['z1']),
    ('rect-clip-coincident', (20.3, 30.6, 50.5, 30.25), SQUARE, SQUARE, 'lrtb', ['z1']),
    ('rounded-clip-coincident', (20.3, 30.6, 80.5, 60.25), SQUARE, SQUARE, 'lrtb', ['z1']),
    ('rect-clip-rect-inside', (20.3, 30.6, 40, 20), SQUARE, SQUARE, 'lt', ['z1']),
    ('rect-clip-path-inside', (20.3, 30.6, 59.7, 49.4), SQUARE, SQUARE, 'lt', ['z1']),
    ('rounded-clip-rect-inside', (20.3, 46, 40, 28.4), SQUARE, SQUARE, 'l', ['z1']),
    ('nested-twin-clips', (20.3, 30.6, 50.5, 30.25), SQUARE, SQUARE, 'lrtb', ['z1']),
    ('nested-twin-rounded-clips', (20.3, 30.6, 80.5, 60.25), SQUARE, SQUARE, 'lrtb', ['z1']),
    ('viewport-fill', (0, 0, 173, 131), EXPORT, EXPORT, 'b', ['z1']),
    ('viewport-path-edge', (60, 0, 113, 131), EXPORT, EXPORT, 'b', ['z1']),
    ('viewport-clip-twin', (0, 0, 173, 131), EXPORT, EXPORT, 'b', ['z1']),
    ('viewport-clip-twin-fill', (0, 0, 173, 131), EXPORT, EXPORT, 'b', ['z1']),
    ('rect-clip-half-pixel', (0, 0, 361, 400), TALL, (361, 400), 'lr', ['z1', 'z2']),
    ('path-clip-half-pixel', (0, 0, 361, 400), TALL, (361, 400), 'lr', ['z1', 'z2']),
]
by_key = {f['key']: f for f in files()}


def frame(build, key, framing):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{OUT}/{d}/{build}_{key}_{framing}.png'
        if os.path.exists(p):
            return p
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    os.makedirs(f'{OUT}/png_changed', exist_ok=True)
    ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, by_key[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra},
                   capture_output=True, text=True, timeout=600)
    Image.open(ppm).save(p)
    os.remove(ppm)
    return p


def cell(values):
    return ' '.join(('%.2f' % v).lstrip('0') if 0 < v < 0.995 else '%d' % round(v) for v in values)


columns = ['exact'] + [label for _, label in builds] + [names[r] for r in refs]
print('| probe | framing | ' + ' | '.join(columns) + ' |')
print('|---|---|' + '---|' * len(columns))
for name, (x, y, w, h), (pw, ph), (vw, vh), sides, framings in PROBES:
    key = f'corpus__clip-probes__{name}'
    for framing in framings:
        fr, z = FRAMINGS[framing]
        box, bx, by, fw, fh = (float(fr[k]) for k in ('BOX', 'BOX_X', 'BOX_Y', 'FRAME_W', 'FRAME_H'))
        # The viewBox centered in the viewport, the viewport fitted to the box, then the zoom about the box's
        # center - as the harness and make_ref.py frame a file.
        inner = min(pw / vw, ph / vh)
        ox, oy = (pw - vw * inner) / 2, (ph - vh * inner) / 2
        fit = box / max(pw, ph)
        cx, cy = bx + box / 2, by + box / 2
        dev = lambda u, offset, origin, c: c + (origin + (offset + u * inner) * fit - c) * z
        x0, x1 = dev(x, ox, bx, cx), dev(x + w, ox, bx, cx)
        y0, y1 = dev(y, oy, by, cy), dev(y + h, oy, by, cy)
        mx, my = int((max(x0, 0) + min(x1, fw)) / 2), int((max(y0, 0) + min(y1, fh)) / 2)
        at = {'l': (math.floor(x0), my, 1 - (x0 - math.floor(x0))), 'r': (math.floor(x1), my, x1 - math.floor(x1)),
              't': (mx, math.floor(y0), 1 - (y0 - math.floor(y0))), 'b': (mx, math.floor(y1), y1 - math.floor(y1))}
        row = [cell([at[s][2] for s in sides])]
        pictures = [frame(b, key, framing) for b, _ in builds] + [f'{REFS}/{r}_{key}_{framing}.png' for r in refs]
        for p in pictures:
            if not os.path.exists(p):
                row.append('')
                continue
            # Green (0, 128, 0) over white: the red channel is what the fill left uncovered.
            red = np.asarray(Image.open(p).convert('RGB'), dtype=np.float64)[..., 0]
            row.append(cell([1 - red[at[s][1], at[s][0]] / 255 for s in sides]))
        print(f'| `{name}` | {framing} | ' + ' | '.join(row) + ' |')
