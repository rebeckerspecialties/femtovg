#!/usr/bin/env python3
"""Full-corpus run over files.json x four framings.

  run.py pixels            parallel: builds pre369 and noslices, frame hash only  -> pixels.jsonl
  run.py memory [filter]   sequential: builds base and slices with MEM_PEAKS: hash, layer stats,
                           peak memory, and the slices frame against Chromium (and Firefox at z1)
                           -> memory.jsonl
Both append and resume: a (key, framing, build) already in the output is skipped."""
import hashlib, json, os, re, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from common import *

TMP = f'{OUT}/tmp'
os.makedirs(TMP, exist_ok=True)
STATS = {
    'layers': r'layers begun: (\d+)',
    'transient': r'transient bytes held at flush: (\d+)',
    'pass_through': r'layers passed through: (\d+)',
    'skipped': r'filters skipped \(SKIP_UNSUPPORTED_FILTERS\): (\d+)',
    'turb_not_run': r'feTurbulence chains not run \(no harness_turbulence\): (\d+)',
    'unclipped': r'clip paths drawn unclipped \(no harness_clip\): (\d+)',
    'invalid_dropped': r'filter attributes with invalid references dropped \(Filter Effects 5\): (\d+)',
}


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def cmp(a, c, thr=20):
    h, w = min(a.shape[0], c.shape[0]), min(a.shape[1], c.shape[1])
    dm = np.abs(a[:h, :w] - c[:h, :w]).max(axis=2)
    over = dm > thr
    return {'px': round(100 * float(over.mean()), 3), 'struct': round(100 * float(erode(over).mean()), 4),
            'max': int(dm.max()), 'exact': int((dm > 0).sum())}


def load(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def render(f, framing, build, memory):
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{TMP}/{threading.get_ident()}_{build}.ppm'
    if os.path.exists(ppm):
        os.remove(ppm)
    env = {**os.environ, **fr, **SWEEP_ENV, **extra}
    if memory:
        env['MEM_PEAKS'] = '1'
    row = {'key': f['key'], 'group': f['group'], 'framing': framing, 'build': build}
    try:
        r = subprocess.run([binary, f'{z:g}', ppm, f['path']], env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        row['error'] = 'timeout'
        return row, None
    err = r.stderr
    row['rc'] = r.returncode
    for name, pattern in STATS.items():
        m = re.search(pattern, err)
        if m:
            row[name] = int(m.group(1))
    m = re.search(r'harness cfgs: (.*)', err)
    if m:
        row['cfgs'] = m.group(1).strip()
    m = re.search(r'^PASSREPORT (.*)$', err, re.M)
    if m:
        row['passes'] = {k: int(v) for k, v in re.findall(r'([\w>]+)=(\d+)', m.group(1))}
    m = re.search(r'^MEM (.*)$', err, re.M)
    if m:
        row['mem'] = {k: (float(v) if '.' in v else int(v)) for k, v in re.findall(r'(\w+)=([\d.]+)', m.group(1))}
    if r.returncode != 0 or not os.path.exists(ppm):
        row['error'] = err.strip()[-400:]
        return row, None
    data = open(ppm, 'rb').read()
    row['hash'] = hashlib.sha1(data).hexdigest()
    return row, ppm


def done_set(path):
    done = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                r = json.loads(line)
                done.add((r['key'], r['framing'], r['build']))
            except Exception:
                pass
    return done


def pixels(builds):
    path = f'{OUT}/pixels.jsonl'
    done = done_set(path)
    jobs = [(f, fr, b) for f in files() for fr in DEFAULT_FRAMINGS for b in builds if (f['key'], fr, b) not in done]
    lock = threading.Lock()
    out = open(path, 'a')

    def one(job):
        # MEM_PEAKS for the pass counts; the memory figures of a parallel run are not used.
        row, ppm = render(*job, memory=True)
        if ppm:
            os.remove(ppm)
        with lock:
            out.write(json.dumps(row) + '\n')
            out.flush()
        return row.get('error')

    errors = 0
    with ThreadPoolExecutor(6) as ex:
        for i, e in enumerate(ex.map(one, jobs)):
            errors += bool(e)
            if (i + 1) % 500 == 0:
                print(f'pixels: {i + 1}/{len(jobs)} errors {errors}', flush=True)
    print(f'pixels done: {len(jobs)} runs, {errors} errors', flush=True)


def memory(builds, frames=None):
    """frames: optional set of (key, framing) to restrict the run to."""
    path = f'{OUT}/memory.jsonl'
    done = done_set(path)
    out = open(path, 'a')
    fs = files()
    n = 0
    for i, f in enumerate(fs):
        for framing in DEFAULT_FRAMINGS:
            if frames is not None and (f['key'], framing) not in frames:
                continue
            for build in builds:
                if (f['key'], framing, build) in done:
                    continue
                row, ppm = render(f, framing, build, memory=True)
                if ppm and build == 'slices':
                    a = load(ppm)
                    chr_png = ref_png('chr', f['key'], framing)
                    if os.path.exists(chr_png):
                        c = load(chr_png)
                        row['vs_chr'] = cmp(a, c)
                        ff_png = ref_png('ff', f['key'], framing)
                        if os.path.exists(ff_png):
                            g = load(ff_png)
                            row['vs_ff'] = cmp(a, g)
                            row['chr_vs_ff'] = cmp(c, g)
                if ppm:
                    os.remove(ppm)
                out.write(json.dumps(row) + '\n')
                out.flush()
                n += 1
        if (i + 1) % 50 == 0:
            print(f'memory: {i + 1}/{len(fs)} files, {n} runs', flush=True)
    print(f'memory done: {n} runs', flush=True)


if sys.argv[1] == 'pixels':
    pixels(sys.argv[2].split(','))
else:
    frames = None
    if len(sys.argv) > 3:  # a file of "key framing" lines
        frames = {tuple(line.split()) for line in open(sys.argv[3]) if line.strip()}
    memory(sys.argv[2].split(','), frames)
