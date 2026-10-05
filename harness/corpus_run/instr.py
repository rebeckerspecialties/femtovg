#!/usr/bin/env python3
"""instr.py BUILD... -- file...  : instructions retired and cycles per frame (difference of a long and a short run)."""
import os, re, subprocess, sys
from common import *
args = sys.argv[1:]; i = args.index('--'); builds, files_ = args[:i], args[i + 1:]
lo, hi = int(os.environ.get('LO', 200)), int(os.environ.get('HI', 1200))
def run(build, f, frames):
    binary, extra = BUILDS[build]
    env = {**os.environ, **HD, **SWEEP_ENV, **extra, 'FRAMES': str(frames)}
    for key in os.environ.get('BENCH_UNSET', '').split(','):
        env.pop(key, None)
    r = subprocess.run(['/usr/bin/time', '-l', binary, '1', f'{OUT}/tmp/bench.ppm', f], env=env, capture_output=True, text=True)
    g = lambda name: int(re.search(r'(\d+)\s+' + name, r.stderr).group(1))
    return g('instructions retired'), g('cycles elapsed')
for f in files_:
    for b in builds:
        rows = []
        for _ in range(int(os.environ.get('REPEATS', 3))):
            (i0, c0), (i1, c1) = run(b, f, lo), run(b, f, hi)
            rows.append(((i1 - i0) / (hi - lo), (c1 - c0) / (hi - lo)))
        ins = sorted(r[0] for r in rows); cyc = sorted(r[1] for r in rows)
        print(f"{os.path.basename(f)[:-4]:32s} {b:10s} instructions/frame {ins[len(ins)//2]/1e6:8.3f} M (spread {100*(ins[-1]-ins[0])/ins[0]:.2f} %)  cycles/frame {cyc[len(cyc)//2]/1e6:8.3f} M", flush=True)
