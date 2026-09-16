#!/bin/zsh
# Multi-frame stencil artifact probe (harness/pz/patch_equivalence.md: Ghostscript_Tiger at 640x480,
# FRAMES>=2 vs 1 differs at (200,145) when clear_rect does not clear the winding bits).
S=/private/tmp/claude-501/-Users-matt-src-femtovg/e8e3f9a7-e26b-426f-ad20-5815dcc2470f/scratchpad
export FRAME_W=640 FRAME_H=480 BOX=480 BOX_X=80 BOX_Y=0 SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1
T=/private/tmp/wt-all3/examples/assets/Ghostscript_Tiger.svg
mkdir -p $S/cost/out/tiger
for pair in fixed=/private/tmp/wt-all3/target/debug/examples/_logos_full orig=$S/wpt-masks/bin/_logos_full.orig master=$S/w336/bin/_logos_full_master; do
  tag=${pair%%=*}; bin=${pair#*=}
  FRAMES=1 $bin 1.0 $S/cost/out/tiger/${tag}_f1.ppm $T 2>/dev/null
  FRAMES=2 $bin 1.0 $S/cost/out/tiger/${tag}_f2.ppm $T 2>/dev/null
  python3 - $tag $S/cost/out/tiger/${tag}_f1.ppm $S/cost/out/tiger/${tag}_f2.ppm <<'PY'
import sys, numpy as np
from PIL import Image
tag, a, b = sys.argv[1:4]
A = np.asarray(Image.open(a).convert("RGB"), dtype=int); B = np.asarray(Image.open(b).convert("RGB"), dtype=int)
d = np.abs(A - B).max(axis=2); ys, xs = np.nonzero(d)
print(f"{tag}: FRAMES=1 vs FRAMES=2 differing px {int((d>0).sum())}" + (f" at {list(zip(xs.tolist(), ys.tolist()))[:5]} f1={A[ys[0],xs[0]].tolist()} f2={B[ys[0],xs[0]].tolist()}" if len(xs) else ""))
PY
done
