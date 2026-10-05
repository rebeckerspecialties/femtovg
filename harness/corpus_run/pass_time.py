#!/usr/bin/env python3
"""Steady-state frame time of two builds over the corpus frames a filter change can reach, for a change that is
meant to cost less and draw the same: every frame of every file that uses a filter is run with each build, one
process at a time, the builds alternating, FRAMES frames each and REPEATS times; a frame's time is the median.
Rows go to CORPUS_RUN_OUT/pass_time.jsonl; a second run resumes and prints the summary.

  pass_time.py BEFORE AFTER [frames=20] [repeats=3] [match=REGEX over the file's text]"""
import collections, json, os, re, statistics, subprocess, sys
from common import *

before, after = sys.argv[1:3]
opts = dict(a.split('=', 1) for a in sys.argv[3:])
FRAMES, REPEATS = opts.get('frames', '20'), int(opts.get('repeats', 3))
by_key = {f['key']: f for f in files()}
path = f'{OUT}/pass_time.jsonl'
rows = [json.loads(l) for l in open(path)] if os.path.exists(path) else []
out = open(path, 'a')


def run(build, key, framing, frames):
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{OUT}/tmp/pt_{os.getpid()}_{build}_{abs(hash((key, framing))) % 10**9}.ppm'
    r = subprocess.run([binary, f'{z:g}', ppm, by_key[key]['path']], capture_output=True, text=True, timeout=900,
                       env={**os.environ, **fr, **SWEEP_ENV, **extra, 'MEM_PEAKS': '1', 'MEM_SETTLE_MS': '0', 'FRAMES': str(frames)})
    if os.path.exists(ppm):
        os.remove(ppm)
    m = re.search(r'frame_ms=([\d.]+) passes=(\d+)', r.stderr)
    return (float(m.group(1)), int(m.group(2))) if m else None


match = re.compile(opts.get('match', r'filter\s*=|<filter\b'))
selected = sorted((f['key'], fr) for f in files() if match.search(open(f['path'], errors='replace').read())
                  for fr in DEFAULT_FRAMINGS)
timed = collections.defaultdict(list)
for r in rows:
    if r['frames'] == FRAMES:
        timed[(r['key'], r['framing'], r['build'])].append(r['frame_ms'])
for rep in range(REPEATS):
    for i, (k, f) in enumerate(selected):
        order = (before, after) if (i + rep) % 2 == 0 else (after, before)
        for b in order:
            if len(timed[(k, f, b)]) > rep:
                continue
            res = run(b, k, f, FRAMES)
            if res:
                timed[(k, f, b)].append(res[0])
                out.write(json.dumps({'key': k, 'framing': f, 'build': b, 'frames': FRAMES, 'frame_ms': res[0]}) + '\n')
                out.flush()

med = lambda k, f, b: statistics.median(timed[(k, f, b)])
done = [(k, f) for k, f in selected if timed[(k, f, before)] and timed[(k, f, after)]]
print(f'{len(selected)} frames of {len(set(k for k, _ in selected))} files that use a filter; {len(done)} timed with both builds')
if done:
    tb, ta = sum(med(k, f, before) for k, f in done), sum(med(k, f, after) for k, f in done)
    faster = sum(med(k, f, after) < med(k, f, before) * 0.98 for k, f in done)
    slower = sum(med(k, f, after) > med(k, f, before) * 1.02 for k, f in done)
    print(f'steady-state frame time summed over them: {tb:.0f} ms -> {ta:.0f} ms ({100 * (ta - tb) / tb:+.1f} %); '
          f'{faster} frames more than 2 % faster, {slower} more than 2 % slower')
    for framing in DEFAULT_FRAMINGS:
        sel = [(k, f) for k, f in done if f == framing]
        if sel:
            tb, ta = sum(med(k, f, before) for k, f in sel), sum(med(k, f, after) for k, f in sel)
            print(f'  {framing}: {len(sel)} frames, {tb:.0f} -> {ta:.0f} ms ({100 * (ta - tb) / tb:+.1f} %)')
    groups = collections.defaultdict(lambda: [0.0, 0.0, 0])
    group_of = {f['key']: f['group'] for f in files()}
    for k, f in done:
        g = groups[group_of[k]]
        g[0] += med(k, f, before); g[1] += med(k, f, after); g[2] += 1
    for name, (tb, ta, n) in sorted(groups.items(), key=lambda kv: kv[1][1] - kv[1][0]):
        print(f'  {name}: {n} frames, {tb:.0f} -> {ta:.0f} ms ({100 * (ta - tb) / tb:+.1f} %)')
    ratio = sorted((med(k, f, after) / med(k, f, before), k.split('__')[-1], f) for k, f in done)
    print('  largest savings:', [(f'{100 * (r - 1):+.0f} %', n, f) for r, n, f in ratio[:5]])
    print('  smallest:', [(f'{100 * (r - 1):+.0f} %', n, f) for r, n, f in ratio[-5:]])
