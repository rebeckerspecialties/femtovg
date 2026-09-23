# WPT mix-blend-mode / compositing reftests, as standalone SVG

Twenty-three test / `-ref.svg` pairs extracted from Web Platform Tests
(`css/compositing/mix-blend-mode`, `css/compositing/svg`,
`css/filter-effects`; WPT is 3-Clause BSD) into self-contained SVG, with
`test-manifest.json` naming each source test, spec link and bug tracker.
A reftest passes when the test renders like its reference in the same
renderer; `harness/reftest.py` runs a binary over the suite and also
checks each pair in Chromium 131, which validates the extraction.

Chromium renders 22 pairs alike. `blend-svg-root-isolation` needs its
WPT `<img>` embedding (an SVG image is an isolated group; inline, the root
blends with the page), so Chromium fails the standalone version and it is
not counted. `blend-plus-lighter-isolated` uses `mix-blend-mode:
plus-lighter`, which usvg 0.48 does not parse, so the harness cannot map
it; femtovg's `CompositeOperation::Lighter` is the equivalent.
