#!/usr/bin/env python3
"""bench.py A B PAIRS FRAMES file...  - paired 1080p timings of two builds from common.BUILDS."""
import os, re, statistics as st, subprocess, sys
from common import *
a, b, pairs, frames = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
def run(build, f):
    binary, extra = BUILDS[build]
    env = {**os.environ, **HD, **SWEEP_ENV, **extra, 'MEM_PEAKS': '1', 'MEM_SETTLE_MS': '0', 'FRAMES': frames}
    for key in os.environ.get('BENCH_UNSET', '').split(','):
        env.pop(key, None)
    r = subprocess.run([binary, '1', f'{OUT}/tmp/bench.ppm', f], env=env, capture_output=True, text=True)
    return float(re.search(os.environ.get('BENCH_FIELD', 'frame_ms') + r'=([\d.]+)', r.stderr).group(1))
for f in sys.argv[5:]:
    x, y = [], []
    for i in range(pairs):
        if i % 2 == 0: p = run(a, f); q = run(b, f)
        else: q = run(b, f); p = run(a, f)
        x.append(p); y.append(q)
    d = [q - p for p, q in zip(x, y)]
    print(f"{os.path.basename(f)[:-4]}: {a} {st.median(x):.3f} {b} {st.median(y):.3f} ms | paired difference median {st.median(d):+.3f} ms ({100 * st.median(d) / st.median(x):+.1f} %), slower in {sum(v > 0 for v in d)} of {len(d)}", flush=True)
