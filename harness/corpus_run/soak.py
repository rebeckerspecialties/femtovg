#!/usr/bin/env python3
"""Persistent-canvas soak of the whole corpus per build, with per-frame peak memory.

  soak.py run BUILD[,BUILD...] [hd]   three passes over every file on one canvas, never recreated;
                                      default framing at zooms 1,2,4, or the 1080p framing at zoom 1
  soak.py report                      per build: time, peaks, what is still held, growth across passes
"""
import csv, os, statistics, subprocess, sys
from common import *

MiB = 1048576.0
LIST = f'{OUT}/soak_list.txt'


def run(builds, hd):
    if not os.path.exists(LIST):
        open(LIST, 'w').write('\n'.join(f['path'] for f in files()) + '\n')
    for b in builds:
        binary, extra = BUILDS[b]
        fr = HD if hd else DEFAULT
        out = f'{OUT}/soak_{b}_{"hd" if hd else "zooms"}.csv'
        env = {**os.environ, **fr, 'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'MEM_PEAKS': '1',
               'SOAK_PASSES': '3', 'SOAK_ZOOMS': '1' if hd else '1,2,4', **extra}
        r = subprocess.run(['/usr/bin/time', '-l', binary, 'soak', out, LIST], env=env, capture_output=True, text=True)
        peak = [l.strip() for l in r.stderr.splitlines() if 'peak memory footprint' in l or 'maximum resident' in l]
        print(b, 'hd' if hd else 'zooms', 'rc', r.returncode, peak, flush=True)


def report():
    for name in sorted(os.listdir(OUT)):
        if not (name.startswith('soak_') and name.endswith('.csv')):
            continue
        # File names may hold commas: the pass leads, the 13 fields after the name are numeric.
        lines = open(f'{OUT}/{name}').read().splitlines()
        header = lines[0].split(',')
        rows = []
        for line in lines[1:]:
            parts = line.split(',')
            rows.append(dict(zip(header, [parts[0], ','.join(parts[1:-13])] + parts[-13:])))
        if not rows:
            continue
        f = lambda r, k: float(r[k])
        wall = [f(r, 'wall_ms') for r in rows]
        cpu = [f(r, 'cpu_ms') for r in rows]
        fp = [f(r, 'peak_footprint') / MiB for r in rows]
        g = [f(r, 'peak_graphics') / MiB for r in rows]
        c = [f(r, 'peak_cpu') / MiB for r in rows]
        passes = sorted({r['pass'] for r in rows})
        per_pass = []
        for p in passes:
            sel = [r for r in rows if r['pass'] == p]
            per_pass.append((max(f(r, 'peak_footprint') for r in sel) / MiB, statistics.median(f(r, 'footprint_after') for r in sel) / MiB,
                             f(sel[-1], 'footprint_after') / MiB, sum(f(r, 'wall_ms') for r in sel) / 1000))
        ws = sorted(wall)
        print(f'{name[5:-4]:22s} frames {len(rows):5d}  wall {sum(wall) / 1000:6.1f} s  cpu {sum(cpu) / 1000:6.1f} s  frame ms p50 {ws[len(ws) // 2]:6.2f} p99 {ws[int(len(ws) * .99)]:7.1f} max {ws[-1]:7.1f}')
        print(f'{"":22s} peak footprint {max(fp):6.0f} MiB (graphics {max(g):6.0f}, cpu {max(c):5.0f}); render passes max {max(int(r["passes"]) for r in rows)}')
        for p, (mx, med_after, last_after, secs) in zip(passes, per_pass):
            print(f'{"":22s} pass {p}: peak {mx:6.0f} MiB, held after a frame median {med_after:6.0f}, held after the last frame {last_after:6.0f}, {secs:5.1f} s')


if sys.argv[1] == 'run':
    run(sys.argv[2].split(','), len(sys.argv) > 3 and sys.argv[3] == 'hd')
else:
    report()
