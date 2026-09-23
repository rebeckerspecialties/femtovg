# Ported reftests: zero-area fills (#341) and feGaussianBlur edges and kernels

Fifteen test / `-ref.svg` pairs in the style of `corpus/wpt-blend-reftests/`
(W3C `shapes-line-02-f`, SVG 2 path semantics, and the blur primitive's
edge cases), with `test-manifest.json`. `harness/reftest.py` runs them; a
pass is the renderer's test matching its own reference. Chromium 131
renders every pair alike. `blur-axis-zero-directional`'s reference uses
the same anisotropic filters as its test, so only the Chromium comparison
discriminates there.
