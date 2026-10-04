#!/usr/bin/env python3
"""Steady-state frame time of two harness builds on the wgpu backend, back to back with the order alternating, and
the paired differences: `paired.py PAIRS FRAMES file...` (1080p, bin/_logos_full_master and bin/_logos_full_ca)."""
import os, re, statistics as st, subprocess, sys
B = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'bin'))
env = {**os.environ, 'FRAME_W': '1920', 'FRAME_H': '1080', 'BOX': '1080', 'BOX_X': '420', 'BOX_Y': '0', 'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'LAYER_STATS': '1', 'MEM_PEAKS': '1', 'FRAMES': sys.argv[2]}
def run(b, f):
    r = subprocess.run([f'{B}/_logos_full_{b}', '1', '/tmp/bench_out.ppm', f], env=env, capture_output=True, text=True, timeout=600)
    return float(re.search(r'frame_ms=([\d.]+)', r.stderr).group(1))
for f in sys.argv[3:]:
    m, c = [], []
    for i in range(int(sys.argv[1])):
        if i % 2 == 0: a = run('master', f); b = run('ca', f)
        else: b = run('ca', f); a = run('master', f)
        m.append(a); c.append(b)
    d = [y - x for x, y in zip(m, c)]
    print(f"{os.path.basename(f)[:-4]}: master {st.median(m):.3f} PR {st.median(c):.3f} | paired difference median {st.median(d):+.3f} ms ({100 * st.median(d) / st.median(m):+.1f} %), PR slower in {sum(x > 0 for x in d)} of {len(d)} pairs, range {min(d):+.3f}..{max(d):+.3f}", flush=True)
