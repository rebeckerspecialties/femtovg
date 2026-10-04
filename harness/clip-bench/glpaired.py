#!/usr/bin/env python3
"""Frame time of two gl_fill_bench builds (bin/gl_fill_bench_A and _B) on the OpenGL backend, back to back with the
order alternating, and the paired differences: `glpaired.py A B PAIRS FRAMES scene...`."""
import os, re, statistics as st, subprocess, sys
B = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'bin'))
a, b, pairs, frames = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
def run(build, scene):
    r = subprocess.run([f'{B}/gl_fill_bench_{build}', scene, frames], capture_output=True, text=True, timeout=600)
    return float(re.search(r'frame_ms=([\d.]+)', r.stdout).group(1))
for scene in sys.argv[5:]:
    x, y = [], []
    for i in range(pairs):
        if i % 2 == 0: p = run(a, scene); q = run(b, scene)
        else: q = run(b, scene); p = run(a, scene)
        x.append(p); y.append(q)
    d = [q - p for p, q in zip(x, y)]
    print(f"GL {scene}: {a} {st.median(x):.3f} {b} {st.median(y):.3f} | paired difference median {st.median(d):+.3f} ms ({100 * st.median(d) / st.median(x):+.1f} %), {b} slower in {sum(v > 0 for v in d)} of {len(d)} pairs, range {min(d):+.3f}..{max(d):+.3f}", flush=True)
