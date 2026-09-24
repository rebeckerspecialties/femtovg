#!/usr/bin/env python3
"""Run a reftest suite: render each test and its -ref.svg with BINARY at the
default 460x260 framing (zoom 1), compare them (pixels beyond THRESHOLD/255),
and, with --chromium, also compare Chromium's renders of the pair and the
binary's test against Chromium's test.
  reftest.py BINARY SUITE_DIR [--threshold 8] [--chromium] [--out DIR]
Pass = test vs ref at most 0.5 % of pixels beyond the threshold."""
import argparse, glob, os, subprocess, sys
import numpy as np
from PIL import Image
CHR = os.path.expanduser('~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell')
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('binary'); ap.add_argument('suite'); ap.add_argument('--threshold', type=int, default=8)
ap.add_argument('--chromium', action='store_true'); ap.add_argument('--out', default='/tmp/reftest')
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
env = dict(os.environ, SKIP_UNSUPPORTED_FILTERS='1', VIEWPORT_CLIP='1')
def render(svg, out):
    subprocess.run([args.binary, '1', out, svg], env=env, capture_output=True)
    return np.asarray(Image.open(out).convert('RGB'), dtype=np.int16)
def chromium(svg, out):
    html = out + '.html'
    with open(html, 'w') as f:
        subprocess.run([sys.executable, os.path.join(HERE, 'make_ref.py'), svg, '1'], stdout=f, check=True)
    for attempt in range(3):
        subprocess.run([CHR, '--headless', '--disable-gpu', f'--screenshot={out}', '--window-size=460,260',
                        '--default-background-color=FFFFFFFF', 'file://' + html], capture_output=True)
        px = np.asarray(Image.open(out).convert('RGB'), dtype=np.int16)
        if px.min() != px.max():
            return px
        print(f'chromium returned a blank screenshot for {svg} (attempt {attempt + 1})', file=sys.stderr)
    sys.exit(f'chromium kept returning blank screenshots for {svg}')
def pct(a, b): return float((np.abs(a - b).max(axis=2) > args.threshold).mean() * 100)
tests = sorted(t for t in glob.glob(os.path.join(args.suite, '**', '*.svg'), recursive=True) if not t.endswith('-ref.svg'))
passed = 0
for t in tests:
    name = os.path.splitext(os.path.basename(t))[0]; ref = t[:-4] + '-ref.svg'
    a = render(t, f'{args.out}/{name}.ppm'); b = render(ref, f'{args.out}/{name}-ref.ppm')
    own = pct(a, b); ok = own <= 0.5; passed += ok
    line = f'{"pass" if ok else "FAIL"} {name}: test vs ref {own:.2f} %'
    if args.chromium:
        ca = chromium(t, f'{args.out}/chr_{name}.png'); cb = chromium(ref, f'{args.out}/chr_{name}-ref.png')
        line += f' | chromium test vs ref {pct(ca, cb):.2f} % | test vs chromium {pct(a, ca):.2f} %'
    print(line)
print(f'{passed}/{len(tests)} pass')
