# WPT mix-blend-mode / compositing reftests (`corpus/wpt-blend-reftests/`), 2026-09-23

Twenty-three test / reference pairs extracted from WPT into standalone
SVG. Validation: Chromium 131 renders each pair (`make_ref.py`, 460x260,
zoom 1); a pair is valid when Chromium's test matches its reference.
Then each of master ae66a1e, #355 (fe-blend) and #356 (mix-blend) renders
test and reference with one harness (`harness/reftest.py`); a pass is the
binary's test matching its own reference. Columns: percent of pixels beyond
8/255: Chromium test-vs-ref | binary test-vs-ref / binary test-vs-Chromium.

    blend-clip-parent-non-overflow | 0.05% | 13.58% / 13.58% | 13.58% / 13.58% | 0.05% / 0.19% |
    blend-clip-rotated | 0.00% | 27.72% / 27.72% | 27.72% / 27.72% | 0.00% / 0.00% |
    blend-clip-rounded-child | 0.00% | 18.06% / 18.14% | 18.06% / 18.14% | 0.00% / 0.16% |
    blend-clip-rounded-parent | 0.10% | 12.84% / 13.04% | 12.84% / 13.04% | 0.00% / 0.29% |
    blend-clip-sibling-overlap | 0.00% | 9.41% / 9.48% | 9.41% / 9.48% | 0.00% / 0.16% |
    blend-filter-identity-isolation | 0.00% | 33.44% / 33.44% | 33.44% / 33.44% | 0.00% / 0.00% |
    blend-filter-order-grayscale-screen | 0.00% | 0.00% / 33.44% | 0.00% / 33.44% | 0.00% / 0.00% |
    filter-chained-identity | 0.00% | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% |
    blend-mask-circle-difference | 0.00% | 16.98% / 16.99% | 16.98% / 16.99% | 0.00% / 0.26% |
    filter-vs-clip-precedence | 0.00% | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% |
    filter-vs-mask-precedence | 0.00% | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% |
    blend-interposed-child | 0.00% | 33.44% / 33.44% | 33.44% / 33.44% | 0.00% / 0.00% |
    blend-isolation-explicit | 0.00% | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% |
    blend-isolation-group-opacity | 0.00% | 0.00% / 0.00% | 0.00% / 0.00% | 0.00% / 0.00% |
    blend-overflowing-child | 0.00% | 2.09% / 2.09% | 2.09% / 2.09% | 0.00% / 0.00% |
    blend-stacking-context-bounds-isolation | 0.21% | 12.86% / 12.86% | 12.86% / 12.86% | 0.21% / 0.00% |
    blend-transparent-backdrop-boundary | 0.00% | 17.34% / 17.34% | 17.34% / 17.34% | 0.00% / 0.00% |
    filter-blur-clip-ancestor | 0.56% | 0.00% / 0.56% | 0.00% / 0.56% | 0.00% / 0.56% |
    filter-clip-under-blur | 0.24% | 0.00% / 1.35% | 0.00% / 1.35% | 0.00% / 1.35% |
    filter-drop-shadow-overflow-clipped | 0.84% | 4.52% / 5.35% | 4.52% / 5.35% | 4.52% / 5.35% |
    blend-plus-lighter-isolated | 0.00% | 3.85% / 3.85% | 3.85% / 3.85% | 3.85% / 3.85% |
    blend-svg-rectangle-multiply | 0.00% | 33.44% / 33.44% | 33.44% / 33.44% | 0.00% / 0.00% |
    blend-svg-root-isolation | 33.44% | 0.00% / 33.44% | 0.00% / 33.44% | 33.44% / 0.00% |

Valid pairs: 22 (Chromium test-vs-ref at most 0.84 %, an antialiased
edge). `blend-svg-root-isolation` needs its WPT `<img>` embedding (an SVG
image is an isolated group; inline, the root blends with the page), so
Chromium fails the standalone version too: not counted, not femtovg's.

Passes (test-vs-ref at most 0.5 %): master 6, #355 6, #356 19 of 22.

The three #356 misses:
- `filter-drop-shadow-overflow-clipped` (4.52 %): a layer opened under a
  scissor captured only the scissor's rect, so an element past the SVG
  viewport with an feDropShadow was not in the store and cast no shadow
  into view. Library fix on branch shadow-capture (the capture takes in
  what reaches into the scissor once shifted by the offset and spread by
  the blur): test-vs-ref 0.00 %.
- `blend-plus-lighter-isolated` (3.85 %): `mix-blend-mode: plus-lighter`
  (compositing-2) is not parsed by usvg 0.48, so the harness cannot see
  it; femtovg's `CompositeOperation::Lighter` is the equivalent. Not a
  femtovg gap; a harness one without a usvg change.
- `blend-svg-root-isolation`: invalid outside `<img>`, above.

Two harness gaps the suite exposed, fixed in `harness/_logos_full.rs`
(`layer_chain`): a group's `feColorMatrix` / alpha-only
`feComponentTransfer` / `feGaussianBlur` chain now maps to layer passes in
the color space each primitive asks for, following the chain from the
source graphic (a transparent `feFlood` blended in is the identity, the
Figma export idiom), where before every blur in the filter was applied to
the whole group whatever its input - which blurred the source of a
manual drop-shadow chain (`feGaussianBlur in=SourceAlpha -> feOffset ->
feMerge`) along with the shadow - and a color-matrix group was skipped as
unsupported
(`blend-filter-order-grayscale-screen`: 33.44 % -> 0.00 % against
Chromium on #356); and a blur runs in linearRGB when
`color-interpolation-filters` says so, which matters where two colors
meet under the blur (`filter-clip-under-blur`: 8.30 % -> 1.35 % against
Chromium, Chromium's own test-vs-ref 0.24 %; the rest is the blur
kernel). Single-color blurs are unchanged by the color space, which is
why the earlier corpus experiment measured nothing.

## The harness change across the corpus (`harness/ab.py`, master's library, old harness vs new)

102 of 564 frames change (BuseyBench groups with blur, color-matrix or
manual drop-shadow chains; google-workspace-48px is unchanged once the
transparent-flood blend counts as the identity), SVGenius none. The 30
changed frames with Chromium references: mean pixels beyond 8/255
7.81 % -> 5.78 %, structural 2.90 % -> 1.42 %; 10 better, 12 unchanged,
8 worse by at most 0.36 points (gemini-3-1-pro-preview 4x 8.03 -> 8.39,
gemini-3-7-flash 2x 6.57 -> 6.77: multi-color blurs now in linearRGB, the
rest of their residue is the blur kernel). The large gains are the manual
drop-shadow chains no longer blurring the whole group (gpt-5-2-pro 4x
48.34 -> 21.52, gpt-5-6-sol-pro 4x 31.81 -> 19.05); mapping that chain to
the shadow state is the next harness step.
(`harness/wpt-blend-reftests-harness-ab-2026-09-23.txt`)

## Re-measured 2026-09-25, with #361 on master

Master 9f2523b (`_logos_full_master_h15`) versus #356 with that master
merged (`_logos_full_mixblend13`), same harness, 460x260 framing
(`wpt-blend-reftests-master-361-2026-09-25.txt`,
`wpt-blend-reftests-356-2026-09-25.txt`): master passes 9 of the 22 valid
pairs, #356 passes 20 and matches Chromium on 21. `filter-drop-shadow-
overflow-clipped` now matches Chromium to 0.00 % and misses only its
reference (0.84 %, Chromium's own test-vs-reference gap); `plus-lighter`
stays (usvg drops it); `blend-svg-root-isolation` is the invalid pair.
