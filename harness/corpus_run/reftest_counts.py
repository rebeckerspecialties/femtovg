#!/usr/bin/env python3
"""Reftest counts for two builds from the frames accuracy.py kept (png=png_wpt under CORPUS_RUN_OUT):
- the tests of one reftest group within 0.15 % of pixels beyond 20/255 of each reference at every framing
  (software Chromium, GPU Chromium, Firefox), and how many the references agree on among themselves;
- the suite's test/reference pairs (its test-manifest.json) whose two frames agree within 0.15 % at every framing.

  reftest_counts.py BEFORE AFTER [group=wpt-clip-path-reftests] [suite=DIR]"""
import collections, json, os, sys
import numpy as np
from PIL import Image
from common import *

before, after = sys.argv[1:3]
opts = dict(a.split('=', 1) for a in sys.argv[3:])
group = opts.get('group', 'wpt-clip-path-reftests')
suite = os.path.expanduser(opts.get('suite', os.environ.get('WPT_SVG_REFTESTS', 'wpt_svg_reftests')))
names = {'chr': 'Chromium software', 'chg': 'Chromium GPU', 'ff': 'Firefox', 'wk': 'WebKit', 'id': 'the area reference'}
fs = files()


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16) if os.path.exists(p) else None


def beyond(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return 100 * float((np.abs(a - b).max(axis=2) > 20).mean())


def frame(build, key, framing):
    return load(f'{OUT}/png_wpt/{build}_{key}_{framing}.png')


def ref(browser, key, framing):
    return load(f'{REFS}/{browser}_{key}_{framing}.png')


def within(values):
    return len(values) == len(DEFAULT_FRAMINGS) and all(v is not None and v <= 0.15 for v in values)


tests = sorted(f['key'] for f in fs if f['group'] == group and not f['key'].endswith('-ref'))
print(f'{group}: {len(tests)} tests; within 0.15 % at every framing, {before} -> {after}')
for browser in ('chr', 'chg', 'ff', 'wk', 'id'):
    counts = [sum(within([beyond(frame(b, k, fr), ref(browser, k, fr)) for fr in DEFAULT_FRAMINGS]) for k in tests)
              for b in (before, after)]
    print(f'  of {names[browser]}: {counts[0]} -> {counts[1]}')
# The browsers themselves against the area reference (refs_ideal.py), where every framing has one.
for browser in ('chr', 'chg', 'ff', 'wk'):
    print(f'  {names[browser]} within 0.15 % of the area reference: '
          f'{sum(within([beyond(ref(browser, k, fr), ref("id", k, fr)) for fr in DEFAULT_FRAMINGS]) for k in tests)}')
for a, b in (('chr', 'chg'), ('chr', 'ff'), ('chg', 'ff')):
    agree = sum(within([beyond(ref(a, k, fr), ref(b, k, fr)) for fr in DEFAULT_FRAMINGS]) for k in tests)
    print(f'  {names[a]} and {names[b]} agree on {agree}')

manifest = json.load(open(f'{suite}/test-manifest.json'))
by_base = collections.defaultdict(list)
for f in fs:
    by_base[f['key'].split('__')[-1]].append(f['key'])


def key_of(path):
    hits = by_base.get(os.path.basename(path)[:-4], [])
    return hits[0] if len(hits) == 1 else None


pairs = [(key_of(t['test_file']), key_of(t['ref_file'])) for t in manifest['tests']]
pairs = [(t, r) for t, r in pairs if t and r]
print(f'{len(pairs)} test/reference pairs; the two frames within 0.15 % at every framing:')
for label, build in ((before, before), (after, after)) + tuple((names[r], r) for r in ('chr', 'chg', 'ff')):
    get = (lambda k, fr, b=build: ref(b, k, fr)) if build in names else (lambda k, fr, b=build: frame(b, k, fr))
    values = [[beyond(get(t, fr), get(r, fr)) for fr in DEFAULT_FRAMINGS] for t, r in pairs]
    have = [v for v in values if all(x is not None for x in v)]
    print(f'  {label}: {sum(within(v) for v in have)} of {len(have)}')
