#!/usr/bin/env python3
"""What is left against Chromium on a frame, and how much of it is budget: each build at the library's budgets, with
the transient-image budget lifted, and with the filter work budget lifted too.
  budget_probe.py build[,build...] key:framing ..."""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image
from common import FRAMINGS, SWEEP_ENV, BUILDS, OUT as R
files = {f['key']: f for f in json.load(open(f'{R}/files.json'))}
def erode(m, it=2):
    for _ in range(it): m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m
CONFIGS = [('library budgets', {}), ('transient budget 16 GiB', {'TRANSIENT_BUDGET_MB': '16384'}), ('transient 16 GiB + filter work 64 Gi samples', {'TRANSIENT_BUDGET_MB': '16384', 'FILTER_WORK_GSAMPLES': '64'})]
for spec in sys.argv[2:]:
    name, framing = spec.split(':'); key = [k for k in files if k.endswith('__' + name)][0]
    fr, z = FRAMINGS[framing]; ref = np.asarray(Image.open(f'{R}/refs/chr_{key}_{framing}.png').convert('RGB'), dtype=np.int16)
    print(f'{name} {framing}')
    for build in sys.argv[1].split(','):
        binary, extra = BUILDS[build]
        for label, env in CONFIGS:
            os.makedirs(f'{R}/tmp', exist_ok=True)
            ppm = f'{R}/tmp/probe.ppm'
            r = subprocess.run([binary, f'{z:g}', ppm, files[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra, **env}, capture_output=True, text=True, timeout=900)
            a = np.asarray(Image.open(ppm).convert('RGB'), dtype=np.int16); os.remove(ppm)
            d = np.abs(a - ref).max(axis=2); o = d > 20
            st = {k: int(v) for k, v in re.findall(r'(layers begun|layers passed through|filters skipped \(SKIP_UNSUPPORTED_FILTERS\)|transient bytes held at flush): (\d+)', r.stderr)}
            print(f"   {build:7s} {label:46s} px>8 {100*(d>8).mean():5.2f} %  px>20 {100*o.mean():5.2f} %  structural {100*erode(o).mean():6.3f} %  max {d.max():3d} | layers {st.get('layers begun')} passed through {st.get('layers passed through')} filters skipped {st.get('filters skipped (SKIP_UNSUPPORTED_FILTERS)')} transient {st.get('transient bytes held at flush', 0)/2**20:.0f} MiB")
