import sys
sys.path.insert(0, '/Users/matt/src/femtovg-wt/runs/pr/tmp/flat')
from analyze_flat import *
cs = load(sys.argv[1:])
ch = chains(cs)
print(len(cs), 'cubics in', len(ch), 'smooth chains')
def rep(name, polys):
    segs = sum(len(p) - 1 for p in polys)
    r = np.array([polyline_dev(c, p) for c, p in zip(cs, polys)])
    sa = np.array([signed_area(c, p) for c, p in zip(cs, polys)])
    print(f"{name:30s} segs {segs:6d}  per-curve max dev: mean {r[:, 0].mean():.4f} p90 {np.percentile(r[:, 0], 90):.4f} p99 {np.percentile(r[:, 0], 99):.4f}  |area| {r[:, 1].sum():8.1f}  |net| {np.abs(sa).sum():8.1f}")
rep('bisection 0.25', [bisect_poly(c, 0.25) for c in cs])
rep('bisection 0.0625', [bisect_poly(c, 0.0625) for c in cs])
for tol in (0.25, 0.125):
    for k in (0.5,):
        rep(f'straddle {tol} k={k}', [bisect_straddle(c, tol, k) for c in cs])
        polys = {}
        for chain in ch:
            polys.update(chain_straddle(cs, chain, tol, k))
        rep(f'chain straddle {tol} k={k}', [polys[i] for i in range(len(cs))])
