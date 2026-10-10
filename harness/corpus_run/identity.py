#!/usr/bin/env python3
"""identity.py A B [workers=3] : render every corpus frame (all files, every framing) with builds A and B, as
sweep.py renders them, and compare the two frames' hashes. Keeps no frames. Prints the counts and every frame that
differs or fails; writes tmp/identity_A_B.jsonl (key, framing, same, error)."""
import hashlib, json, os, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

a, b = sys.argv[1], sys.argv[2]
opts = dict(x.split('=', 1) for x in sys.argv[3:])
workers = int(opts.get('workers', 3))
TMP = f'{OUT}/tmp'


def render(f, framing, build):
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    ppm = f'{TMP}/identity_{build}_{os.getpid()}_{threading.get_ident()}.ppm'
    env = {**os.environ, **fr, **SWEEP_ENV, **extra}
    for _ in range(30):
        if shutil.disk_usage('/').free > 0.4e9:
            break
        time.sleep(20)
    r = subprocess.run([binary, f'{z:g}', ppm, f['path']], env=env, capture_output=True, timeout=300)
    if r.returncode != 0 or not os.path.exists(ppm):
        return None, r.stderr.decode(errors='replace')[-300:]
    digest = hashlib.sha1(open(ppm, 'rb').read()).hexdigest()
    os.remove(ppm)
    return digest, None


def job(args):
    f, framing = args
    ha, ea = render(f, framing, a)
    hb, eb = render(f, framing, b)
    return {'key': f['key'], 'framing': framing, 'same': ha is not None and ha == hb, 'error': ea or eb}


jobs = [(f, framing) for f in files() for framing in FRAMINGS]
print(len(jobs), 'frames', flush=True)
out = open(f'{TMP}/identity_{a}_{b}.jsonl', 'w')
same = differ = failed = 0
with ThreadPoolExecutor(workers) as ex:
    for i, row in enumerate(ex.map(job, jobs)):
        out.write(json.dumps(row) + '\n')
        if row['error']:
            failed += 1
            print('FAILED', row['key'], row['framing'], row['error'][-120:], flush=True)
        elif row['same']:
            same += 1
        else:
            differ += 1
            print('DIFFERS', row['key'], row['framing'], flush=True)
        if (i + 1) % 500 == 0:
            print(time.strftime('%H:%M:%S'), i + 1, 'done:', same, 'same', differ, 'differ', failed, 'failed', flush=True)
print('done:', same, 'same', differ, 'differ', failed, 'failed', flush=True)
