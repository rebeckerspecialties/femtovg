# WPT css-masking candidates: femtovg (#323 layer masks + #324 clip paths) vs Chromium 131 and Firefox

Measured 2026-09-16 on the `corpus-all3` harness tree (`/private/tmp/wt-all3`, the whole
open stack merged) with `_wpt_masks.rs`, a copy of `_logos_full.rs` plus three
translations the WPT files need (nested clipPath chains, clipPath children carrying
clip-path, `<text>`); built with
`cargo rustc --example _wpt_masks --features wgpu -- --cfg harness_clip --cfg harness_turbulence`
(binary md5 `1893eb004619d239c29d68c46662cf67`), run with `SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1`.

**Sources.** `css/css-masking/mask-svg-content/{mask-negative-scale, mask-with-filter,
mask-text-001, mask-on-thin-stroked-path-userspaceonuse}.svg` and every
`css/css-masking/clip-path-svg-content/*.svg` whose name contains `nested` or `mask`
(18 files), plus the reference each one names with `<link rel="match">` (12 refs), from
WPT master via raw.githubusercontent.com. Originals are in `tests/` and `refs/`.

**Framing.** 20 of the 22 files declare no width/height/viewBox; a browser gives such a
root a 100%x100% viewport while usvg gives it `Options::default_size` (100x100), so both
renderers were fed `framed/*.svg`: the same file with an explicit `width`/`height`/`viewBox`
covering the content (`frame.py`, `manifest.json`). The harness box is `max(vb.w, vb.h)`
so zoom 1.0 is one user unit per device pixel and zoom 2.0 is device-pixel-ratio 2; the
frame is `2*box + 60` square with the box centred, so the 2x zoom stays inside it. The two
panning tests move the viewport with `currentTranslate.x = -75` from a `<script>`; usvg has
no DOM and in a nested-svg reference page the script would pan the outer frame, so the
script is dropped and the pan is expressed as `viewBox="75 0 200 200"`. `mask-text-001`
asks for WPT's Ahem font (`/fonts/ahem.css`), not installed here, so it is measured as-is
(both renderers fall back) and again with `font-family="Arial"` (`mask-text-001-arial`).

**References.** Chromium: `chrome-headless-shell` 131 `--headless --disable-gpu
--hide-scrollbars --force-device-scale-factor=1 --window-size=W,H
--default-background-color=FFFFFFFF` on `make_ref.py` pages (same pivot zoom and box).
Firefox Developer Edition headless at 1x on the same pages. Every WPT reference file was
rendered by Chromium, Firefox and femtovg too.

**Metrics.** Over the SVG's own box (mapped through the pivot zoom, so the padded frame does
not dilute percentages): `px>20` = share of box pixels whose max channel delta exceeds
20/255 (`compare.py`'s metric), `struct` = the same after a 2-px erosion, `max` = max
channel delta, `exact` = count of pixels that differ at all. WPT's own rule is test-vs-ref
in the *same* engine under the file's `<meta name=fuzzy>` (max channel delta; number of
differing pixels; 0/0 when absent), so `femtovg test-vs-ref` and `Chromium test-vs-ref`
give that verdict for each engine (the pixel budget is scaled by zoom^2 at 2x).

## Table

| case | zoom | fvg vs Chromium(test) px>20 / struct / max / exact | fvg vs Chromium(ref) px>20 / struct / max | Chromium test-vs-ref px>20 | Chromium vs Firefox (test, 1x) px>20 / struct | fvg vs Firefox (1x) px>20 / struct | femtovg test-vs-ref exact / max -> WPT | Chromium test-vs-ref exact / max -> WPT | verdict |
|---|---|---|---|---|---|---|---|---|---|
| clip-path-clip-nested-twice | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (nested clipPath chain via clip_path intersection) |
| clip-path-clip-nested-twice | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (nested clipPath chain via clip_path intersection) |
| mask-and-nested-clip-path | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (nested clipPath chain) |
| mask-and-nested-clip-path | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (nested clipPath chain) |
| mask-negative-scale | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-negative-scale | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-nested-clip-path-001 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage, two levels) |
| mask-nested-clip-path-001 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage, two levels) |
| mask-nested-clip-path-002 | 1.0 | 64.25% / 55.522% / 255 / 25700 | 64.25% / 55.522% / 255 | 0.00% | 0.00% / 0.000% | 64.25% / 55.522% | 25700 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-002 | 2.0 | 30.19% / 25.847% / 255 / 48300 | 30.19% / 25.847% / 255 | 0.00% | - | - | 48300 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-003 | 1.0 | 62.00% / 53.280% / 255 / 24800 | 62.00% / 53.280% / 255 | 0.00% | 0.00% / 0.000% | 62.00% / 53.280% | 24800 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-003 | 2.0 | 30.19% / 25.847% / 255 / 48300 | 30.19% / 25.847% / 255 | 0.00% | - | - | 48300 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-004 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-004 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-005 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-005 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-006 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-006 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-007 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-007 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-008 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-008 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-009 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-009 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match (clip coverage) |
| mask-nested-clip-path-010 | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-nested-clip-path-010 | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-nested-clip-path-panning-001 | 1.0 | 64.25% / 55.522% / 255 / 25700 | 64.25% / 55.522% / 255 | 0.00% | 0.00% / 0.000% | 64.25% / 55.522% | 25700 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-panning-001 | 2.0 | 30.19% / 25.847% / 255 / 48300 | 30.19% / 25.847% / 255 | 0.00% | - | - | 48300 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-panning-002 | 1.0 | 62.00% / 53.280% / 255 / 24800 | 62.00% / 53.280% / 255 | 0.00% | 0.00% / 0.000% | 62.00% / 53.280% | 24800 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-nested-clip-path-panning-002 | 2.0 | 30.19% / 25.847% / 255 / 48300 | 30.19% / 25.847% / 255 | 0.00% | - | - | 48300 / 255 -> FAIL (fuzzy 0-0; 0-0) | 0 / 0 -> pass | DEVIATION: nested layer mask origin (finding A) |
| mask-objectboundingbox-content-clip-transform | 1.0 | 0.68% / 0.000% / 149 / 373 | 0.68% / 0.000% / 149 | 0.00% | 0.15% / 0.000% | 0.68% / 0.000% | 332 / 129 -> FAIL (fuzzy 0-38; 0-268) | 66 / 1 -> pass | edge only: hard clip edge vs AA mask edge (finding B) |
| mask-objectboundingbox-content-clip-transform | 2.0 | 0.32% / 0.000% / 167 / 738 | 0.32% / 0.000% / 167 | 0.00% | - | - | 620 / 127 -> FAIL (fuzzy 0-38; 0-268) | 137 / 1 -> pass | edge only: hard clip edge vs AA mask edge (finding B) |
| mask-objectboundingbox-content-clip | 1.0 | 0.68% / 0.000% / 149 / 374 | 0.68% / 0.000% / 149 | 0.00% | 0.15% / 0.000% | 0.68% / 0.000% | 332 / 123 -> FAIL (fuzzy 0-38; 0-376) | 67 / 1 -> pass | edge only: hard clip edge (finding B) |
| mask-objectboundingbox-content-clip | 2.0 | 0.32% / 0.000% / 167 / 738 | 0.32% / 0.000% / 167 | 0.00% | - | - | 620 / 126 -> FAIL (fuzzy 0-38; 0-376) | 137 / 1 -> pass | edge only: hard clip edge (finding B) |
| mask-on-thin-stroked-path-userspaceonuse | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-on-thin-stroked-path-userspaceonuse | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-text-001 | 1.0 | 1.49% / 0.020% / 239 / 207 | 1.31% / 0.030% / 240 | 1.38% | 1.81% / 0.000% | 2.02% / 0.080% | 20 / 17 -> FAIL (fuzzy 0-0; 0-0) | 188 / 65 -> FAIL | within browser envelope (fallback font on both sides, finding D) |
| mask-text-001 | 2.0 | 0.85% / 0.000% / 232 / 470 | 0.77% / 0.000% / 243 | 0.69% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 383 / 65 -> FAIL | within browser envelope (fallback font on both sides, finding D) |
| mask-userspaceonuse-content-clip-transform | 1.0 | 0.68% / 0.000% / 149 / 373 | 0.68% / 0.000% / 149 | 0.00% | 0.15% / 0.000% | 0.68% / 0.000% | 332 / 129 -> FAIL (fuzzy 0-38; 0-268) | 66 / 1 -> pass | edge only: hard clip edge (finding B) |
| mask-userspaceonuse-content-clip-transform | 2.0 | 0.32% / 0.000% / 167 / 738 | 0.32% / 0.000% / 167 | 0.00% | - | - | 620 / 127 -> FAIL (fuzzy 0-38; 0-268) | 137 / 1 -> pass | edge only: hard clip edge (finding B) |
| mask-userspaceonuse-content-clip | 1.0 | 0.68% / 0.000% / 149 / 374 | 0.68% / 0.000% / 149 | 0.00% | 0.15% / 0.000% | 0.68% / 0.000% | 332 / 123 -> FAIL (fuzzy 0-38; 0-376) | 67 / 1 -> pass | edge only: hard clip edge (finding B) |
| mask-userspaceonuse-content-clip | 2.0 | 0.32% / 0.000% / 167 / 738 | 0.32% / 0.000% / 167 | 0.00% | - | - | 620 / 126 -> FAIL (fuzzy 0-38; 0-376) | 137 / 1 -> pass | edge only: hard clip edge (finding B) |
| mask-with-filter | 1.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | 0.00% / 0.000% | 0.00% / 0.000% | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-with-filter | 2.0 | 0.00% / 0.000% / 0 / 0 | 0.00% / 0.000% / 0 | 0.00% | - | - | 0 / 0 -> pass (fuzzy 0-0; 0-0) | 0 / 0 -> pass | match |
| mask-text-001-arial | 1.0 | 1.37% / 0.000% / 252 / 226 | 1.35% / 0.010% / 253 | 1.26% | 1.83% / 0.000% | 2.07% / 0.090% | 20 / 1 -> FAIL (fuzzy 0-0; 0-0) | 200 / 64 -> FAIL | within browser envelope (same face both sides) |
| mask-text-001-arial | 2.0 | 1.01% / 0.000% / 255 / 496 | 0.88% / 0.000% / 255 | 0.77% | - | - | 3 / 1 -> FAIL (fuzzy 0-0; 0-0) | 397 / 65 -> FAIL | within browser envelope (same face both sides) |

Box sizes: 200x200 user units (40,000 px at 1x, 160,000 at 2x) except
mask-and-nested-clip-path 300x300, mask-nested-clip-path-010 400x100,
mask-on-thin-stroked-path-userspaceonuse 200x100, mask-text-001 100x100.

## Findings

### A. Nested layer masks land offset by the enclosing layer's origin (femtovg, #323)

`mask-nested-clip-path-002`, `-003`, `-panning-001`, `-panning-002` (a `<g mask>` whose
child carries its own `mask`, or a mask whose content is itself masked): femtovg draws green
only in the bottom-right 70x70 of the 200x200 box at 1x (device x,y 260..329 = SVG
130..199) and in SVG 15..200 at 2x, against Chromium/Firefox's full drawing: 64.25% /
62.00% of the box differs at 1x, 30.19% at 2x, max delta 255, and the same-engine WPT
check fails (25,700 / 24,800 px at 1x, 48,300 at 2x). The browsers agree with each other
and with the references to 0 px.

Mechanism, proven by A/B: the harness places every mask at the screen-device rect
`(0, 0, frame_w, frame_h)`, which `LayerEffects::with_mask` documents as device space
(`src/lib.rs:470-488`). `begin_layer` derives a layer's origin from the scissor's bounds
in the *current* device space (`src/lib.rs:1440-1446`, stored at `:1484`) and then shifts
device space so that origin lands on (0, 0) (`:1504`). Inside the outer masked layer the
scissor bounds are therefore already shifted, so the inner layer records origin (0, 0)
in the *outer store's* space, and `apply_layer_mask` subtracts that local origin from the
caller's screen-space rect (`src/lib.rs:1700-1712`, `mask.x - minx`). With the viewport
scissor at (130, 130) the inner mask is applied 130 px too far right and down: the mask's
white region (screen 130..330) lands at 260..460, and its intersection with the box is the
260..330 band observed; at 2x the box sits at (30, 30) and the band starts at 60, also as
observed. Removing the scissor (`VIEWPORT_CLIP` unset, top-level origin 0,0) or moving the
box to the frame origin (`BOX_X=0 BOX_Y=0`) makes all four files match Chromium with **0
differing pixels** at 1x and 2x (`ab/noclip_*`, `ab/origin0_*`). A caller cannot
compensate: there is no getter for the current layer origin. It is the defect the
demo-assets commit 34c01cf reduces from qwen3-8-2-4t-a95b (`mask-nested-origin-reduction.svg`:
displaced by the outer layer's capture origin, (130,30) at 1x and (30,0) at 2x in the
460x260 framing, none at 4x); these four WPT files are the spec's own tests for it.

### B. Clip edges are single-sample; a circle taken as a clip differs from the same circle as a mask (femtovg, #324's documented follow-up)

`mask-objectboundingbox-content-clip`, `-transform`, `mask-userspaceonuse-content-clip`,
`-transform`: the test clips the mask content with a circle, the reference draws the
circle into the mask. In Chromium the two agree to 66-67 px / max delta 1 (pass under the
files' fuzzy 0-38; 0-268/376); in femtovg they differ by 332 px / max 123-129 at 1x and
620 px / max 126-127 at 2x, i.e. the circle's perimeter (2*pi*50 = 314 px; 628 at 2x) at
about half coverage: the clip edge is hard (`clip_path` doc, `src/lib.rs:1769-1771`) while
the mask edge is antialiased. Against Chromium's rendering of the test: 0.68% of the box at
1x (373 px, max 149) and 0.32% at 2x (738 px, max 167), structural 0.000% - edge ribbon
only; the browser envelope on these files is 0.15%. Fails WPT's fuzzy budget on both counts
(delta 129 > 38, 332 px > 268).

### C. Three translations the harness needed (not femtovg deviations; before -> after)

* **clipPath carrying clip-path** (`clip-path-clip-nested-twice`: three chained clipPaths;
  `mask-and-nested-clip-path`): `_logos_full.rs` applied only the clipPath's own content
  (53.43% and 11.11% of the box wrong: the whole r=100 circle instead of the 50..150
  square; a red 100x100 block). The chain is `ClipPath::clip_path()` in usvg 0.48.1
  (`tree/mod.rs:828`); each ancestor's content is taken as its own `clip_path` first,
  outermost in, and #324's stencil intersection does the rest: **0 px** at 1x and 2x.
* **clipPath children carrying clip-path** (`mask-nested-clip-path-001` and `-004`..`-009`):
  the region is the union over children of (child ∩ child's clip), which no sequence of
  intersections expresses; the harness's path union ignored the per-child clips, so the
  mask's black rect covered everything (files 001/004/007/008 blank, 005/006/009 fully
  green: 64.00% of the box). Browsers rasterize such a clip as a mask (Blink's mask-based
  clipping, which is what these WPT files were written to force). The harness now does
  the same with the two APIs together: `capture_clip_coverage` draws every child white
  under its own `clip_path` intersection into a canvas-sized image, and the clipped group
  applies it through `LayerEffects::with_mask(.., MaskKind::Alpha, ..)`
  (`_wpt_masks.rs:151-232`, `:800-820`; the precapture walk carries a base transform and
  recurses into clip content so 001's two-level nesting captures innermost first,
  `:236-275`). Result **0 px** on all seven at 1x and 2x, and the A/B against the previous
  build changed only those files (12 frames, then 2 frames for the 001 fix). This works
  here because the clipped groups sit in mask content (an image target, origin 0); a
  coverage-masked group inside a scissored layer would hit finding A.
* **`<text>`** (`mask-text-001`): `_logos_full.rs` had no `usvg::Node::Text` arm, so text
  drew nothing anywhere (0 ink pixels on the unmasked reference too). Drawing
  `Text::flattened()` (`tree/text.rs:704`) fixes it: the test lands at 1.49% / struct
  0.020% of the box against Chromium at 1x and 0.85% / 0.000% at 2x, inside the
  Chromium-vs-Firefox envelope on the same file (1.81%); with Arial on both sides 1.37% /
  0.000% and 1.01% / 0.000% (envelope 1.83%). femtovg's own mask-vs-direct residual is 20 px
  / max 17 (Arial: 20 px / max 1), smaller than Chromium's 188-200 px / max 64-65.

### D. Fonts

Ahem is not installed, so `mask-text-001` renders in each renderer's fallback face (both
draw the same rotated "foobar", 199 vs 184-212 ink pixels at 1x). The Arial variant removes
the face difference; what remains is glyph rasterization (femtovg's thin-fill fringe,
femtovg#327) at the 1.0-1.5% level, below the browsers' own disagreement.

### E. Browser envelope

Chromium 131 vs Firefox on the test pages at 1x: 0.00% on 18 files, 0.15% (edge) on the four
circle files, 1.81-1.83% on the text files. Chromium matches every WPT reference with 0 px
except the circle files (66-67 px, max 1) and text (188-200 px, max 64-65, an AA
difference between masked and direct text).

## Files

`tests/`, `refs/` originals; `framed/` what was rendered; `pages/` the reference pages;
`chromium/`, `firefox/` browser screenshots (`chr_<case>_{test,ref}_<zoom>.png`,
`ff_<case>_{test,ref}_1.0.png`); `femtovg/` femtovg renders as PNG (`fvg_<case>_<zoom>.png`,
`fvgref_<ref>_<zoom>.png`); `strips/` femtovg | Chromium test | Chromium ref | Firefox test |
diff overlay per case and zoom; `metrics.json`, `metrics_selfref.json`; `frame.py`,
`render.sh`, `metrics.py`, `results_md.py`; `_wpt_masks.rs` the harness variant.
