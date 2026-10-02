#!/usr/bin/env python3
"""Summaries of the full-corpus run: pixel identity between builds, peak memory per build, pass counts,
budget pass-throughs and accuracy against the browsers. Reads pixels.jsonl and memory.jsonl."""
import collections, json, os, statistics, sys
from common import *

MiB = 1048576.0


def rows(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


pix = rows(f'{OUT}/pixels.jsonl')
mem = rows(f'{OUT}/memory.jsonl')
frames = collections.defaultdict(dict)  # (key, framing) -> build -> row; memory rows win over pixel rows
for r in pix:
    frames[(r['key'], r['framing'])][r['build']] = r
for r in mem:
    frames[(r['key'], r['framing'])][r['build']] = r
group = {}
for (k, _), v in frames.items():
    for r in v.values():
        group[k] = r['group']
PATHOLOGICAL = ('buseybench', 'pressure')
kind = lambda k: 'BuseyBench + pressure' if group[k] in PATHOLOGICAL else 'everything else'


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else float('nan')


def identity(a, b):
    same = diff = missing = 0
    bad = []
    for k, v in frames.items():
        if a in v and b in v and 'hash' in v[a] and 'hash' in v[b]:
            if v[a]['hash'] == v[b]['hash']:
                same += 1
            else:
                diff += 1
                bad.append(k)
        elif a in v or b in v:
            missing += 1
    return same, diff, missing, bad


print('## Pixel identity (frame hashes)')
builds = sorted({b for v in frames.values() for b in v})
print('builds present:', builds, '| frames:', len(frames))
for a, b in (('pre369', 'base'), ('pre369', 'noslices'), ('base', 'slices'), ('base', 'lazy'), ('base', 'final'), ('base', 'final_noslices'), ('base', 'lazy_slices'), ('base', 'wait2')):
    if a in builds and b in builds:
        s, d, m, bad = identity(a, b)
        print(f'  {a:8s} vs {b:12s}: {s} identical, {d} differ, {m} not paired', bad[:5] if bad else '')
errors = [(k, b, r.get('error', '')[-120:]) for k, v in frames.items() for b, r in v.items() if 'error' in r]
print('render errors:', len(errors))
for e in errors[:10]:
    print('  ', e)

if not mem:
    sys.exit()


def m(r, field):
    return r['mem'][field] / MiB


print('\n## Render passes per frame (eager = master; lazy = a pass begun only when drawn into)')
for fr in FRAMINGS:
    for label in ('everything else', 'BuseyBench + pressure'):
        eager = [v['slices']['mem']['passes'] for (k, f), v in frames.items() if f == fr and kind(k) == label and 'slices' in v and 'mem' in v['slices']]
        lazy = [v['lazy']['mem']['passes'] for (k, f), v in frames.items() if f == fr and kind(k) == label and 'lazy' in v and 'mem' in v['lazy']]
        if eager:
            line = f'  {fr} {label:22s} n={len(eager):4d} eager median {statistics.median(eager):5.0f} p90 {pct(eager, .9):5.0f} max {max(eager):5d}  frames over 64 passes: {sum(p > 64 for p in eager)}'
            if lazy:
                line += f' | lazy median {statistics.median(lazy):5.0f} p90 {pct(lazy, .9):5.0f} max {max(lazy):5d}  over 64: {sum(p > 64 for p in lazy)}'
            print(line)

print('\n## Peak memory per frame, MiB (one process per frame; footprint = CPU + GPU, graphics = GPU part, cpu = the rest)')
mem_builds = [b for b in ('base', 'final_noslices', 'final', 'slices', 'wait2') if any(b in v and 'mem' in v[b] for v in frames.values())]
floor = {}
for fr in FRAMINGS:
    for b in mem_builds:
        g = [m(v[b], 'peak_graphics') for (k, f), v in frames.items() if f == fr and b in v and 'mem' in v[b]]
        if g:
            floor[(fr, b)] = min(g)
print('  fixed driver pool (smallest graphics peak of any frame):', {f'{fr}/{b}': round(x) for (fr, b), x in floor.items() if b == 'base'})
for fr in FRAMINGS:
    for label in ('everything else', 'BuseyBench + pressure'):
        for b in mem_builds:
            sel = [v[b] for (k, f), v in frames.items() if f == fr and kind(k) == label and b in v and 'mem' in v[b]]
            if not sel:
                continue
            fp = [m(r, 'peak_footprint') for r in sel]
            g = [m(r, 'peak_graphics') for r in sel]
            c = [m(r, 'peak_cpu') for r in sel]
            print(f'  {fr} {label:22s} {b:11s} n={len(sel):4d}  footprint median {statistics.median(fp):6.0f} p90 {pct(fp, .9):6.0f} max {max(fp):6.0f} | graphics median {statistics.median(g):6.0f} max {max(g):6.0f} | cpu median {statistics.median(c):5.0f} max {max(c):5.0f}')

print('\n## Heaviest frames by master graphics peak (MiB): passes, then each build')
heavy = sorted(((m(v['base'], 'peak_graphics'), k, f) for (k, f), v in frames.items() if 'base' in v and 'mem' in v['base']), reverse=True)[:25]
for g, k, f in heavy:
    v = frames[(k, f)]
    cells = ' '.join(f"{b}={m(v[b], 'peak_graphics'):5.0f}" for b in mem_builds if b in v and 'mem' in v[b])
    passes = v.get('slices', {}).get('mem', {}).get('passes', '?')
    lazy_passes = v.get('lazy', v.get('lazy_slices', {})).get('mem', {}).get('passes', '?')
    print(f'  {k.split("__")[-1][:34]:34s} {f} passes {passes:>5}/{lazy_passes:>5}  {cells}  pass-through {v["base"].get("pass_through", 0)} of {v["base"].get("layers", 0)} layers')

print('\n## Layers passed through under the transient budget (quality given up for memory)')
for b in ('base', 'slices'):
    pt = [(k, f, v[b]['pass_through'], v[b].get('layers', 0)) for (k, f), v in frames.items() if b in v and v[b].get('pass_through', 0) > 0]
    by = collections.Counter((group[k], f) for k, f, _, _ in pt)
    print(f'  {b}: {len(pt)} frames:', dict(by))

print('\n## Accuracy of the slices build against Chromium 131 (px beyond 20/255, structural after 2 px erosion), by group')
acc = collections.defaultdict(list)
for (k, f), v in frames.items():
    r = v.get('slices')
    if r and 'vs_chr' in r:
        acc[(kind(k), f)].append(r)
for (label, f), rs in sorted(acc.items()):
    px = [r['vs_chr']['px'] for r in rs]
    st = [r['vs_chr']['struct'] for r in rs]
    line = f'  {label:22s} {f}: n={len(rs):4d} px>20 median {statistics.median(px):5.2f}% p90 {pct(px, .9):5.2f}%  structural median {statistics.median(st):6.3f}% p90 {pct(st, .9):6.3f}%  frames over 1% structural: {sum(s > 1 for s in st)}'
    ff = [r for r in rs if 'vs_ff' in r]
    if ff:
        line += f' | vs Firefox px median {statistics.median([r["vs_ff"]["px"] for r in ff]):5.2f}%, Chromium vs Firefox {statistics.median([r["chr_vs_ff"]["px"] for r in ff]):5.2f}%'
    print(line)

print('\n## Frame time of the single cold frame, ms (record + flush + GPU wait)')
for label in ('everything else', 'BuseyBench + pressure'):
    for b in mem_builds:
        t = [v[b]['mem']['frame_ms'] for (k, f), v in frames.items() if kind(k) == label and b in v and 'mem' in v[b]]
        if t:
            print(f'  {label:22s} {b:11s} median {statistics.median(t):7.1f} p90 {pct(t, .9):7.1f} max {max(t):8.1f} sum {sum(t) / 1000:7.1f} s')
