#!/usr/bin/env python3
"""Summarise a soak CSV: per pass, CPU and wall percentiles, the transient
high-water, images held at the end of the pass, RSS high-water; growth
across passes is the signal (a persistent canvas should settle after pass 0)."""
import csv, sys, statistics
def pct(xs, p):
    xs = sorted(xs); k = (len(xs) - 1) * p / 100; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)
for path in sys.argv[1:]:
    rows = list(csv.DictReader(open(path)))
    passes = sorted({int(r['pass']) for r in rows})
    print(f"== {path}: {len(rows)} frames, {len({r['file'] for r in rows})} files, zooms {sorted({r['zoom'] for r in rows})}")
    print("pass | cpu p50/p95/p99/max ms | wall p50/p95/p99/max ms | transient max MiB | images at pass end | maxrss MiB at pass end")
    for p in passes:
        rs = [r for r in rows if int(r['pass']) == p]
        cpu = [float(r['cpu_ms']) for r in rs]; wall = [float(r['wall_ms']) for r in rs]
        tr = max(int(r['transient_bytes']) for r in rs) / 2**20
        print(f"{p:4d} | {pct(cpu,50):6.1f} {pct(cpu,95):6.1f} {pct(cpu,99):6.1f} {max(cpu):6.1f} | {pct(wall,50):6.1f} {pct(wall,95):6.1f} {pct(wall,99):6.1f} {max(wall):6.1f} | {tr:7.1f} | {rs[-1]['images']:>5} | {int(rs[-1]['maxrss_bytes'])/2**20:7.1f}")
    # slowest frames of the last pass
    last = [r for r in rows if int(r['pass']) == passes[-1]]
    worst = sorted(last, key=lambda r: -float(r['cpu_ms']))[:5]
    print("slowest (last pass):", ", ".join(f"{r['file']}@{r['zoom']}x {float(r['cpu_ms']):.0f} ms" for r in worst))
