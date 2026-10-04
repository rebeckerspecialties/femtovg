#!/usr/bin/env python3
"""The clip-edge probes (corpus/clip-probes) as ink: how much of the green fill each renderer drew at the fit,
against the exact area of what the clip leaves of it, in pixels. A renderer that covers each edge pixel by its share
inside is at 0; one that multiplies two coverages where a clip's edge and the content's (or two clips' edges)
coincide is short by about a sixth of a pixel per pixel of shared edge.

  probe_ink.py BUILD[=label]... [refs=chr,chg,ff] [framing=z1]"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image
from common import *

builds = [(a.split('=', 1) + [a])[:2] for a in sys.argv[1:] if not a.startswith(('refs=', 'framing='))]
opts = dict(a.split('=', 1) for a in sys.argv[1:] if a.startswith(('refs=', 'framing=')))
refs = opts.get('refs', 'chr,chg,ff').split(',')
framing = opts.get('framing', 'z1')
names = {'chr': 'Chromium software', 'chg': 'Chromium GPU', 'ff': 'Firefox'}
ROUND = (4 - math.pi) * 12 * 12  # what four corners of radius 12 leave out
# probe -> (exact area in its own units, the side of its viewBox that fits the 200 px box)
PROBES = {
    'rect-fill-fractional': (50.5 * 30.25, 200),
    'rect-clip-fractional': (50.5 * 30.25, 200),
    'rect-clip-coincident': (50.5 * 30.25, 200),
    'rounded-clip-coincident': (80.5 * 60.25 - ROUND, 200),
    'rotated-clip-coincident': (80.5 * 60.25, 200),
    'rect-clip-path-edge': (80.5 * 60.25, 200),
    'rect-clip-rect-inside': (40 * 20, 200),
    'rounded-clip-rect-inside': (40 * 28.4, 200),
    'nested-twin-clips': (50.5 * 30.25, 200),
    'nested-twin-rounded-clips': (80.5 * 60.25 - ROUND, 200),
    'viewport-fill': (173 * 131, 173),
    'viewport-overflow': (173 * 131, 173),
    'viewport-clip-twin': (173 * 131, 173),
    'viewport-clip-twin-fill': (173 * 131, 173),
}
by_key = {f['key']: f for f in files()}
fr, z = FRAMINGS[framing]


def frame(build, key):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{OUT}/{d}/{build}_{key}_{framing}.png'
        if os.path.exists(p):
            return p
    binary, extra = BUILDS[build]
    os.makedirs(f'{OUT}/png_changed', exist_ok=True)
    ppm = p[:-4] + '.ppm'
    subprocess.run([binary, f'{z:g}', ppm, by_key[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra},
                   capture_output=True, text=True, timeout=600)
    Image.open(ppm).save(p)
    os.remove(ppm)
    return p


def ink(p):
    # Green (0, 128, 0) over white: the red channel is what the fill left uncovered.
    return float((1 - np.asarray(Image.open(p).convert('RGB'), dtype=np.float64)[..., 0] / 255).sum())


columns = [label for _, label in builds] + [names[r] for r in refs]
print('| probe | exact px | ' + ' | '.join(columns) + ' |')
print('|---|---:|' + '---:|' * len(columns))
for name, (area, side) in PROBES.items():
    key = f'corpus__clip-probes__{name}'
    exact = area * (int(fr['BOX']) / side * z) ** 2
    cells = [ink(frame(b, key)) - exact for b, _ in builds]
    cells += [ink(f'{REFS}/{r}_{key}_{framing}.png') - exact if os.path.exists(f'{REFS}/{r}_{key}_{framing}.png') else None for r in refs]
    print(f'| `{name}` | {exact:.0f} | ' + ' | '.join('' if c is None else f'{c:+.1f}' for c in cells) + ' |')
