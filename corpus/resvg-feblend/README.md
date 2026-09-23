# resvg feBlend conformance cases

From linebender/resvg, `crates/resvg/tests/tests/filters/feBlend/*.svg`
(MIT / Apache-2.0), fetched 2026-09-23. Each blends an `feFlood` with the
source graphic: `mode=*.svg` over the whole region, `with-subregion-on-input-*`
with the flood limited to a subregion. Used as the non-BuseyBench example
for `ImageFilter::Blend` (femtovg/femtovg#355); references are Chromium 131
through `harness/make_ref.py` as for the rest of the corpus.
