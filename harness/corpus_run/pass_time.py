#!/usr/bin/env python3
"""Steady-state frame time of two builds over the corpus frames a filter change can reach, for a change that is
meant to cost less and draw the same: every frame of every file that uses a filter is run with each build, one
process at a time, the builds alternating, FRAMES frames each and REPEATS times; a frame's time is the median.
Rows go to CORPUS_RUN_OUT/pass_time.jsonl; a second run resumes and prints the summary.

  pass_time.py BEFORE AFTER [frames=20] [repeats=3] [match=REGEX over the file's text] [keys=FILE] [framings=z1,hd]
               [env=NAME=VALUE,...] [out=NAME]

keys=FILE (a JSON list) times those files instead of the ones match finds; env adds to both builds' environment
(FRAME_DRIFT=0.37 moves the scene every frame, so nothing cached for one frame serves the next); out names the
rows' file, pass_time.jsonl by default."""
import collections, json, os, re, statistics, subprocess, sys
from common import *

before, after = sys.argv[1:3]
opts = dict(a.split('=', 1) for a in sys.argv[3:])
FRAMES, REPEATS = opts.get('frames', '20'), int(opts.get('repeats', 3))
by_key = {f['key']: f for f in files()}
path = f'{OUT}/{opts.get("out", "pass_time")}.jsonl'
EXTRA = dict(pair.split('=', 1) for pair in opts.get('env', '').split(',') if pair)
rows = [json.loads(l) for l in open(path)] if os.path.exists(path) else []
out = open(path, 'a')


def run(build, key, framing, frames):
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{OUT}/tmp/pt_{os.getpid()}_{build}_{abs(hash((key, framing))) % 10**9}.ppm'
    r = subprocess.run([binary, f'{z:g}', ppm, by_key[key]['path']], capture_output=True, text=True, timeout=900,
                       env={**os.environ, **fr, **SWEEP_ENV, **extra, **EXTRA, 'MEM_PEAKS': '1', 'MEM_SETTLE_MS': '0',
                            'FRAMES': str(frames)})
    if os.path.exists(ppm):
        os.remove(ppm)
    m = re.search(r'frame_ms=([\d.]+) passes=(\d+)', r.stderr)
    e = re.search(r'encode_ms=([\d.]+)', r.stderr)
    return (float(m.group(1)), int(m.group(2)), float(e.group(1)) if e else None) if m else None


match = re.compile(opts.get('match', r'filter\s*=|<filter\b'))
framings = opts['framings'].split(',') if 'framings' in opts else DEFAULT_FRAMINGS
if 'keys' in opts:
    wanted = set(json.load(open(opts['keys'])))
    selected = sorted((f['key'], fr) for f in files() if f['key'] in wanted for fr in framings)
else:
    selected = sorted((f['key'], fr) for f in files() if match.search(open(f['path'], errors='replace').read())
                      for fr in framings)
timed = collections.defaultdict(list)
passes, encoded = {}, collections.defaultdict(list)
for r in rows:
    if r['frames'] == FRAMES:
        timed[(r['key'], r['framing'], r['build'])].append(r['frame_ms'])
        if r.get('passes') is not None:
            passes[(r['key'], r['framing'], r['build'])] = r['passes']
        if r.get('encode_ms') is not None:
            encoded[(r['key'], r['framing'], r['build'])].append(r['encode_ms'])
for rep in range(REPEATS):
    for i, (k, f) in enumerate(selected):
        order = (before, after) if (i + rep) % 2 == 0 else (after, before)
        for b in order:
            if len(timed[(k, f, b)]) > rep:
                continue
            res = run(b, k, f, FRAMES)
            if res:
                timed[(k, f, b)].append(res[0])
                passes[(k, f, b)] = res[1]
                if res[2] is not None:
                    encoded[(k, f, b)].append(res[2])
                out.write(json.dumps({'key': k, 'framing': f, 'build': b, 'frames': FRAMES, 'frame_ms': res[0],
                                      'passes': res[1], 'encode_ms': res[2]}) + '\n')
                out.flush()

med = lambda k, f, b: statistics.median(timed[(k, f, b)])
done = [(k, f) for k, f in selected if timed[(k, f, before)] and timed[(k, f, after)]]
print(f'{len(selected)} frames of {len(set(k for k, _ in selected))} files; {len(done)} timed with both builds')
if done:
    tb, ta = sum(med(k, f, before) for k, f in done), sum(med(k, f, after) for k, f in done)
    faster = sum(med(k, f, after) < med(k, f, before) * 0.98 for k, f in done)
    slower = sum(med(k, f, after) > med(k, f, before) * 1.02 for k, f in done)
    print(f'steady-state frame time summed over them: {tb:.0f} ms -> {ta:.0f} ms ({100 * (ta - tb) / tb:+.1f} %); '
          f'{faster} frames more than 2 % faster, {slower} more than 2 % slower')
    for framing in framings:
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
    counted = [(k, f) for k, f in done if (k, f, before) in passes and (k, f, after) in passes]
    if counted:
        pb, pa = sum(passes[(k, f, before)] for k, f in counted), sum(passes[(k, f, after)] for k, f in counted)
        more = sum(passes[(k, f, after)] > passes[(k, f, before)] for k, f in counted)
        fewer = sum(passes[(k, f, after)] < passes[(k, f, before)] for k, f in counted)
        print(f'  render passes over {len(counted)} frames: {pb} -> {pa}; {fewer} frames with fewer, {more} with more')
    cpu = [(k, f) for k, f in done if encoded[(k, f, before)] and encoded[(k, f, after)]]
    if cpu:
        emed = lambda k, f, b: statistics.median(encoded[(k, f, b)])
        eb, ea = sum(emed(k, f, before) for k, f in cpu), sum(emed(k, f, after) for k, f in cpu)
        ratios = sorted(emed(k, f, after) / emed(k, f, before) for k, f in cpu)
        print(f'  encoding (recording and encoding a frame, before the submit) over {len(cpu)} frames: {eb:.0f} -> {ea:.0f} ms '
              f'({100 * (ea - eb) / eb:+.1f} %); median frame {100 * (ratios[len(ratios) // 2] - 1):+.1f} %')
    whole = sorted(med(k, f, after) / med(k, f, before) for k, f in done)
    print(f'  median frame: {100 * (whole[len(whole) // 2] - 1):+.1f} %; a tenth of the frames beyond '
          f'{100 * (whole[len(whole) // 10] - 1):+.1f} % and {100 * (whole[-(len(whole) // 10) - 1] - 1):+.1f} %')
    ratio = sorted((med(k, f, after) / med(k, f, before), k.split('__')[-1], f) for k, f in done)
    print('  largest savings:', [(f'{100 * (r - 1):+.0f} %', n, f) for r, n, f in ratio[:5]])
    print('  smallest:', [(f'{100 * (r - 1):+.0f} %', n, f) for r, n, f in ratio[-5:]])
