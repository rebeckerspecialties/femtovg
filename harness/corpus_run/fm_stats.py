"""fm_stats.py BUILD [framing=z1] [group=NAME]  - how many fills a FILL_MASKS build draws through masks and what the
masks hold, per corpus file (MASK_STATS=1): totals, and the distribution over files."""
import json, os, re, subprocess, sys, statistics
from concurrent.futures import ThreadPoolExecutor
from common import *
build = sys.argv[1]
opts = dict(a.split('=', 1) for a in sys.argv[2:])
framing = opts.get('framing', 'z1')
fs = [f for f in files() if not opts.get('group') or f['key'].split('__')[1] == opts['group']]
binary, extra = BUILDS[build]; fr, z = FRAMINGS[framing]
def one(f):
    out = f"/tmp/fm_stats_{os.getpid()}_{abs(hash(f['key']))}.ppm"
    r = subprocess.run([binary, f'{z:g}', out, f['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra, 'MASK_STATS': '1'}, capture_output=True, text=True)
    try: os.remove(out)
    except OSError: pass
    m = re.search(r'MASKS bytes=(\d+) budget=(\d+) fills=(\d+) through_masks=(\d+)', r.stderr)
    return (f['key'], tuple(int(g) for g in m.groups())) if m else (f['key'], None)
with ThreadPoolExecutor(4) as ex:
    rows = [r for r in ex.map(one, fs) if r[1]]
frames = int(os.environ.get('FRAMES_PER_RUN', '0')) or None
by = sorted(rows, key=lambda r: -r[1][3])
tot_f = sum(r[1][2] for r in rows); tot_m = sum(r[1][3] for r in rows)
with_m = [r for r in rows if r[1][3]]
print(f'{build} {framing}: {len(rows)} files; fills {tot_f}, through masks {tot_m} ({100 * tot_m / max(tot_f, 1):.1f} %); files with any {len(with_m)}')
if with_m:
    b = sorted(r[1][0] for r in with_m)
    print(f'  mask bytes over files with any: median {statistics.median(b) / 1024:.1f} KiB, max {b[-1] / 1048576:.2f} MiB of a budget of {with_m[0][1][1] / 1048576:.0f} MiB')
    print('  most masked fills:', [(k.split('__')[-1], v[3], v[2]) for k, v in by[:8]])
