# Ported reftests, second blend batch (PRs #355 and #356)

Fifty-two test / `-ref.svg` pairs in five directories: every `feBlend`
mode with a flood over a solid, every `mix-blend-mode` on a group, blends
under gradients, clips and group opacity, filter chains ending in a blend,
and `color-interpolation-filters` / gradient `color-interpolation` cases.
`harness/reftest.py` runs them; the framing comes from `FRAME_W` /
`FRAME_H` / `BOX` (`1024` and `256` square framings were used).

Chromium 131 renders every pair alike except at the filter region's edge
pixels, where the hand-made solid references differ from a filtered
element by up to 0.31 % of pixels at 1024 (1.25 % at 256):
Blink fills the region's enclosing pixel rect, the references are plain
anti-aliased rects. `filter-chain-double-feblend` is white on white by
design.
