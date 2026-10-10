#!/usr/bin/env python3
"""accuracy.py for several builds at once, in parallel, keeping frames only where they matter.

  sweep.py BUILD[,BUILD...] [workers=6] [base=BUILD]

Rows are appended to CORPUS_RUN_OUT/accuracy.jsonl exactly as accuracy.py writes them (same render, same
compare). Frames kept: every frame of the WPT groups in png_wpt (reftest_counts.py reads them there), and
elsewhere only frames whose hash differs from the base build's, in png_changed. The base build (default: the
first one) must have been swept before, or every frame of the others counts as changed. Waits while the disk has under
1.5 GB free. Resumable like accuracy.py."""
import hashlib, json, os, re, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

builds = sys.argv[1].split(',')
opts = dict(a.split('=', 1) for a in sys.argv[2:])
workers = int(opts.get('workers', 6))
base = opts.get('base', builds[0])
WPT_GROUPS = {'wpt-blend-reftests-2', 'wpt-fegaussianblur-reftests', 'wpt-clip-path-reftests', 'wpt-feoffset-reftests',
              'wpt-femorphology-reftests', 'wpt-blend-reftests', 'wpt-fill-blur-reftests'}
TMP = f'{OUT}/tmp'
STATS = {
    'layers': r'layers begun: (\d+)',
    'pass_through': r'layers passed through: (\d+)',
    'skipped': r'filters skipped \(SKIP_UNSUPPORTED_FILTERS\): (\d+)',
    'invalid_dropped': r'filter attributes with invalid references dropped \(Filter Effects 5\): (\d+)',
}


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def compare(a, b):
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    dm = np.abs(a[:h, :w] - b[:h, :w]).max(axis=2)
    over20 = dm > 20
    return {'px8': round(100 * float((dm > 8).mean()), 3), 'px20': round(100 * float(over20.mean()), 3),
            'struct': round(100 * float(erode(over20).mean()), 4), 'max': int(dm.max()), 'exact': int((dm > 0).sum())}


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def wait_for_disk():
    for _ in range(45):
        if shutil.disk_usage('/').free > 1.5e9:
            return
        print('disk under 1.5 GB free, waiting', flush=True)
        time.sleep(20)


def render(f, framing, build):
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{TMP}/sweep_{os.getpid()}_{threading.get_ident()}.ppm'
    if os.path.exists(ppm):
        os.remove(ppm)
    env = {**os.environ, **fr, **SWEEP_ENV, **extra}
    row = {'key': f['key'], 'group': f['group'], 'framing': framing, 'build': build}
    for attempt in range(5):
        wait_for_disk()
        try:
            r = subprocess.run([binary, f'{z:g}', ppm, f['path']], env=env, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            row['error'] = 'timeout'
            return row, None
        if r.returncode != 0 and 'No space left' in r.stderr:
            time.sleep(60)
            continue
        break
    row['rc'] = r.returncode
    for name, pattern in STATS.items():
        m = re.search(pattern, r.stderr)
        if m:
            row[name] = int(m.group(1))
    m = re.search(r'harness cfgs: (.*)', r.stderr)
    if m:
        row['cfgs'] = m.group(1).strip()
    if r.returncode != 0 or not os.path.exists(ppm):
        row['error'] = r.stderr.strip()[-400:]
        return row, None
    row['hash'] = hashlib.sha1(open(ppm, 'rb').read()).hexdigest()
    return row, ppm


base_hash, done = {}, set()
path = f'{OUT}/accuracy.jsonl'
for line in open(path):
    try:
        r = json.loads(line)
    except Exception:
        continue
    done.add((r['key'], r['framing'], r['build']))
    if r['build'] == base:
        base_hash[(r['key'], r['framing'])] = r.get('hash')
out = open(path, 'a')
lock = threading.Lock()
counts = {b: [0, 0] for b in builds}  # frames, changed against base


def job(args):
    build, f, framing = args
    row, ppm = render(f, framing, build)
    if ppm:
        a = load(ppm)
        changed = row['hash'] != base_hash.get((f['key'], framing))
        keep = 'png_wpt' if f['group'] in WPT_GROUPS else ('png_changed' if changed else None)
        if keep:
            for attempt in range(5):
                try:
                    Image.open(ppm).save(f'{OUT}/{keep}/{build}_{f["key"]}_{framing}.png')
                    break
                except OSError:
                    time.sleep(60)
        os.remove(ppm)
        c, g = ref_png('chr', f['key'], framing), ref_png('ff', f['key'], framing)
        c = load(c) if os.path.exists(c) else None
        g = load(g) if os.path.exists(g) else None
        if c is not None:
            row['vs_chr'] = compare(a, c)
        if g is not None:
            row['vs_ff'] = compare(a, g)
        if c is not None and g is not None:
            row['chr_vs_ff'] = compare(c, g)
    else:
        changed = None
    with lock:
        out.write(json.dumps(row) + '\n')
        out.flush()
        counts[build][0] += 1
        counts[build][1] += bool(changed)
        n = sum(v[0] for v in counts.values())
        if n % 200 == 0:
            print(time.strftime('%H:%M:%S'), counts, flush=True)


jobs = [(b, f, fr) for f in files() for fr in DEFAULT_FRAMINGS for b in builds if (f['key'], fr, b) not in done]
print(f'{len(jobs)} frames to render', flush=True)
with ThreadPoolExecutor(workers) as ex:
    list(ex.map(job, jobs))
print('done', counts, flush=True)
