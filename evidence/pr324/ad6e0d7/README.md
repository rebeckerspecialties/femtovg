# PR #324 visual comparison, 2026-09-22

These panels were regenerated for femtovg `ad6e0d7` against its current
`master` base `9fb5dba`. They supersede the root-level `clip_static.png`,
`clip_zoom.gif`, and `busey-stack-parity.png`, which were made on September 16
from earlier builds. The old Reddit SVG is not tracked with the harness, so the
second scene here is the tracked `gpt-6-astra.svg` Busey corpus fixture; it
contains clip paths, filters, and a mask.

The static image shows femtovg on master, femtovg on the PR, Chromium, and
Firefox. Red pixels in the second row differ from the named browser by more
than 20/255 in an RGB channel. The 11-frame GIF repeats the clip scene from
0.5x through 2.5x. `provenance.json` records exact source and input hashes,
browser and toolchain versions, framing, per-frame raw and structural metrics,
and output hashes. The structural metric erodes the difference mask by two
pixels to discount edge antialiasing.

At 1.5x, clipdemo differs from Chromium by 24.675% raw / 21.671% structural
on master and 0.769% raw / 0% structural on the PR. At 1x, the Busey fixture
goes from 0.728% raw / 0.050% structural to 0.149% raw / 0% structural. Every
PR clipdemo frame in the zoom ladder has 0% structural difference.

To reproduce, use separate source and target directories for master and the
PR. The harness source is `harness/_logos_full.rs` at demo-assets commit
`5bd6adc`; the script is `harness/pr324_visuals.py` in this asset revision.
Place or symlink `_logos_full.rs` into each checkout's `examples/` directory,
then build with:

```sh
# From master 9fb5dba
CARGO_TARGET_DIR="$WORK/target-base" cargo rustc --example _logos_full --features wgpu -- --cfg harness_turbulence

# From PR ad6e0d7
CARGO_TARGET_DIR="$WORK/target-pr" cargo rustc --example _logos_full --features wgpu -- --cfg harness_clip --cfg harness_turbulence
```

Run the script with `--base-src`, `--pr-src`, both resulting `--base-bin` and
`--pr-bin`, `--chromium`, `--firefox`, `--work`, and `--output`. It renders the
femtovg frames through WGPU/Metal, uses Chromium's headless software path for
the browser reference, and captures Firefox headlessly. It sets
`SKIP_UNSUPPORTED_FILTERS=1` and `VIEWPORT_CLIP=1` for both femtovg builds.
