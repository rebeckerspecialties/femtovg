#!/usr/bin/env python3
"""Writes files.json, the run's file list: every SVG of the demo-assets corpus and top level, plus any
extra directories given as GROUP=DIR arguments (searched recursively) or GROUP=FILE.

  files.py svgenius=~/src/SVGenius tiger=~/Ghostscript_Tiger.svg
"""
import glob, json, os, sys
from common import *


def group(rel):
    parts = rel.split('/')
    if parts[0] == 'corpus' and len(parts) > 2:
        return parts[1]
    return 'reductions' if parts[0] == 'corpus' else 'logos'


out = []
for p in sorted(glob.glob(f'{DA}/corpus/**/*.svg', recursive=True)) + sorted(glob.glob(f'{DA}/*.svg')):
    rel = os.path.relpath(p, DA)
    out.append({'path': p, 'key': rel[:-4].replace('/', '__'), 'group': group(rel)})
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1)
    path = os.path.expanduser(path)
    found = [path] if os.path.isfile(path) else sorted(glob.glob(f'{path}/**/*.svg', recursive=True))
    for p in found:
        out.append({'path': p, 'key': f'{name}__{os.path.basename(p)[:-4]}', 'group': name})
keys = [f['key'] for f in out]
assert len(keys) == len(set(keys)), 'two files map to one key'
os.makedirs(OUT, exist_ok=True)
json.dump(out, open(f'{OUT}/files.json', 'w'), indent=0, ensure_ascii=False)
print(len(out), 'files')
