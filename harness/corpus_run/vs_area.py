#!/usr/bin/env python3
"""Every renderer against the area reference (refs_ideal.py), over the frames two builds differ on: the share of
each frame's pixels more than 20/255 from the reference, summed as pixels and averaged over the frames, for the two
builds and for each browser at one device pixel - what a clip's edge is off by where the browsers' own
antialiasing meets it, next to what the builds are off by.

  vs_area.py BEFORE AFTER [refs=chr,chg,ff,wk] [rows=NAME:FRAMING,...]"""
import collections, json, os, sys
import numpy as np
from PIL import Image
from common import *

before, after = sys.argv[1:3]
opts = dict(a.split('=', 1) for a in sys.argv[3:])
refs = opts.get('refs', 'chr,chg,ff,wk').split(',')
names = {'chr': 'Chromium software', 'chg': 'Chromium GPU', 'ff': 'Firefox', 'wk': 'WebKit'}
rec = {}
for line in open(f'{OUT}/accuracy.jsonl'):
    r = json.loads(line)
    if r['build'] in (before, after):
        rec[(r['build'], r['key'], r['framing'])] = r.get('hash')
changed = sorted((k, f) for (b, k, f), h in rec.items() if b == before and rec.get((after, k, f)) not in (None, h))


def load(prefix, key, framing):
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed', 'refs'):
        p = f'{OUT}/{d}/{prefix}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    return None


def beyond(a, b):
    return int((np.abs(a - b).max(axis=2) > 20).sum())


who = [before, after] + refs
rows = []
for key, framing in changed:
    area = load('id', key, framing)
    pictures = {w: load(w, key, framing) for w in who}
    if area is None or any(p is None or p.shape != area.shape for p in pictures.values()):
        continue
    rows.append((key, framing, area.shape[0] * area.shape[1], {w: beyond(p, area) for w, p in pictures.items()}))
print(f'{before} -> {after}: {len(changed)} changed frames, {len(rows)} with the area reference and every renderer')
print('| renderer | pixels beyond 20/255 of the area reference | mean share of a frame | frames it is nearest on |')
print('|---|---:|---:|---:|')
nearest = collections.Counter()
for _, _, _, counts in rows:
    best = min(counts.values())
    for w, c in counts.items():
        if c == best:
            nearest[w] += 1
for w in who:
    total = sum(counts[w] for _, _, _, counts in rows)
    share = 100 * sum(counts[w] / size for _, _, size, counts in rows) / max(len(rows), 1)
    print(f'| {names.get(w, w)} | {total} | {share:.3f} % | {nearest[w]} |')
for want in filter(None, opts.get('rows', '').split(',')):
    name, framing = want.split(':')
    for key, f, size, counts in rows:
        if f == framing and key.split('__')[-1] == name:
            print(f'{name} {framing}: ' + ', '.join(f'{names.get(w, w)} {100 * c / size:.2f} %' for w, c in counts.items()))
