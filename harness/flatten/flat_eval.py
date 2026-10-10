#!/usr/bin/env python3
"""flat_eval.py VARIANT... : render every frame that has an area reference (refs/id_*) with the flattening experiment
binary (_logos_full_fx) under each variant's environment and record its distance from the area reference.
Rows: tmp/flat/eval.jsonl {variant, key, framing, far20, far8, sad}; a frame already recorded is not rendered again."""
import json, os, sys, subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'corpus_run'))
from common import OUT, FRAMINGS, SWEEP_ENV, BIN, files

VARIANTS = {
    'm': {'FEMTOVG_TESS_TOL': '0.25', 'FEMTOVG_JOIN_TOL': '0.25'},   # master, bit-identical to m7
    'p': {},                                                          # the PR (0.0625 bisection), bit-identical to m7f
    'nw10': {'FEMTOVG_FLAT_DEV': '0.10', 'FEMTOVG_JOIN_TOL': '0.10'},
    'nw08': {'FEMTOVG_FLAT_DEV': '0.08', 'FEMTOVG_JOIN_TOL': '0.08'},
    'nw06': {'FEMTOVG_FLAT_DEV': '0.06', 'FEMTOVG_JOIN_TOL': '0.06'},
    'nw08j25': {'FEMTOVG_FLAT_DEV': '0.08', 'FEMTOVG_JOIN_TOL': '0.25'},
    'nw12': {'FEMTOVG_FLAT_DEV': '0.12', 'FEMTOVG_JOIN_TOL': '0.12'},
    's25': {'_bin': 'fxs', 'FEMTOVG_TESS_TOL': '0.25', 'FEMTOVG_STRADDLE': '0.5', 'FEMTOVG_JOIN_TOL': '0.25'},
    's125': {'_bin': 'fxs', 'FEMTOVG_TESS_TOL': '0.125', 'FEMTOVG_STRADDLE': '0.5', 'FEMTOVG_JOIN_TOL': '0.125'},
    's25m': {'_bin': 'fxs', 'FEMTOVG_TESS_TOL': '0.25', 'FEMTOVG_STRADDLE': '0.375', 'FEMTOVG_JOIN_TOL': '0.25'},
    's25j': {'_bin': 'fxs', 'FEMTOVG_TESS_TOL': '0.25', 'FEMTOVG_STRADDLE': '0.5', 'FEMTOVG_JOIN_TOL': '0.0625'},
    'fc': {'_bin': 'fc'},   # option C on master (flatten-straddle-half 297bf9a)
    'c2': {'_bin': 'c2'},
    'm8': {'_bin': 'm8'},   # upstream master d70ffeb, all cfgs
    'pr2': {'_bin': 'pr2'}, # straddled-chords (option C) on fill-point-costs, all cfgs   # option C v2 on savings v3 (point-costs-3-straddle 36f8a18): per-point straddle, grown gate
}
path = f'{OUT}/tmp/flat/eval.jsonl'
done = set()
if os.path.exists(path):
    for l in open(path):
        r = json.loads(l); done.add((r['variant'], r['key'], r['framing']))
by_key = {f['key']: f for f in files()}
frames = []
for name in sorted(os.listdir(f'{OUT}/refs')):
    if not name.startswith('id_') or not name.endswith('.png'):
        continue
    stem = name[3:-4]; key, framing = stem.rsplit('_', 1)
    if key in by_key and framing in FRAMINGS:
        frames.append((key, framing))
out = open(path, 'a')

def one(job):
    v, key, framing = job
    fr, z = FRAMINGS[framing]
    ppm = f'{OUT}/tmp/flat/{v}_{os.getpid()}_{abs(hash((key, framing))) % 10**9}.ppm'
    var = dict(VARIANTS[v]); binary = var.pop('_bin', 'fx')
    env = {**os.environ, **fr, **SWEEP_ENV, 'SINGLE_SHADOW_LAYER': '1', **var}
    subprocess.run([f'{BIN}/_logos_full_{binary}', f'{z:g}', ppm, by_key[key]['path']], env=env, capture_output=True, timeout=900)
    if not os.path.exists(ppm):
        return None
    a = np.asarray(Image.open(ppm).convert('RGB'), dtype=np.int16); os.remove(ppm)
    r = np.asarray(Image.open(f'{OUT}/refs/id_{key}_{framing}.png').convert('RGB'), dtype=np.int16)
    h, w = min(a.shape[0], r.shape[0]), min(a.shape[1], r.shape[1])
    d = np.abs(a[:h, :w] - r[:h, :w]).max(axis=2)
    return {'variant': v, 'key': key, 'framing': framing, 'far20': int((d > 20).sum()), 'far8': int((d > 8).sum()), 'sad': int(d.sum())}

jobs = [(v, k, f) for v in sys.argv[1:] for k, f in frames if (v, k, f) not in done]
print(len(frames), 'frames;', len(jobs), 'renders to do', flush=True)
with ThreadPoolExecutor(int(os.environ.get('JOBS', 6))) as ex:
    for i, r in enumerate(ex.map(one, jobs)):
        if r:
            out.write(json.dumps(r) + '\n'); out.flush()
        if i % 500 == 0:
            print(i, flush=True)
