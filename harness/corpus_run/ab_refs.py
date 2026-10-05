#!/usr/bin/env python3
"""Two builds against every reference, over the frames they differ on (by the hashes accuracy.py recorded):
software Chromium (chr), GPU-rasterized Chromium (chg, refs_gpu.py) and Firefox (ff). Frames accuracy.py kept
(png=DIR) are read; the rest are rendered into CORPUS_RUN_OUT/png_changed. Prints, per reference, how many changed
frames move toward it and away from it by the share of pixels beyond 20/255, the frames that move away most, and
over the pixels the two builds differ on how many end nearer the reference and how far from it they are in all.

  ab_refs.py BEFORE AFTER [refs=chr,chg,ff] [worst=N]"""
import collections, json, os, statistics, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from common import *

before, after = sys.argv[1:3]
opts = dict(a.split('=', 1) for a in sys.argv[3:])
refs = opts.get('refs', 'chr,chg,ff').split(',')
worst = int(opts.get('worst', 8))
names = {'chr': 'Chromium (software)', 'chg': 'Chromium (GPU)', 'ff': 'Firefox', 'wk': 'WebKit', 'id': 'Area reference'}
by_key = {f['key']: f for f in files()}
rec = {}
for line in open(f'{OUT}/accuracy.jsonl'):
    r = json.loads(line)
    if r['build'] in (before, after):
        rec[(r['build'], r['key'], r['framing'])] = r
both = sorted((k, f) for (b, k, f) in rec if b == before and (after, k, f) in rec)
changed = [x for x in both if rec[(before,) + x].get('hash') != rec[(after,) + x].get('hash')]
os.makedirs(f'{OUT}/png_changed', exist_ok=True)


def frame(job):
    build, key, framing = job
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{OUT}/{d}/{build}_{key}_{framing}.png'
        if os.path.exists(p):
            return p
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{OUT}/png_changed/{build}_{key}_{framing}.ppm'
    r = subprocess.run([binary, f'{z:g}', ppm, by_key[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra},
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not os.path.exists(ppm):
        return None
    Image.open(ppm).save(p)
    os.remove(ppm)
    return p


with ThreadPoolExecutor(6) as ex:
    paths = dict(zip([(b,) + x for x in changed for b in (before, after)],
                     ex.map(frame, [(b,) + x for x in changed for b in (before, after)])))


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def beyond(a, b):
    return 100 * float((np.abs(a - b).max(axis=2) > 20).mean())


print(f'{before} -> {after}: {len(both)} frames of {len(set(k for k, _ in both))} files with both builds; '
      f'{len(both) - len(changed)} bit-identical, {len(changed)} changed in {len(set(k for k, _ in changed))} files')
rows = collections.defaultdict(list)
moved = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0])  # pixels nearer, farther, as far; distance before, after
for x in changed:
    pb, pa = paths[(before,) + x], paths[(after,) + x]
    if not pb or not pa:
        continue
    b, a = load(pb), load(pa)
    for ref in refs:
        p = f'{REFS}/{ref}_{x[0]}_{x[1]}.png'
        if os.path.exists(p):
            r = load(p)
            if r.shape == b.shape:
                rows[ref].append((beyond(a, r) - beyond(b, r), beyond(b, r), beyond(a, r), x))
                differ = (a != b).any(axis=2)
                db, da_ = np.abs(b - r).max(axis=2)[differ], np.abs(a - r).max(axis=2)[differ]
                m = moved[ref]
                m[0] += int((da_ < db).sum()); m[1] += int((da_ > db).sum()); m[2] += int((da_ == db).sum())
                m[3] += float(db.sum()); m[4] += float(da_.sum())
for ref in refs:
    d = [row[0] for row in rows[ref]]
    if not d:
        continue
    print(f'\n{names[ref]}: {len(d)} changed frames compared; toward {sum(v < -0.005 for v in d)}, away '
          f'{sum(v > 0.005 for v in d)}, level {sum(abs(v) <= 0.005 for v in d)}; by more than 0.1 points: toward '
          f'{sum(v < -0.1 for v in d)}, away {sum(v > 0.1 for v in d)}; median {statistics.median(d):+.3f}')
    nearer, farther, same, far_before, far_after = moved[ref]
    pixels = max(nearer + farther + same, 1)
    print(f'   of {pixels} pixels that differ between the builds: {nearer} nearer the reference, {farther} farther, '
          f'{same} as far; mean distance {far_before / pixels:.1f} -> {far_after / pixels:.1f} of 255')
    for delta, vb, va, (key, framing) in sorted(rows[ref], reverse=True)[:worst]:
        if delta > 0.005:
            print(f'   away {delta:+.3f}: {key.split("__")[-1]} {framing}  {vb:.2f} % -> {va:.2f} %')
