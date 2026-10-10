#!/usr/bin/env python3
"""Writes files.json, the run's file list: every SVG of the demo-assets corpus and top level, plus any
extra directories given as GROUP=DIR arguments (searched recursively) or GROUP=FILE.

  files.py [GROUP=DIR|GROUP=FILE ...]

The SVGenius icons and the Ghostscript tiger live in corpus/svgenius and corpus/tiger; they keep the keys they
had when they were read from outside (GROUP__name), so earlier runs' references and results still match.
"""
import glob, json, os, sys
from common import *

# Imported sets keyed by file name, as GROUP=DIR arguments are.
NAME_KEYED = {'svgenius', 'tiger'}


def group(rel):
    parts = rel.split('/')
    if parts[0] == 'corpus' and len(parts) > 2:
        return parts[1]
    return 'reductions' if parts[0] == 'corpus' else 'logos'


out = []
for p in sorted(glob.glob(f'{DA}/corpus/**/*.svg', recursive=True)) + sorted(glob.glob(f'{DA}/*.svg')):
    rel = os.path.relpath(p, DA)
    g = group(rel)
    key = f'{g}__{os.path.basename(p)[:-4]}' if g in NAME_KEYED else rel[:-4].replace('/', '__')
    out.append({'path': p, 'key': key, 'group': g})
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
