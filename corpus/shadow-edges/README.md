# Shadow casters at the canvas edges (#342)

A 60x88 rect with `feDropShadow` (stdDeviation 5) placed entirely above,
left of, beyond the right or bottom edge of, or crossing the top of a
200x200 canvas, with the offset pointing back into view. Chromium draws
the shadow that lands inside; a layer whose capture stopped at the
scissor lost it (femtovg/femtovg#361 fixes the capture). References are
Chromium 131 through `harness/make_ref.py`.
