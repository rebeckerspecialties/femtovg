#!/usr/bin/env python3
"""gl_instr.py BUILD... -- scene... : instructions retired per frame of $HARNESS_BIN/gl_fill_bench_BUILD (long minus
short run, LO and HI frames, REPEATS times; macOS /usr/bin/time -l). Build them with harness/build.sh --gl."""
import os, re, subprocess, sys
args = sys.argv[1:]; i = args.index('--'); builds, scenes = args[:i], args[i + 1:]
lo, hi = int(os.environ.get('LO', 50)), int(os.environ.get('HI', 450))
B = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'bin'))
def run(build, scene, frames):
    r = subprocess.run(['/usr/bin/time', '-l', f'{B}/gl_fill_bench_{build}', scene, str(frames)], capture_output=True, text=True, timeout=900)
    g = lambda name: int(re.search(r'(\d+)\s+' + name, r.stderr).group(1))
    return g('instructions retired'), g('cycles elapsed')
for s in scenes:
    for b in builds:
        rows = []
        for _ in range(int(os.environ.get('REPEATS', 3))):
            (i0, c0), (i1, c1) = run(b, s, lo), run(b, s, hi)
            rows.append(((i1 - i0) / (hi - lo), (c1 - c0) / (hi - lo)))
        ins = sorted(r[0] for r in rows); cyc = sorted(r[1] for r in rows)
        print(f"GL {s:18s} {b:6s} instructions/frame {ins[len(ins)//2]/1e6:8.3f} M (spread {100*(ins[-1]-ins[0])/ins[0]:.2f} %)  cycles/frame {cyc[len(cyc)//2]/1e6:8.3f} M", flush=True)
