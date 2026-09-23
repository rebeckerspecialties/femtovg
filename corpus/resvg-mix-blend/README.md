# resvg mix-blend-mode, isolation and feBlend-chain conformance cases

From linebender/resvg (MIT / Apache-2.0), fetched 2026-09-23:
`crates/resvg/tests/tests/painting/mix-blend-mode/*.svg` (the sixteen modes,
`as-property`, `opacity-on-element`, `opacity-on-group`, `xor`),
`painting/isolation/*.svg` (prefixed `isolation-`) and
`filters/filter/multiple-primitives-4.svg` (a blur then `feBlend` against
`SourceAlpha`, prefixed `filter-`). Evidence for `LayerEffects::with_blend`
(femtovg/femtovg#356) and the `feBlend` chain mapping of #355; references are
Chromium 131 through `harness/make_ref.py`.
