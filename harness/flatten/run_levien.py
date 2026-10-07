import sys
sys.path.insert(0, '/Users/matt/src/femtovg-wt/runs/pr/tmp/flat')
from analyze_flat import *
cs = load(sys.argv[1:])
print(len(cs), 'cubics')
for tol in (0.25, 0.0625):
    report_poly(f'bisection {tol}', [bisect_poly(c, tol) for c in cs], cs)
for tol in (0.15, 0.12, 0.1, 0.08, 0.06):
    report_poly(f'levien {tol} (quads {tol*0.1:.3f})', [levien(c, tol, tol * 0.1) for c in cs], cs)
