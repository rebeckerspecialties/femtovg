#!/usr/bin/env python3
"""Evidence figure for #368: peak footprint of one frame for the 27 BuseyBench portraits under master,
this PR, and this PR with slicing on (a dot per build on one row per portrait), over stat tiles for the
whole-corpus soak. Writes chart.html; Chromium renders it to PNG."""
import collections, json, html
from common import *

MiB = 1048576.0
rows = [json.loads(l) for l in open(f'{OUT}/memory.jsonl')]
by = collections.defaultdict(dict)
for r in rows:
    by[(r['key'], r['framing'])][r['build']] = r
fp = lambda r: r['mem']['peak_footprint'] / MiB / 1024  # GiB
SERIES = [('base', 'master', '#2a78d6'), ('final_noslices', 'this PR', '#eb6834'), ('final', 'this PR, slicing on', '#1baf7a')]
data = []
for (k, f), v in by.items():
    if f == 'z1' and 'buseybench' in k:
        data.append((k.split('__')[-1], [fp(v[b]) for b, _, _ in SERIES], v['slices']['mem']['passes'], v['final']['mem']['passes']))
data.sort(key=lambda d: -d[1][0])

SURFACE, INK, SECOND, MUTED, GRID, RULE = '#fcfcfb', '#0b0b0b', '#52514e', '#8a8982', '#e9e8e3', '#b9b8b1'
W, LEFT, RIGHT, TOP, ROW = 1160, 330, 70, 150, 20
PLOT_W = W - LEFT - RIGHT
XMAX = 4.25
x = lambda gib: LEFT + PLOT_W * gib / XMAX
plot_h = ROW * len(data)
tiles_y = TOP + plot_h + 62
H = tiles_y + 118
POOL = 445 / 1024

s = []
a = s.append
a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="-apple-system, Helvetica Neue, Arial, sans-serif">')
a(f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>')
a(f'<text x="24" y="34" font-size="17" font-weight="600" fill="{INK}">Peak memory of one frame: the 27 BuseyBench portraits at 460x260</text>')
a(f'<text x="24" y="55" font-size="12.5" fill="{SECOND}">Process footprint, CPU and GPU together, of a single cold frame on an M4 Max; one process per frame. Every build draws the same pixels.</text>')
# legend
lx = 24
for (_, label, color), detail in zip(SERIES, ('one command buffer per frame, a pass at every target switch', 'a pass begins with its first draw', '64 passes per submission')):
    a(f'<circle cx="{lx + 6}" cy="82" r="5.5" fill="{color}"/>')
    a(f'<text x="{lx + 18}" y="86.5" font-size="12.5" fill="{INK}"><tspan font-weight="600">{label}</tspan><tspan fill="{SECOND}">: {detail}</tspan></text>')
    lx += 18 + 6.15 * (len(label) + len(detail) + 2) + 34
# column heads
a(f'<text x="24" y="{TOP - 12}" font-size="11" fill="{MUTED}">portrait</text>')
a(f'<text x="{LEFT - 22}" y="{TOP - 12}" font-size="11" fill="{MUTED}" text-anchor="end">render passes, before and after</text>')
# grid
for g in range(0, 5):
    a(f'<line x1="{x(g):.1f}" y1="{TOP}" x2="{x(g):.1f}" y2="{TOP + plot_h}" stroke="{GRID}" stroke-width="1"/>')
    a(f'<text x="{x(g):.1f}" y="{TOP + plot_h + 18}" font-size="11" fill="{MUTED}" text-anchor="middle">{g} GiB</text>' if g else f'<text x="{x(g):.1f}" y="{TOP + plot_h + 18}" font-size="11" fill="{MUTED}" text-anchor="middle">0</text>')
# the fixed pool
a(f'<line x1="{x(POOL):.1f}" y1="{TOP - 4}" x2="{x(POOL):.1f}" y2="{TOP + plot_h}" stroke="{RULE}" stroke-width="1"/>')
a(f'<text x="{x(POOL) + 6:.1f}" y="{TOP + plot_h + 36}" font-size="11" fill="{SECOND}">0.43 GiB: the pool the driver grows for any first frame, a single rectangle included</text>')
for i, (name, vals, eager, lazy) in enumerate(data):
    cy = TOP + ROW * i + ROW / 2
    a(f'<text x="24" y="{cy + 4:.1f}" font-size="11.5" fill="{SECOND}">{html.escape(name)}</text>')
    a(f'<text x="{LEFT - 22}" y="{cy + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end" style="font-variant-numeric: tabular-nums">{eager:,} &#8594; {lazy:,}</text>')
    a(f'<line x1="{x(min(vals)):.1f}" y1="{cy:.1f}" x2="{x(max(vals)):.1f}" y2="{cy:.1f}" stroke="#d9d8d2" stroke-width="2"/>')
    for (b, _, color), v in zip(SERIES, vals):
        a(f'<circle cx="{x(v):.1f}" cy="{cy:.1f}" r="5.5" fill="{color}" stroke="{SURFACE}" stroke-width="2"/>')
    if i == 0:
        for v, anchor, dx in zip(vals, ('start', 'start', 'end'), (10, 10, -10)):
            a(f'<text x="{x(v) + dx:.1f}" y="{cy - 9:.1f}" font-size="11.5" font-weight="600" fill="{INK}" text-anchor="{anchor}">{v:.2f} GiB</text>')
# tiles
soak = {}
for b in ('base', 'final_noslices', 'final'):
    lines = open(f'{OUT}/soak_{b}_zooms.csv').read().splitlines()
    soak[b] = max(float(l.split(',')[-7]) for l in lines[1:]) / MiB / 1024
tiles = [
    ('Pixels, 2,844 frames', 'identical', '711 files at four framings, against master before #369'),
    ('The other 684 files', '0.45 GiB', 'median in every build; one render pass at the median'),
    ('Corpus soak, master', f'{soak["base"]:.2f} GiB', 'peak over 6,399 frames on one canvas'),
    ('Corpus soak, this PR', f'{soak["final_noslices"]:.2f} GiB', 'the same soak, slicing off'),
    ('Corpus soak, slicing on', f'{soak["final"]:.2f} GiB', 'the same soak, 64 passes per submission'),
]
tw = (W - 48 - 16 * (len(tiles) - 1)) / len(tiles)
for i, (label, value, note) in enumerate(tiles):
    tx = 24 + i * (tw + 16)
    a(f'<rect x="{tx:.1f}" y="{tiles_y}" width="{tw:.1f}" height="96" rx="8" fill="#f4f3ef"/>')
    a(f'<text x="{tx + 14:.1f}" y="{tiles_y + 24}" font-size="12" fill="{SECOND}">{label}</text>')
    a(f'<text x="{tx + 14:.1f}" y="{tiles_y + 54}" font-size="23" font-weight="600" fill="{INK}">{value}</text>')
    words, line, lines_out = note.split(), '', []
    for w in words:
        if len(line) + len(w) + 1 > 34:
            lines_out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    lines_out.append(line)
    for j, l in enumerate(lines_out[:2]):
        a(f'<text x="{tx + 14:.1f}" y="{tiles_y + 73 + 13 * j}" font-size="10.5" fill="{MUTED}">{html.escape(l)}</text>')
a('</svg>')
open(f'{OUT}/chart.html', 'w').write(f'<!doctype html><html><body style="margin:0;background:{SURFACE}">' + '\n'.join(s) + '</body></html>')
print(W, H)
for name, vals, eager, lazy in data[:5]:
    print(f'{name:30s}', ' '.join(f'{v:.2f}' for v in vals), eager, lazy)
print({k: round(v, 2) for k, v in soak.items()})
