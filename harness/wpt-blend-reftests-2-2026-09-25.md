# Second blend reftest batch (52 pairs) against PRs #355 and #356

`corpus/wpt-blend-reftests-2/`, rendered at 1024x1024 and 256x256 with one
harness for master (`_logos_full_master_h14`), #355 (`_logos_full_feblend17`)
and #356 (`_logos_full_mixblend12`); Chromium 131 references at the same
framings. Columns in `wpt-blend-reftests-2-{1024,256}.txt`: Chromium's own
test-vs-reference, then per binary test-vs-reference / test-vs-Chromium,
pixels beyond 8/255.

## Result on the stack head (#356)

Exact against Chromium (0.00-0.01 % at both framings): all sixteen `feBlend`
modes with a flood in either input order, both `feBlend` subregion cases,
`color-interpolation-filters` sRGB and linearRGB multiply and screen, the
linearRGB-to-sRGB transition chain, a filtered child inside a blending
group, blends under a radial gradient, an alpha gradient, group opacity and
a rectangular clip, and all sixteen `mix-blend-mode` pairs. Master fails the
`feBlend` pairs at 64 % (it has no blend) and the `mix-blend-mode` pairs at
36 %.

Not exact:

| pair | vs Chromium 1024 / 256 | cause |
|---|---|---|
| blend-clip-path-gradient-difference, -nested-overlay | 0.25 / 0.99, 0.16 / 0.65 | a one-pixel band along the clip edge (vanishes under a 1 px erosion): the stencil clip has no antialiasing, #346 |
| filter-chain-blur-feblend-sourcealpha, -colormatrix-feblend-screen, -offset-blur-feblend, filter-subregion-chain-feblend | 64 % | harness: a chain on the source side of the blend, or two floods with subregions, is not mapped; the group is skipped |
| gradient-colorspace-linearrgb-blend | 63.7 / 64.1 | Chromium honours `color-interpolation="linearRGB"` on the gradient (midpoint 187,187,0); usvg does not expose it and femtovg interpolates gradients in sRGB. A gradient-space feature (#359), not a blend |

The hand-made references differ from Chromium themselves at the filter
region's edge pixels (0.31 % at 1024, 1.25 % at 256 on every `feBlend`
pair; 0.12 / 0.47 % on `mix-blend-mode`): Blink fills the region's
enclosing pixel rect, the references are anti-aliased rects. femtovg
matches Chromium there, not the references, so the suite's own pass mark
(0.5 %) under-counts at 256.

## Harness changes for this batch

- The filter region and subregion scissors snap outward to whole device
  pixels, as Blink sizes a filter's raster. Before the snap every `feBlend`
  pair carried the same 0.31 / 1.25 % edge band against Chromium.
- A flood-first `feBlend` in a mode where the input order matters (normal,
  overlay, hard/soft-light, dodge, burn, hue, saturation, color,
  luminosity) maps with the flood as the layer's content and the group's
  root precapture as the backdrop, so all sixteen modes are exercised.
- A filter that is a flood alone replaces its source instead of skipping
  the group.
- `reftest.py` takes the framing from `FRAME_W`/`FRAME_H`, makes its paths
  absolute (a relative `--out` gave Chromium a `file://` URL that loaded
  nothing, every screenshot blank), retries a blank screenshot and offers
  `--chromium-only`.

Corpus A/B of these harness changes on the master library (`_logos_full_master_h12b`
vs `_logos_full_master_h14`, 552 frames at 1/2/4x): 77 frames change by the
snapped region edge; against Chromium refs mean px > 8 4.01 % → 3.96 %,
structural 0.860 % both, 5 better / 68 same / 4 worse by at most 0.003 %.
