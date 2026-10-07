# Flattening experiments (2026-10-07)

What finer curve flattening buys and costs, and the alternatives tried, on master cc0d841.

- `flattening-experiments-2026-10-07.patch` - on `finer-flattening-rebased` (08d020f): environment switches for one
  harness binary - `FEMTOVG_TESS_TOL` (the bisection's tolerance), `FEMTOVG_JOIN_TOL` (round joins and caps),
  `FEMTOVG_FLAT_DEV` (an n-way split to a deviation), `FEMTOVG_STRADDLE` / `FEMTOVG_STRADDLE2` (vertices moved off the
  curve by k times the mean of each chord's control distances; the second keeps one pending vertex), `FEMTOVG_COUNT`
  (points flattened, printed when the canvas drops) and `FEMTOVG_DUMP` (every cubic in device space).
- `flat_eval.py VARIANT...` - every frame with an area reference (1,170) rendered under each variant's environment,
  pixels beyond 8 and 20/255 of the reference.
- `analyze_flat.py` and `run_*.py` - offline over dumped cubics: bisection, the optimum, Levien's parabola flattening,
  straddled vertices, per-curve deviation and area.

Pixels beyond 20/255 of the area over the 1,170 frames, against master: tolerance 0.0625 (the PR) -155,334 for 1.41x
the points (tiger at 1080p +12.6 % instructions); straddled vertices at master's tolerance and points -107,042 (k=0.5)
and -111,514 (k=0.375), about +0.2 % instructions, 4,883 of its 5,468 pixels of regressions in #380's clip twins (the
outline test needs the shift as slack); an n-way split by a 0.75 max-distance bound needs more points than bisection
for the same accuracy.
