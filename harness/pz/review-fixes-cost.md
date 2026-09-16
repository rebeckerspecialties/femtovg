# Cost of the #323 review fixes: CPU, GPU and memory against the pre-review numbers

Date 2026-09-16. Question: did the #323 review fixes - (a) one ownership definition for a layer's images (kept across a flush, returned on a discard: 84bf2b2, 556f299), (b) the mask placed against the root device origin (0bd7e9f), (c) `begin_layer` reserving the filter chain's result and scratches with the store (dc0f9a9; previously acquired lazily at `end_layer`), (d) `LayerEffects::default()` = `new()` (b8b2fdc), (e) a rounded/rotated scissor clipping only the composite, not the draws inside the layer (e7788a1) - and #324's `clear_rect` now also clearing the stencil's winding bits (1e144b9) change CPU, GPU or memory behaviour on the 70-row Pi Zero matrix (harness/pz/measurements.json, 2026-09-13)?

## Summary

* **Memory: nothing moved.** All 70 rows (27 BuseyBench + 8 icon files x 640x480 and 1080p) hold exactly the transient bytes measurements.json recorded, begin the same number of layers (2,379 per framing) and pass none through at the default 256 MiB budget. A pool simulation of every 1080p LAYER_LOG under both reservation policies gives the same bytes for all 28 files: (c) holds a blurred layer's result and scratch (2 x 5.06-5.64 MiB at 1080p, 2 x 1.00-1.56 MiB at 640x480) from `begin_layer` instead of from `end_layer`, but the pool's peak is the per-(size, flags) class maximum, and a nested layer's images are never in the enclosing chain's class on this corpus.
* **CPU: within noise.** Same-build A/B (debug build, same harness) of the fixed tree against the pre-fix tree: per-frame wall time summed over the 35 rows moves -1.6 % at 640x480 and -0.5 % at 1080p (CPU time -1.0 % / -0.3 %); every BuseyBench row is within -12.9 %..+6.6 %; the six rows beyond +-20 % are 2-9 ms icon frames at the 1 ms/frame resolution of `/usr/bin/time`.
* **GPU: same command stream.** 61 of 70 renders are bit-identical between the two builds; the 9 that differ (three stroke-heavy icons, splash-logo by 2-3 px, qwen3-8-2-4t-a95b by <= 5/255) differ identically with `NO_CLIP=1` and include fox-with-box-on-cloud, which opens no layer at all, so they come from the other commits between the two builds (#336's merged form in src/path/cache.rs, #339's stroke alpha, the clip fill-rule pass-through), not from (a)-(e). The stencil-bit clear costs nothing on wgpu (the stencil attachment is loaded and stored on every pass, src/renderer/wgpu.rs:2155-2158); on GL over Mesa/vc4 it is one full-target stencil quad per `clear_rect` (0.4-1.8 ms per icon frame, 31 ms mean per BuseyBench frame at 640x480 on the model's rates) and, for a pass that did not otherwise touch stencil, a Z/S tile load+store (bound: +1.6-7.5 ms icons, +133 ms mean BuseyBench at 640x480, half of which the model's central assumption already charges).
* **Pi Zero budgets (32-48 MiB, 1080p):** the peak bytes are identical on both trees at every budget; what (c) changes is who gets refused. At 48 MiB the fixed tree passes 17 of 2,374 layers through against 10 (the same 3 files; the renders differ from each other by at most 8,630 px, max delta 45, and from Chromium by the same box percentages within 0.03 points). At 32 MiB it is 104 against 65 (16 files against 14), and on 4 files the picture is worse than the pre-fix tree's silent filter drop (qwen3-8-max: box px>20 5.61 % vs 0.91 %; gpt-5-6-sol-pro 8.78 % vs 4.45 %; qwen3-8-27b 0.33 % vs 0.04 %; nex-n2-pro 1.57 % vs 1.56 %) - the fixed tree drops the whole effect set where the old tree kept opacity and dropped only the blur without reporting it.

## 1. Setup

**Binaries.** Fixed: `/private/tmp/wt-all3/target/debug/examples/_logos_full`, md5 7596fc6e500e10e016916730008149ee, tree /private/tmp/wt-all3 at 7bbcb5e (corpus-all3 = #322 + #323 with the review fixes + #324 clip + #338 turbulence + #339 + #336, plus the clear_rect winding-bit clear as pushed to #324 and one uncommitted line, src/lib.rs:1959, passing the fill rule to `expand_fill` for clip fills), built with `--cfg harness_clip --cfg harness_turbulence` (`harness cfgs: clip=true turbulence=true`). Pre-fix: `$S/wpt-masks/bin/_logos_full.orig`, md5 8dea3accf4cae4948f1f1de352363383, the same harness on corpus-all3 at f05e2da (the tree measurements.json and mask-budget-ladder.md's "pre-fix #323" columns used), copied at 13:29 before the review fixes landed. `git log f05e2da..7bbcb5e -- src/` is the five review-fix commits plus the two master merges that bring 83ea071 (#336, src/path/cache.rs +107 lines) and 1715442 (#339), the stencil clear (src/renderer/opengl.rs +16, wgpu.rs +24) and src/transient.rs doc lines; whether the .orig binary already carried the then-uncommitted stencil-clear change cannot be told from the binary. Nothing was rebuilt.

**What the binary prints.** With `LAYER_STATS=1` (examples/_logos_full.rs:936-964): `layers begun`, `transient bytes held at flush` (`Canvas::transient_image_bytes()` sampled before `flush_to_output`, the frame's peak since the pool frees only at the flush), `layers passed through`, the cfgs and the skipped-filter counters. The layer counters are process-wide atomics, so under `FRAMES=n` they are n times the per-frame value (checked: every FRAMES=11 run reports exactly 11x its FRAMES=1 run and the same held bytes - no state leaks across frames). The binary has no per-phase timers: measurements.json's `femtovg_record_ms` / `encode_ms` / `gpu_ms` came from the PZ_STATS-instrumented harness on a release build (wt-pz, 0a56986) and cannot be reproduced with this binary, so the timing comparison here is a same-build A/B of fixed vs pre-fix on the debug build, with measurements.json's release numbers carried along for reference only.

**Protocol** (`$S/cost/run_cost.py`). Per row: framing env from run_matrix.py (640x480: FRAME 640x480, BOX 480 at 80,0; 1080p: FRAME 1920x1080, BOX 1080 at 420,0), `SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1 LAYER_STATS=1`, default 256 MiB budget, zoom 1.0; one `FRAMES=1` run and one `FRAMES=11` run under `/usr/bin/time -l`, per-frame wall / user / sys = (11-frame - 1-frame) / 10, two repeats, the repeat with the smaller wall delta kept. `/usr/bin/time` has 10 ms resolution, so a per-frame figure is quantised to 1 ms; the debug build is CPU-bound (user+sys per frame >= wall on every BuseyBench row: recording and wgpu encoding in a debug build take 30-240 ms per frame while the Metal GPU work overlaps), so GPU-side changes cannot show in these timings and are argued from the command stream instead (section 3). Fixed and pre-fix matrices were run serially with nothing else on the GPU; the pixel and budget runs came after.

## 2. The 70-row matrix against measurements.json

Totals (35 rows per framing; "pre" = measurements.json, "fixed" / "pre-fix" = today's two binaries):

| framing | layers begun pre -> fixed | pass-through pre -> fixed | transient sum pre -> fixed (pre-fix today) | wall/frame sum pre-fix -> fixed | cpu/frame sum pre-fix -> fixed |
|---|---|---|---|---|---|
| 640x480 | 2,379 -> 2,379 | 0 -> 0 | 270.74 -> 270.74 MiB (270.74) | 2,380 -> 2,343 ms (-1.6 %) | 2,480 -> 2,456 ms (-1.0 %) |
| 1080p | 2,379 -> 2,379 | 0 -> 0 | 1,023.47 -> 1,023.47 MiB (1,023.47) | 2,575 -> 2,563 ms (-0.5 %) | 2,617 -> 2,609 ms (-0.3 %) |

Per row: `transient_at_flush`, `layers` and `pass_through` are identical to measurements.json on all 70 rows (0 moved). Timing: over the 54 BuseyBench rows the fixed/pre-fix wall delta has median +0.0 %, minimum -12.9 % (gemini-3-1-pro-preview at 1080p, 171 -> 149 ms) and maximum +6.6 % (qwen3-8-flash at 1080p, 137 -> 146 ms), CPU median +0.0 %, -12.2 %..+6.5 %; nothing is beyond the +-20 % noise band. Six icon rows exceed +-20 % on wall time - clipdemo@640x480 (2 -> 0-1 ms), duckduckgo-com_2x@640x480 (3 -> 2), google-workspace-48px@640x480 (4 -> 5), splash-logo@640x480 (3 -> 2), kit@1080p (5 -> 8), mr-settodefault@1080p (9 -> 7) - all frames of 2-9 ms where one timer tick is 11-50 %, and their repeats straddle the same values in both directions. Peak RSS (`/usr/bin/time -l`, includes Metal residency) moves by a median +2.9 MiB with a -84..+48 MiB spread across the 70 rows in both directions; it is not a property of the tree (the same binary's two repeats differ by as much) and the deterministic figure is the held transient bytes. The full per-row table is appendix A.

**Render identity** (`$S/cost/identity.py`, FRAMES=1, `cmp`): 640x480: 30 of 35 identical; 1080p: BuseyBench 26 of 27 identical (from the ladder's 256 MiB renders), icons 4 of 8. The differing rows: mr-settodefault (10,399 px at 640x480 / 24,080 px at 1080p, max delta 254), fox-with-box-on-cloud (5,860 / 13,041 px, max 63-248), duckduckgo-com_2x (4,030 / 8,984 px, max 204), splash-logo (3 / 2 px, max 12), qwen3-8-2-4t-a95b (18,064 / 83,769 px, max 5 / 2). Re-rendering the three icons with `NO_CLIP=1` gives the same pixel counts, fox-with-box-on-cloud opens no layer (0 layers, 0 transient bytes in both trees), and none of the five uses a mask, a rounded scissor, a nested filtered layer or a discard - the code (a)-(e) touch. They are the fill-winding (#336, hole-contour orientation, src/path/cache.rs) and sub-pixel stroke alpha (#339) commits whose merged forms are in 7bbcb5e and not in f05e2da, plus the clip fill-rule line; qwen3-8-2-4t-a95b's <= 5/255 over 18k px is the same class.

## 3. Attribution per change

Store sizes the arguments use (src/lib.rs:1541-1560, `transient::LAYER_GRANULARITY` 64): under `VIEWPORT_CLIP=1` a depth-0 layer's store is the box rounded to 64 (1080 -> 1088 px, 4,734,976 B = 4.52 MiB; 480 -> 512 px, 1,048,576 B = 1.00 MiB), padded by ceil(3 * min(sigma, 8)) + 2 per side when the chain has a Gaussian blur (1080 + 2 x 8..26 -> 1152 px, 5,308,416 B = 5.06 MiB; 480 -> 512 or 576 px, 1.00 / 1.27 MiB); a nested layer's scissor is the enclosing store (the offscreen state resets it, src/lib.rs:1719-1728), so a blurred child of a 1152 store is 1216 px (5,914,624 B = 5.64 MiB; 640 px = 1.56 MiB at 640x480). A capture is `PREMULTIPLIED | FLIP_Y`, a chain's result and scratches and a luminance mask's converted image are `PREMULTIPLIED`; the pool reuses only an exact (width, height, flags) match (src/transient.rs:74-93).

**(a) One ownership definition** (`LayerRecord::images()`, src/lib.rs:563-578; used by the flush retention at src/lib.rs:2771-2772, `end_layer`'s release at 1706-1713 and `discard_open_layers` at 761). CPU: the flush builds the `held` list by iterating every open layer's images (up to 6 ids per open layer instead of 1); the harness closes every layer before the flush, so `held` is empty on every row and the release loop is unchanged. GPU: none. Memory: an open masked or filtered layer now keeps 1-5 more images live across a flush - correct ownership, not a per-frame cost; a discard returns them instead of leaking them to the flush. Evidence: identical held bytes and timing on all 70 rows.

**(b) Mask against the root device origin** (`root_origin` on `LayerRecord`, src/lib.rs:545-552; computed once per `begin_layer` as the enclosing origin plus the store origin, 1603; read by `apply_layer_mask` at 1809 instead of `origin`). One tuple addition per layer and a different pair of floats in the mask's image paint; no image, pass or fragment changes. Evidence: identical held bytes, timing and renders on every masked row at 256 MiB (all 15 mask-referencing BuseyBench files and google-workspace-48px are bit-identical between the builds at 1080p).

**(c) Filter-chain images reserved at `begin_layer`** (`reserve_filter_images`, src/lib.rs:1774-1786: the result plus `min(2, passes - 1)` scratches from `acquire_filter_scratches`, all store-sized and `PREMULTIPLIED`; `filter_passes` at 586-605 is the single plan; `end_layer` runs `run_filter_passes` through them, 1655-1660; pre-fix the result was acquired at `end_layer` and the scratches lazily inside the chain loop). Extra bytes held per open filtered level for the whole life of the layer instead of during `end_layer` only: a lone blur is two passes (blur + the parity identity), so result + 1 scratch = 2 stores: +10.1 MiB (1152 store) or +11.3 MiB (1216) at 1080p, +2.0-2.5 MiB (512/576) at 640x480, +3 stores (three passes or more) for chains that do not fold. Why the peak did not move: the bytes at the flush are the sum over classes of the largest number of images live at once in that class. Pre-fix, the enclosing chain's images were taken at `end_layer`, after the children had returned theirs, so a child's image could only lower the peak if it was in the enclosing chain's class (`PREMULTIPLIED`, the enclosing store size) - a luminance-masked, unfiltered child of a blurred parent. A blurred child is one size class larger (1216 vs 1152), an opacity-only child's capture is `FLIP_Y`, and the corpus has no masked child inside a blurred layer, so every class peaks at the same count under both policies. `$S/cost/poolsim2.py` replays each 1080p LAYER_LOG (`$S/cost/layerlog/`) through an exact-class pool under both policies: 28 of 28 files give the same bytes (e.g. gpt-5-2-pro, 32 layers opened inside blurred layers: 1088F x2, 1152F x2, 1152P x2, 1216F x1, 1216P x2 = 46.20 MiB under both; the measured 55.2 MiB adds the two luminance-mask coverage images and the turbulence scratches, which are policy-independent), and matches the measured bytes exactly on the files without masks, shadows or turbulence (gemini-3-7-flash, gemini-3-8-flash, gpt-5-6-sol-pro, gpt-5-6-terra-pro, both muse-spark files: 19.70 / 29.28 / 41.69 / 19.70 / 19.70 / 19.70 MiB). Measured: 70 of 70 rows unchanged; the synthetic blurred layer holds 3 x 5,308,416 = 15,925,248 B on both binaries. What does change is the order of allocation against a budget: the chain's images are now counted before the children's, so under a budget that cannot hold both, the fixed tree refuses the child (an honest pass-through) where the pre-fix tree admitted the child and then composited the parent unfiltered behind a `true` (wt-all3 pre-fix src/lib.rs:1539-1545, the undercount mask-budget-ladder.md documents). Section 4 measures that. CPU: the reservation moves three `acquire` calls (a linear scan of the free list each, src/transient.rs:82-88) from `end_layer` to `begin_layer` and adds none; timing unchanged.

**(d) `LayerEffects::default()` = `new()`** (src/lib.rs:523-527). A constructor; the harness builds effects with `LayerEffects::new()` (examples/_logos_full.rs:203) and the library never calls `default()` on a hot path. Zero cost by construction.

**(e) A rounded/rotated scissor clips the composite only** (src/lib.rs:1549-1554 and the removed re-installation of the scissor after `enter_offscreen_state`, e7788a1). The store already spanned the canvas for such scissors before the fix, so memory is unchanged. GPU: the scissor is a per-fragment mask, not a rasterizer clip: both fragment shaders evaluate `scissorMask` for every fragment of every draw (src/renderer/wgpu/shader.wgsl:188, src/renderer/opengl/main-fs.glsl:447) and multiply the color by it (wgsl:201, 206; glsl:460, 466); the only `discard`s are the stroke-AA threshold (glsl:401, wgsl:117). With no scissor set the params carry `scissor_ext = [1, 1]`, `scissor_scale = [1, 1]` and a zero matrix (src/renderer/params.rs:56-73), so the function still runs and returns 1. The draws inside the layer therefore shade the same fragments before and after; the fix removes the rounded-rect SDF branch (`scissorRadius > 0`, a uniform branch) from them and evaluates it once, on the composite, which was already the case for the composite. CPU: one fewer `Transform2D` premultiply per `begin_layer` under a rounded scissor. Evidence: the harness cannot exercise it - its only scissor is the axis-aligned viewport box (examples/_logos_full.rs:868) and SVG `clip-path` goes through `Canvas::clip_path` (#324, the stencil plane), whose composite-only semantics for a clip taken before `begin_layer` were already in f05e2da (9d9d0e0) - so the closest empirical check is `$S/cost/synth/rounded_clip_blur.svg` (a 24-unit-radius rounded clip-path over a blurred group, 1080p): both binaries begin 1 layer, hold 15.19 MiB, render bit-identically, and take 3.4 (fixed) vs 4.0 (pre-fix) ms per frame, the blur-only variant 2.9 vs 3.2 ms and the clip-only variant 1.6 vs 1.5 ms (0 layers) - all within the 1 ms quantisation.

**`clear_rect` clears the winding bits** (#324; 1e144b9). wgpu (src/renderer/wgpu.rs:1623-1700): the clear was already a full-rect quad through the unclipped fill-color pipeline; it now runs with a stencil state of `compare Always, pass/fail Zero, write_mask 0x7f` (1657-1678) instead of `StencilTest::Disabled`. Fragment count unchanged; the stencil attachment is `LoadOp::Load` / `StoreOp::Store` on every render pass regardless (2150-2158), so no tile traffic is added; the cost is the per-fragment stencil write in tile memory, and the two binaries' timings are indistinguishable (whether .orig already carried the change is unknown, see Setup). OpenGL (src/renderer/opengl.rs:702-722): `glClear(COLOR | STENCIL)` under `glStencilMask(0x7f)` instead of `glClear(COLOR)`, scissored to the rect. On a desktop GL that is one more buffer bit in the same clear. On the Pi's Mesa/vc4 stack it is not: Mesa's state tracker sends a stencil clear with a partial write mask through the quad path when the driver lacks `clear_masked` (`is_stencil_masked`, st_cb_clear.c:388-394 and 463-474; vc4 exposes no such cap), so every `clear_rect` becomes the fast tile clear of the color buffer plus one full-target quad writing stencil under the mask; the quad's draw marks the job's Z/S buffer for resolve (vc4_draw.c:513-515) while the tile clear did not cover it, so the job loads and stores the Z/S tile (vc4_job.c:58-64), and vc4 only has packed depth-stencil formats (vc4_screen.c:315-317), so femtovg's `STENCIL_INDEX8` renderbuffer (src/renderer/opengl/framebuffer.rs:46) is 4 B/px - the model's `stencil_bpp` 4. Per frame, from measurements.json's `clear_pixels` (every `clear_rect` is a full-target clear: the frame, each layer store, each mask normalization, each shadow coverage), at the model's central rates (stencil quads 0.8 Gfrag/s, bus 1.5 GB/s):

| set @ framing | clear_rect / frame | cleared Mpx / frame | stencil quad ms (certain) | Z/S load+store ms (bound, only passes that touched no stencil before) | modelled frame ms (model.md) |
|---|---|---|---|---|---|
| icons @ 640x480 (mean; range) | 1-5 | 0.7 (0.3-1.4) | 0.8 (0.4-1.8) | 3.5 (1.6-7.5) | 3-77 |
| icons @ 1080p | 1-5 | 3.8 (2.1-7.7) | 4.8 (2.6-9.6) | 20 (11-41) | 17-136 |
| BuseyBench @ 640x480 (mean) | 32-208 | 25.0 | 31 | 133 | 300-3,600 |
| BuseyBench @ 1080p (mean) | 32-208 | 115.5 | 144 | 616 | 2,000-20,000 |

A pass whose draws already wrote stencil (a concave fill, a stencil stroke, a clip quad: claude-fable-5-1 at 1080p has 24 + 139 + 21 of them across 361 target switches) loaded and stored its Z/S tile before the change, so the bound is reached only by passes made of convex fills and image draws; the model's `zs_fraction` 0.5 already charges half of every pass's store/load area as Z/S, so half of the bound is inside model.md's frame numbers. What it buys: the winding count a cover pass missed (patch_equivalence.md's Tiger pixel at (200,145)) no longer leaks into the next frame; the probe (`$S/cost/tiger_frames.sh`) shows 0 differing pixels between FRAMES=1 and FRAMES=2 on the fixed, pre-fix and master binaries alike, so the artifact is not reproducible on today's builds (#336 moved the cover geometry) and the clear's benefit cannot be shown here either.

## 4. Pi Zero budget view: 32 and 48 MiB at 1080p

`$S/cost/ladder.py`: the 27 BuseyBench files and google-workspace-48px at 256 / 48 / 32 MiB (`TRANSIENT_BUDGET_MB`), both binaries, FRAMES=1, 1080p framing; each render compared with the same binary's 256 MiB render (`--exact`: pixels that differ at all, px>20 %, max delta), with the other binary's render at the same budget, and with the Chromium 131 reference at the same framing (the 18 references of mask-budget-ladder.md plus 9 made the same way; box = the 1080x1080 SVG box at (420,0): px>20 % / after 2-px erosion / max). mask-budget-ladder.md measured the fixed #323 code on the gated le-fix build (no #324, no #338) against the pre-fix corpus-all3 build; this ladder puts both trees on the full stack, so the vs-Chromium columns are comparable across the two trees.

| budget | fixed: layers passed through / begun | pre-fix | files with a refusal (fixed / pre-fix) | renders differing from own 256 MiB (fixed / pre-fix) | files where fixed and pre-fix renders differ |
|---|---|---|---|---|---|
| 256 MiB | 0 / 2,374 | 0 / 2,374 | 0 / 0 | - | 1 (qwen3-8-2-4t-a95b, 83,769 px, max 2) |
| 48 MiB | 17 / 2,374 | 10 / 2,374 | 3 / 3 (gemini-3-1-pro-preview-custom-tools 72/75 vs 74/75, gpt-5-2-pro 46/53 vs 51/53, qwen3-8-max 87/94 vs 87/94) | 4 / 4 | 3 (gpt-5-2-pro 8,630 px max 29; gemini-…-custom-tools 3,363 px max 45; qwen3-8-2-4t-a95b 83,743 px max 2) |
| 32 MiB | 104 / 2,374 | 65 / 2,374 | 16 / 14 | 18 / 18 | 4 (qwen3-8-max 69,596 px max 124; gpt-5-6-sol-pro 87,910 px max 72; qwen3-8-27b 34,659 px max 53; nex-n2-pro 16,708 px max 24) |

Peak bytes are identical between the trees on every file at every budget (appendix B), as section 3(c) predicts; the counts differ because the fixed tree refuses a layer whole and the pre-fix tree admitted it and then dropped its filter silently when the chain's images failed at `end_layer` - its pass-through count undercounts, its render still changes. At 48 MiB the extra refusals are nested layers inside blurred layers (gpt-5-2-pro: five 19x19 / 38x38 px blurred groups and one opacity group, each costing a 1152-1216 px store because the harness scissors every layer to the viewport) and the two trees' pictures differ from each other by 3,363-8,630 px with max delta 29-45 - against Chromium the box scores are 14.116 % / 10.050 % (fixed) vs 14.092 % / 10.018 % (pre-fix) on gpt-5-2-pro and 6.103 % / 2.723 % vs 6.026 % / 2.704 % on gemini-3-1-pro-preview-custom-tools; qwen3-8-max is identical between trees (87/94, 2,942 px from its 256 MiB render on both). At 32 MiB, 12 of the 16 affected files render identically on both trees; the four that do not are where the old tree's silent degradation looked better than the honest refusal: qwen3-8-max 53/94 admitted vs 87/94, box px>20 5.609 % / structural 3.913 % vs 0.905 % / 0.051 % (the pre-fix render itself differs from its 256 MiB render by 119,693 px, max 73, with the blur dropped and the opacity kept); gpt-5-6-sol-pro 38/41 vs 41/41, 8.783 % / 6.204 % vs 4.448 % / 2.577 % (pre-fix: 36,986 px from its 256 MiB render, max 4); qwen3-8-27b 99/100 vs 100/100, 0.329 % / 0.018 % vs 0.044 % / 0.000 %; nex-n2-pro 99/102 vs 100/102, 1.567 % / 0.902 % vs 1.564 % / 0.914 %. These match mask-budget-ladder.md's le-fix numbers for the same files (48 MiB gpt-5-2-pro 46/53; 32 MiB qwen3-8-max 52/93, gpt-5-6-sol-pro 38/41, qwen3-8-27b 99/100, nex-n2-pro 99/102), so the full stack adds nothing to the budget behaviour beyond the turbulence groups' own layers. The lever stays the one the docs name (src/lib.rs:1319-1323): scissor each group to its bounds before `begin_layer`; with viewport-sized stores 48 MiB holds every masked and every depth-0 layer and 32 MiB does not.

## 5. Verdict for a 256 MB-class Pi Zero

For non-malicious content (the eight demo-assets icons and, as the stress end, BuseyBench) nothing gets worse at the default budget: CPU work per frame is unchanged within the +-20 % noise band on every row (BuseyBench -12.9 %..+6.6 %, sums within 2 %; the fixes move three pool acquires earlier in a layer's life and add one tuple addition), the GPU command stream is the same (61/70 renders bit-identical, the rest explained by the unrelated #336/#339 commits between the builds), CPU RAM is unchanged (three more `Option<ImageId>` per open `LayerRecord`), and the transient peak - the GPU-memory figure ram.md sizes against - is identical on all 70 rows and at every budget. The one measurable GPU-side addition is #324's stencil-bit clear, and only on the GL/vc4 path: +0.4-1.8 ms of certain stencil-quad work per icon frame at 640x480 (frames of 3-77 ms in model.md) with a Z/S tile-traffic bound of +1.6-7.5 ms that applies only to passes that never touched stencil before, and +31 ms certain / +133 ms bound on a mean BuseyBench frame of 300-3,600 ms; half the bound is already inside the model's central assumption. Under a 32-48 MiB budget the fixed tree refuses more nested layers than the old one (17 vs 10 of 2,374 at 48 MiB, 104 vs 65 at 32 MiB) because it refuses honestly what the old tree admitted and then quietly composited unfiltered; at 48 MiB that changes at most 8,630 px on 3 of 28 files, at 32 MiB it makes 4 files visibly worse than the old silent degradation (qwen3-8-max most: 5.6 % of the box beyond 20/255 against Chromium instead of 0.9 %). That is the review's intended behaviour, not a regression in cost, and the documented mitigation (bounds-sized scissors before `begin_layer`) removes the pressure; the docs' 32-48 MiB guidance should say that the low end refuses nested filtered layers on viewport-sized stores.

## 6. Artifacts

Scratchpad `cost/`: `run_cost.py` (matrix driver), `fixed.json` / `orig.json` (70 rows each, every run's real/user/sys/maxrss), `compare_matrix.py` -> `matrix_join.json` / `matrix_tables.md`, `identity.py` -> `identity_640.log` / `identity_1080_icons.log`, `layerlog/*.txt` (1080p LAYER_LOG + TREE_DUMP per file) and `poolsim2.py`, `ladder.py` -> `ladder.json` / `ladder_tables.md` and `refs/` (30 Chromium 1080p references), `synth/*.svg`, `tiger_frames.sh`, `mesa/` (vc4_draw.c, vc4_job.c, vc4_screen.c, st_cb_clear.c from gitlab.freedesktop.org main, read for section 3). Renders were deleted after measuring. Copies of the scripts and JSON are under harness/pz/review-fixes/.

## Appendix A: the 70 rows

"pre" columns are measurements.json (2026-09-13, release build, instrumented harness, median of frames 2-6); "orig" / "fixed" are today's two debug binaries (per-frame wall and user+sys, FRAMES=11 minus FRAMES=1 over 10 frames, min of 2 repeats, 1 ms resolution). "moved" flags a change in layers, pass-throughs or transient bytes against measurements.json, or a wall/CPU delta beyond +-20 % between the two binaries.

| set | framing | file | layers pre/fixed | pass-through pre/fixed | transient pre MiB | transient fixed MiB | delta | pre record / encode / gpu ms (release) | wall/frame orig ms | wall/frame fixed ms | delta | cpu/frame orig ms | cpu/frame fixed ms | delta | moved |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| busey | 640x480 | claude-fable-5-1 | 178/178 | 0/0 | 8.34 | 8.34 | +0.00 (+0.0 %) | 0.655 / 13.23 / 17.12 | 139.0 | 129.0 | -7.2 % | 153.0 | 153.0 | +0.0 % |  |
| busey | 640x480 | claude-opus-5 | 92/92 | 0/0 | 13.11 | 13.11 | +0.00 (+0.0 %) | 0.489 / 9.23 / 12.36 | 105.0 | 102.0 | -2.9 % | 110.0 | 109.0 | -0.9 % |  |
| busey | 640x480 | fugu-ultra | 124/124 | 0/0 | 13.52 | 13.52 | +0.00 (+0.0 %) | 0.489 / 6.72 / 9.18 | 77.0 | 80.0 | +3.9 % | 81.0 | 84.0 | +3.7 % |  |
| busey | 640x480 | gemini-3-1-pro-preview | 98/98 | 0/0 | 10.19 | 10.19 | +0.00 (+0.0 %) | 0.407 / 14.35 / 18.69 | 146.0 | 140.0 | -4.1 % | 153.0 | 154.0 | +0.7 % |  |
| busey | 640x480 | gemini-3-1-pro-preview-custom-tools | 75/75 | 0/0 | 10.26 | 10.26 | +0.00 (+0.0 %) | 0.377 / 9.45 / 13.25 | 103.0 | 106.0 | +2.9 % | 107.0 | 114.0 | +6.5 % |  |
| busey | 640x480 | gemini-3-7-flash | 57/57 | 0/0 | 6.80 | 6.80 | +0.00 (+0.0 %) | 0.440 / 3.98 / 4.87 | 60.0 | 62.0 | +3.3 % | 60.0 | 62.0 | +3.3 % |  |
| busey | 640x480 | gemini-3-8-flash | 118/118 | 0/0 | 7.80 | 7.80 | +0.00 (+0.0 %) | 0.477 / 9.59 / 13.87 | 117.0 | 110.0 | -6.0 % | 120.0 | 118.0 | -1.7 % |  |
| busey | 640x480 | glm-5-3 | 129/129 | 0/0 | 9.92 | 9.92 | +0.00 (+0.0 %) | 0.523 / 12.02 / 15.09 | 133.0 | 132.0 | -0.8 % | 141.0 | 137.0 | -2.8 % |  |
| busey | 640x480 | glm-5-3-flash | 79/79 | 0/0 | 10.26 | 10.26 | +0.00 (+0.0 %) | 0.348 / 5.71 / 10.10 | 70.0 | 64.0 | -8.6 % | 70.0 | 65.0 | -7.1 % |  |
| busey | 640x480 | glm-5v-turbo | 57/57 | 0/0 | 10.19 | 10.19 | +0.00 (+0.0 %) | 0.305 / 5.24 / 7.82 | 59.0 | 58.0 | -1.7 % | 61.0 | 60.0 | -1.6 % |  |
| busey | 640x480 | gpt-5-2-pro | 53/53 | 0/0 | 8.80 | 8.80 | +0.00 (+0.0 %) | 0.302 / 3.90 / 8.26 | 47.0 | 43.0 | -8.5 % | 49.0 | 44.0 | -10.2 % |  |
| busey | 640x480 | gpt-5-6-luna-pro | 33/33 | 0/0 | 7.80 | 7.80 | +0.00 (+0.0 %) | 0.273 / 2.33 / 5.91 | 33.0 | 32.0 | -3.0 % | 34.0 | 33.0 | -2.9 % |  |
| busey | 640x480 | gpt-5-6-sol | 48/48 | 0/0 | 7.80 | 7.80 | +0.00 (+0.0 %) | 0.289 / 2.72 / 4.50 | 39.0 | 39.0 | +0.0 % | 39.0 | 39.0 | +0.0 % |  |
| busey | 640x480 | gpt-5-6-sol-pro | 41/41 | 0/0 | 12.75 | 12.75 | +0.00 (+0.0 %) | 0.341 / 3.14 / 4.65 | 42.0 | 41.0 | -2.4 % | 40.0 | 42.0 | +5.0 % |  |
| busey | 640x480 | gpt-5-6-terra-pro | 31/31 | 0/0 | 6.80 | 6.80 | +0.00 (+0.0 %) | 0.284 / 2.53 / 7.03 | 36.0 | 34.0 | -5.6 % | 38.0 | 34.0 | -10.5 % |  |
| busey | 640x480 | gpt-6-astra | 162/162 | 0/0 | 7.80 | 7.80 | +0.00 (+0.0 %) | 0.803 / 11.26 / 13.55 | 155.0 | 148.0 | -4.5 % | 160.0 | 152.0 | -5.0 % |  |
| busey | 640x480 | grok-4-5 | 76/76 | 0/0 | 6.32 | 6.32 | +0.00 (+0.0 %) | 0.397 / 5.67 / 8.01 | 70.0 | 71.0 | +1.4 % | 72.0 | 72.0 | +0.0 % |  |
| busey | 640x480 | kimi-k2-6 | 55/55 | 0/0 | 10.12 | 10.12 | +0.00 (+0.0 %) | 0.303 / 5.44 / 8.53 | 61.0 | 60.0 | -1.6 % | 64.0 | 61.0 | -4.7 % |  |
| busey | 640x480 | kimi-k3 | 50/50 | 0/0 | 11.26 | 11.26 | +0.00 (+0.0 %) | 0.289 / 2.75 / 4.76 | 35.0 | 36.0 | +2.9 % | 36.0 | 36.0 | +0.0 % |  |
| busey | 640x480 | muse-spark-1-3 | 49/49 | 0/0 | 6.80 | 6.80 | +0.00 (+0.0 %) | 0.319 / 4.73 / 8.34 | 56.0 | 58.0 | +3.6 % | 57.0 | 59.0 | +3.5 % |  |
| busey | 640x480 | muse-spark-1-3-contributor | 59/59 | 0/0 | 6.80 | 6.80 | +0.00 (+0.0 %) | 0.294 / 4.80 / 6.84 | 52.0 | 54.0 | +3.8 % | 53.0 | 53.0 | +0.0 % |  |
| busey | 640x480 | nex-n2-pro | 102/102 | 0/0 | 13.18 | 13.18 | +0.00 (+0.0 %) | 0.418 / 5.28 / 7.85 | 66.0 | 66.0 | +0.0 % | 69.0 | 67.0 | -2.9 % |  |
| busey | 640x480 | ox-alpha | 94/94 | 0/0 | 8.18 | 8.18 | +0.00 (+0.0 %) | 0.363 / 6.89 / 13.64 | 78.0 | 78.0 | +0.0 % | 84.0 | 81.0 | -3.6 % |  |
| busey | 640x480 | qwen3-8-2-4t-a95b | 200/200 | 0/0 | 13.28 | 13.28 | +0.00 (+0.0 %) | 0.771 / 22.96 / 32.71 | 222.0 | 223.0 | +0.5 % | 237.0 | 239.0 | +0.8 % |  |
| busey | 640x480 | qwen3-8-27b | 100/100 | 0/0 | 10.33 | 10.33 | +0.00 (+0.0 %) | 0.425 / 8.70 / 10.63 | 95.0 | 96.0 | +1.1 % | 99.0 | 99.0 | +0.0 % |  |
| busey | 640x480 | qwen3-8-flash | 119/119 | 0/0 | 11.87 | 11.87 | +0.00 (+0.0 %) | 0.538 / 11.83 / 14.29 | 132.0 | 128.0 | -3.0 % | 137.0 | 135.0 | -1.5 % |  |
| busey | 640x480 | qwen3-8-max | 94/94 | 0/0 | 11.43 | 11.43 | +0.00 (+0.0 %) | 0.431 / 8.46 / 13.97 | 91.0 | 93.0 | +2.2 % | 97.0 | 98.0 | +1.0 % |  |
| busey | 1080p | claude-fable-5-1 | 178/178 | 0/0 | 36.54 | 36.54 | +0.00 (+0.0 %) | 0.626 / 13.81 / 30.53 | 151.0 | 152.0 | +0.7 % | 159.0 | 155.0 | -2.5 % |  |
| busey | 1080p | claude-opus-5 | 92/92 | 0/0 | 37.17 | 37.17 | +0.00 (+0.0 %) | 0.549 / 9.37 / 23.72 | 108.0 | 111.0 | +2.8 % | 112.0 | 113.0 | +0.9 % |  |
| busey | 1080p | fugu-ultra | 124/124 | 0/0 | 43.23 | 43.23 | +0.00 (+0.0 %) | 0.483 / 6.80 / 12.55 | 83.0 | 80.0 | -3.6 % | 86.0 | 84.0 | -2.3 % |  |
| busey | 1080p | gemini-3-1-pro-preview | 98/98 | 0/0 | 34.20 | 34.20 | +0.00 (+0.0 %) | 0.422 / 14.70 / 32.84 | 171.0 | 149.0 | -12.9 % | 180.0 | 158.0 | -12.2 % |  |
| busey | 1080p | gemini-3-1-pro-preview-custom-tools | 75/75 | 0/0 | 56.19 | 56.19 | +0.00 (+0.0 %) | 0.460 / 10.04 / 25.17 | 117.0 | 108.0 | -7.7 % | 117.0 | 113.0 | -3.4 % |  |
| busey | 1080p | gemini-3-7-flash | 57/57 | 0/0 | 19.70 | 19.70 | +0.00 (+0.0 %) | 0.471 / 3.92 / 6.92 | 64.0 | 67.0 | +4.7 % | 63.0 | 65.0 | +3.2 % |  |
| busey | 1080p | gemini-3-8-flash | 118/118 | 0/0 | 29.28 | 29.28 | +0.00 (+0.0 %) | 0.503 / 9.58 / 16.63 | 121.0 | 120.0 | -0.8 % | 126.0 | 125.0 | -0.8 % |  |
| busey | 1080p | glm-5-3 | 129/129 | 0/0 | 38.30 | 38.30 | +0.00 (+0.0 %) | 0.583 / 12.03 / 26.96 | 139.0 | 144.0 | +3.6 % | 143.0 | 148.0 | +3.5 % |  |
| busey | 1080p | glm-5-3-flash | 79/79 | 0/0 | 34.75 | 34.75 | +0.00 (+0.0 %) | 0.372 / 5.87 / 14.56 | 76.0 | 68.0 | -10.5 % | 77.0 | 69.0 | -10.4 % |  |
| busey | 1080p | glm-5v-turbo | 57/57 | 0/0 | 39.27 | 39.27 | +0.00 (+0.0 %) | 0.322 / 5.31 / 14.80 | 65.0 | 66.0 | +1.5 % | 63.0 | 66.0 | +4.8 % |  |
| busey | 1080p | gpt-5-2-pro | 53/53 | 0/0 | 55.23 | 55.23 | +0.00 (+0.0 %) | 0.343 / 4.09 / 10.94 | 51.0 | 50.0 | -2.0 % | 52.0 | 52.0 | +0.0 % |  |
| busey | 1080p | gpt-5-6-luna-pro | 33/33 | 0/0 | 28.73 | 28.73 | +0.00 (+0.0 %) | 0.274 / 2.54 / 5.63 | 39.0 | 38.0 | -2.6 % | 35.0 | 36.0 | +2.9 % |  |
| busey | 1080p | gpt-5-6-sol | 48/48 | 0/0 | 28.73 | 28.73 | +0.00 (+0.0 %) | 0.313 / 2.91 / 10.29 | 45.0 | 40.0 | -11.1 % | 41.0 | 41.0 | +0.0 % |  |
| busey | 1080p | gpt-5-6-sol-pro | 41/41 | 0/0 | 41.69 | 41.69 | +0.00 (+0.0 %) | 0.329 / 3.16 / 9.16 | 44.0 | 44.0 | +0.0 % | 42.0 | 42.0 | +0.0 % |  |
| busey | 1080p | gpt-5-6-terra-pro | 31/31 | 0/0 | 19.70 | 19.70 | +0.00 (+0.0 %) | 0.279 / 2.49 / 8.33 | 38.0 | 38.0 | +0.0 % | 36.0 | 37.0 | +2.8 % |  |
| busey | 1080p | gpt-6-astra | 162/162 | 0/0 | 28.73 | 28.73 | +0.00 (+0.0 %) | 0.882 / 11.31 / 21.80 | 160.0 | 161.0 | +0.6 % | 163.0 | 166.0 | +1.8 % |  |
| busey | 1080p | grok-4-5 | 76/76 | 0/0 | 39.27 | 39.27 | +0.00 (+0.0 %) | 0.417 / 5.80 / 10.31 | 75.0 | 78.0 | +4.0 % | 76.0 | 79.0 | +3.9 % |  |
| busey | 1080p | kimi-k2-6 | 55/55 | 0/0 | 34.20 | 34.20 | +0.00 (+0.0 %) | 0.315 / 6.01 / 14.38 | 65.0 | 67.0 | +3.1 % | 67.0 | 67.0 | -0.0 % |  |
| busey | 1080p | kimi-k3 | 50/50 | 0/0 | 38.72 | 38.72 | +0.00 (+0.0 %) | 0.316 / 2.88 / 7.47 | 41.0 | 41.0 | +0.0 % | 41.0 | 40.0 | -2.4 % |  |
| busey | 1080p | muse-spark-1-3 | 49/49 | 0/0 | 19.70 | 19.70 | +0.00 (+0.0 %) | 0.321 / 5.42 / 10.72 | 62.0 | 64.0 | +3.2 % | 63.0 | 64.0 | +1.6 % |  |
| busey | 1080p | muse-spark-1-3-contributor | 59/59 | 0/0 | 19.70 | 19.70 | +0.00 (+0.0 %) | 0.330 / 5.39 / 12.60 | 57.0 | 57.0 | +0.0 % | 58.0 | 57.0 | -1.7 % |  |
| busey | 1080p | nex-n2-pro | 102/102 | 0/0 | 44.33 | 44.33 | +0.00 (+0.0 %) | 0.445 / 5.31 / 10.77 | 73.0 | 69.0 | -5.5 % | 71.0 | 73.0 | +2.8 % |  |
| busey | 1080p | ox-alpha | 94/94 | 0/0 | 30.64 | 30.64 | +0.00 (+0.0 %) | 0.416 / 7.17 / 16.36 | 83.0 | 84.0 | +1.2 % | 86.0 | 85.0 | -1.2 % |  |
| busey | 1080p | qwen3-8-2-4t-a95b | 200/200 | 0/0 | 57.28 | 57.28 | +0.00 (+0.0 %) | 0.725 / 20.39 / 50.49 | 237.0 | 245.0 | +3.4 % | 250.0 | 256.0 | +2.4 % |  |
| busey | 1080p | qwen3-8-27b | 100/100 | 0/0 | 34.34 | 34.34 | +0.00 (+0.0 %) | 0.454 / 8.63 / 22.47 | 102.0 | 103.0 | +1.0 % | 104.0 | 103.0 | -1.0 % |  |
| busey | 1080p | qwen3-8-flash | 119/119 | 0/0 | 46.32 | 46.32 | +0.00 (+0.0 %) | 0.611 / 12.28 / 28.25 | 137.0 | 146.0 | +6.6 % | 141.0 | 147.0 | +4.3 % |  |
| busey | 1080p | qwen3-8-max | 94/94 | 0/0 | 49.17 | 49.17 | +0.00 (+0.0 %) | 0.467 / 8.48 / 19.94 | 97.0 | 101.0 | +4.1 % | 101.0 | 104.0 | +3.0 % |  |
| icons | 640x480 | Ghostscript_Tiger | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.532 / 0.66 / 1.69 | 32.0 | 32.0 | +0.0 % | 31.0 | 31.0 | -0.0 % |  |
| icons | 640x480 | clipdemo | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.029 / 0.11 / 0.50 | 2.0 | 0.0 | -100.0 % | 2.0 | 1.0 | -50.0 % | wall>20% cpu>20% |
| icons | 640x480 | duckduckgo-com_2x | 1/1 | 0/0 | 1.00 | 1.00 | +0.00 (+0.0 %) | 0.078 / 0.17 / 0.77 | 3.0 | 2.0 | -33.3 % | 2.0 | 1.0 | -50.0 % | wall>20% cpu>20% |
| icons | 640x480 | fox-with-box-on-cloud | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.184 / 0.21 / 0.77 | 7.0 | 8.0 | +14.3 % | 8.0 | 8.0 | -0.0 % |  |
| icons | 640x480 | google-workspace-48px | 1/1 | 0/0 | 5.06 | 5.06 | +0.00 (+0.0 %) | 0.087 / 0.35 / 1.07 | 4.0 | 5.0 | +25.0 % | 4.0 | 6.0 | +50.0 % | wall>20% cpu>20% |
| icons | 640x480 | kit | 2/2 | 0/0 | 2.00 | 2.00 | +0.00 (+0.0 %) | 0.095 / 0.26 / 0.91 | 4.0 | 4.0 | +0.0 % | 3.0 | 2.0 | -33.3 % | cpu>20% |
| icons | 640x480 | mr-settodefault | 2/2 | 0/0 | 1.00 | 1.00 | +0.00 (+0.0 %) | 0.213 / 0.31 / 0.75 | 6.0 | 7.0 | +16.7 % | 5.0 | 5.0 | -0.0 % |  |
| icons | 640x480 | splash-logo | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.051 / 0.14 / 0.28 | 3.0 | 2.0 | -33.3 % | 4.0 | 2.0 | -50.0 % | wall>20% cpu>20% |
| icons | 1080p | Ghostscript_Tiger | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.656 / 0.68 / 2.43 | 35.0 | 33.0 | -5.7 % | 33.0 | 32.0 | -3.0 % |  |
| icons | 1080p | clipdemo | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.039 / 0.14 / 0.82 | 2.0 | 2.0 | -0.0 % | 2.0 | 1.0 | -50.0 % | cpu>20% |
| icons | 1080p | duckduckgo-com_2x | 1/1 | 0/0 | 4.52 | 4.52 | +0.00 (+0.0 %) | 0.091 / 0.19 / 1.27 | 3.0 | 3.0 | +0.0 % | 3.0 | 4.0 | +33.3 % | cpu>20% |
| icons | 1080p | fox-with-box-on-cloud | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.238 / 0.24 / 1.42 | 9.0 | 8.0 | -11.1 % | 8.0 | 7.0 | -12.5 % |  |
| icons | 1080p | google-workspace-48px | 1/1 | 0/0 | 20.25 | 20.25 | +0.00 (+0.0 %) | 0.099 / 0.36 / 2.09 | 8.0 | 8.0 | +0.0 % | 6.0 | 5.0 | -16.7 % |  |
| icons | 1080p | kit | 2/2 | 0/0 | 9.03 | 9.03 | +0.00 (+0.0 %) | 0.103 / 0.27 / 2.67 | 5.0 | 8.0 | +60.0 % | 4.0 | 5.0 | +25.0 % | wall>20% cpu>20% |
| icons | 1080p | mr-settodefault | 2/2 | 0/0 | 4.52 | 4.52 | +0.00 (+0.0 %) | 0.253 / 0.30 / 3.11 | 9.0 | 7.0 | -22.2 % | 6.0 | 8.0 | +33.3 % | wall>20% cpu>20% |
| icons | 1080p | splash-logo | 0/0 | 0/0 | 0.00 | 0.00 | +0.00 (+0.0 %) | 0.071 / 0.18 / 2.39 | 3.0 | 3.0 | +0.0 % | 2.0 | 2.0 | +0.0 % |  |

## Appendix B: the 1080p budget ladder on the full stack

## 48 MiB, 1080p, full stack (wt-all3 7bbcb5e fixed vs f05e2da pre-fix)

| file | fixed admitted | fixed peak MiB | fixed vs its 256 MiB | fixed vs Chromium box px>20 / structural / max | pre-fix admitted | pre-fix peak MiB | pre-fix vs its 256 MiB | pre-fix vs Chromium box | fixed vs pre-fix render |
|---|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 178/178 | 36.5 | identical | 3.364 % / 0.973 % / 91 | 178/178 | 36.5 | identical | 3.364 % / 0.973 % / 91 | identical |
| claude-opus-5 | 92/92 | 37.2 | identical | 0.155 % / 0.000 % / 121 | 92/92 | 37.2 | identical | 0.155 % / 0.000 % / 121 | identical |
| fugu-ultra | 124/124 | 43.2 | identical | 0.368 % / 0.002 % / 103 | 124/124 | 43.2 | identical | 0.368 % / 0.002 % / 103 | identical |
| gemini-3-1-pro-preview | 98/98 | 34.2 | identical | 2.155 % / 0.529 % / 196 | 98/98 | 34.2 | identical | 2.155 % / 0.529 % / 196 | identical |
| gemini-3-1-pro-preview-custom-tools | 72/75 | 46.0 | 60501 px (2.92 %), 0.29 %, max 63 | 6.103 % / 2.723 % / 112 | 74/75 | 46.0 | 60298 px (2.91 %), 0.25 %, max 48 | 6.026 % / 2.704 % / 112 | 3363 px, max 45 |
| gemini-3-7-flash | 57/57 | 19.7 | identical | 2.026 % / 0.733 % / 129 | 57/57 | 19.7 | identical | 2.026 % / 0.733 % / 129 | identical |
| gemini-3-8-flash | 118/118 | 29.3 | identical | 0.777 % / 0.000 % / 105 | 118/118 | 29.3 | identical | 0.777 % / 0.000 % / 105 | identical |
| glm-5-3 | 129/129 | 38.3 | identical | 0.044 % / 0.000 % / 84 | 129/129 | 38.3 | identical | 0.044 % / 0.000 % / 84 | identical |
| glm-5-3-flash | 79/79 | 34.8 | identical | 0.198 % / 0.000 % / 81 | 79/79 | 34.8 | identical | 0.198 % / 0.000 % / 81 | identical |
| glm-5v-turbo | 57/57 | 39.3 | identical | 2.951 % / 0.827 % / 105 | 57/57 | 39.3 | identical | 2.951 % / 0.827 % / 105 | identical |
| gpt-5-2-pro | 46/53 | 45.1 | 86221 px (4.16 %), 2.21 %, max 57 | 14.116 % / 10.050 % / 148 | 51/53 | 45.1 | 84366 px (4.07 %), 2.19 %, max 57 | 14.092 % / 10.018 % / 148 | 8630 px, max 29 |
| gpt-5-6-luna-pro | 33/33 | 28.7 | identical | 0.084 % / 0.000 % / 93 | 33/33 | 28.7 | identical | 0.084 % / 0.000 % / 93 | identical |
| gpt-5-6-sol | 48/48 | 28.7 | identical | 0.112 % / 0.000 % / 80 | 48/48 | 28.7 | identical | 0.112 % / 0.000 % / 80 | identical |
| gpt-5-6-sol-pro | 41/41 | 41.7 | identical | 4.448 % / 2.577 % / 115 | 41/41 | 41.7 | identical | 4.448 % / 2.577 % / 115 | identical |
| gpt-5-6-terra-pro | 31/31 | 19.7 | identical | 5.035 % / 3.195 % / 102 | 31/31 | 19.7 | identical | 5.035 % / 3.195 % / 102 | identical |
| gpt-6-astra | 162/162 | 28.7 | identical | 0.178 % / 0.000 % / 115 | 162/162 | 28.7 | identical | 0.178 % / 0.000 % / 115 | identical |
| grok-4-5 | 76/76 | 39.3 | identical | 0.200 % / 0.000 % / 206 | 76/76 | 39.3 | identical | 0.200 % / 0.000 % / 206 | identical |
| kimi-k2-6 | 55/55 | 34.2 | identical | 0.134 % / 0.000 % / 76 | 55/55 | 34.2 | identical | 0.134 % / 0.000 % / 76 | identical |
| kimi-k3 | 50/50 | 38.7 | identical | 0.426 % / 0.087 % / 90 | 50/50 | 38.7 | identical | 0.426 % / 0.087 % / 90 | identical |
| muse-spark-1-3 | 49/49 | 19.7 | identical | 0.150 % / 0.000 % / 110 | 49/49 | 19.7 | identical | 0.150 % / 0.000 % / 110 | identical |
| muse-spark-1-3-contributor | 59/59 | 19.7 | identical | 0.332 % / 0.020 % / 76 | 59/59 | 19.7 | identical | 0.332 % / 0.020 % / 76 | identical |
| nex-n2-pro | 102/102 | 44.3 | identical | 0.508 % / 0.048 % / 110 | 102/102 | 44.3 | identical | 0.508 % / 0.048 % / 110 | identical |
| ox-alpha | 94/94 | 30.6 | identical | 0.232 % / 0.001 % / 135 | 94/94 | 30.6 | identical | 0.232 % / 0.001 % / 135 | identical |
| qwen3-8-2-4t-a95b | 200/200 | 47.3 | 45326 px (2.19 %), 0.01 %, max 23 | 0.276 % / 0.010 % / 79 | 200/200 | 47.3 | 45325 px (2.19 %), 0.01 %, max 23 | 0.278 % / 0.010 % / 79 | 83743 px, max 2 |
| qwen3-8-27b | 100/100 | 34.3 | identical | 0.044 % / 0.000 % / 64 | 100/100 | 34.3 | identical | 0.044 % / 0.000 % / 64 | identical |
| qwen3-8-flash | 119/119 | 46.3 | identical | 1.124 % / 0.360 % / 76 | 119/119 | 46.3 | identical | 1.124 % / 0.360 % / 76 | identical |
| qwen3-8-max | 87/94 | 44.7 | 2942 px (0.14 %), 0.00 %, max 21 | 0.094 % / 0.000 % / 96 | 87/94 | 44.7 | 2942 px (0.14 %), 0.00 %, max 21 | 0.094 % / 0.000 % / 96 | identical |
| google-workspace-48px | 1/1 | 20.2 | identical | 6.140 % / 5.502 % / 129 | 1/1 | 20.2 | identical | 6.140 % / 5.502 % / 129 | identical |

Totals at 48 MiB: fixed passes through 17 of 2374 layers over 28 files; pre-fix 10 of 2374.

## 32 MiB, 1080p, full stack (wt-all3 7bbcb5e fixed vs f05e2da pre-fix)

| file | fixed admitted | fixed peak MiB | fixed vs its 256 MiB | fixed vs Chromium box px>20 / structural / max | pre-fix admitted | pre-fix peak MiB | pre-fix vs its 256 MiB | pre-fix vs Chromium box | fixed vs pre-fix render |
|---|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 177/178 | 27.5 | 25499 px (1.23 %), 0.29 %, max 42 | 3.721 % / 1.216 % / 91 | 177/178 | 27.5 | 25499 px (1.23 %), 0.29 %, max 42 | 3.721 % / 1.216 % / 91 | identical |
| claude-opus-5 | 90/92 | 31.2 | 211435 px (10.20 %), 0.00 %, max 15 | 0.157 % / 0.000 % / 122 | 90/92 | 31.2 | 211435 px (10.20 %), 0.00 %, max 15 | 0.157 % / 0.000 % / 122 | identical |
| fugu-ultra | 122/124 | 29.2 | 135924 px (6.55 %), 0.98 %, max 245 | 1.863 % / 0.858 % / 245 | 122/124 | 29.2 | 135924 px (6.55 %), 0.98 %, max 245 | 1.863 % / 0.858 % / 245 | identical |
| gemini-3-1-pro-preview | 96/98 | 29.7 | 17042 px (0.82 %), 0.00 %, max 14 | 2.193 % / 0.569 % / 196 | 96/98 | 29.7 | 17042 px (0.82 %), 0.00 %, max 14 | 2.193 % / 0.569 % / 196 | identical |
| gemini-3-1-pro-preview-custom-tools | 60/75 | 29.7 | 96911 px (4.67 %), 0.88 %, max 98 | 7.111 % / 3.375 % / 112 | 60/75 | 29.7 | 96911 px (4.67 %), 0.88 %, max 98 | 7.111 % / 3.375 % / 112 | identical |
| gemini-3-7-flash | 57/57 | 19.7 | identical | 2.026 % / 0.733 % / 129 | 57/57 | 19.7 | identical | 2.026 % / 0.733 % / 129 | identical |
| gemini-3-8-flash | 118/118 | 29.3 | identical | 0.777 % / 0.000 % / 105 | 118/118 | 29.3 | identical | 0.777 % / 0.000 % / 105 | identical |
| glm-5-3 | 129/129 | 28.7 | 4528 px (0.22 %), 0.04 %, max 37 | 0.118 % / 0.012 % / 84 | 129/129 | 28.7 | 4528 px (0.22 %), 0.04 %, max 37 | 0.118 % / 0.012 % / 84 | identical |
| glm-5-3-flash | 68/79 | 29.7 | 24497 px (1.18 %), 0.00 %, max 19 | 0.199 % / 0.000 % / 81 | 68/79 | 29.7 | 24497 px (1.18 %), 0.00 %, max 19 | 0.199 % / 0.000 % / 81 | identical |
| glm-5v-turbo | 50/57 | 29.7 | 21655 px (1.04 %), 0.01 %, max 22 | 2.955 % / 0.829 % / 105 | 50/57 | 29.7 | 21655 px (1.04 %), 0.01 %, max 22 | 2.955 % / 0.829 % / 105 | identical |
| gpt-5-2-pro | 46/53 | 29.3 | 84801 px (4.09 %), 0.06 %, max 85 | 10.584 % / 6.872 % / 148 | 46/53 | 29.3 | 84801 px (4.09 %), 0.06 %, max 85 | 10.584 % / 6.872 % / 148 | identical |
| gpt-5-6-luna-pro | 33/33 | 28.7 | identical | 0.084 % / 0.000 % / 93 | 33/33 | 28.7 | identical | 0.084 % / 0.000 % / 93 | identical |
| gpt-5-6-sol | 48/48 | 28.7 | identical | 0.112 % / 0.000 % / 80 | 48/48 | 28.7 | identical | 0.112 % / 0.000 % / 80 | identical |
| gpt-5-6-sol-pro | 38/41 | 30.4 | 86808 px (4.19 %), 2.41 %, max 72 | 8.783 % / 6.204 % / 115 | 41/41 | 30.4 | 36986 px (1.78 %), 0.00 %, max 4 | 4.448 % / 2.577 % / 115 | 87910 px, max 72 |
| gpt-5-6-terra-pro | 31/31 | 19.7 | identical | 5.035 % / 3.195 % / 102 | 31/31 | 19.7 | identical | 5.035 % / 3.195 % / 102 | identical |
| gpt-6-astra | 162/162 | 28.7 | identical | 0.178 % / 0.000 % / 115 | 162/162 | 28.7 | identical | 0.178 % / 0.000 % / 115 | identical |
| grok-4-5 | 73/76 | 29.7 | 113994 px (5.50 %), 0.00 %, max 20 | 0.208 % / 0.000 % / 206 | 73/76 | 29.7 | 113994 px (5.50 %), 0.00 %, max 20 | 0.208 % / 0.000 % / 206 | identical |
| kimi-k2-6 | 52/55 | 29.7 | 3977 px (0.19 %), 0.07 %, max 73 | 0.259 % / 0.000 % / 80 | 52/55 | 29.7 | 3977 px (0.19 %), 0.07 %, max 73 | 0.259 % / 0.000 % / 80 | identical |
| kimi-k3 | 50/50 | 28.7 | 76345 px (3.68 %), 0.75 %, max 68 | 2.187 % / 1.357 % / 90 | 50/50 | 28.7 | 76345 px (3.68 %), 0.75 %, max 68 | 2.187 % / 1.357 % / 90 | identical |
| muse-spark-1-3 | 49/49 | 19.7 | identical | 0.150 % / 0.000 % / 110 | 49/49 | 19.7 | identical | 0.150 % / 0.000 % / 110 | identical |
| muse-spark-1-3-contributor | 59/59 | 19.7 | identical | 0.332 % / 0.020 % / 76 | 59/59 | 19.7 | identical | 0.332 % / 0.020 % / 76 | identical |
| nex-n2-pro | 99/102 | 29.1 | 42136 px (2.03 %), 0.63 %, max 40 | 1.567 % / 0.902 % / 110 | 100/102 | 29.1 | 37282 px (1.80 %), 0.61 %, max 40 | 1.564 % / 0.914 % / 110 | 16708 px, max 24 |
| ox-alpha | 94/94 | 30.6 | identical | 0.232 % / 0.001 % / 135 | 94/94 | 30.6 | identical | 0.232 % / 0.001 % / 135 | identical |
| qwen3-8-2-4t-a95b | 199/200 | 31.3 | 249089 px (12.01 %), 2.67 %, max 59 | 5.455 % / 0.536 % / 79 | 199/200 | 31.3 | 249745 px (12.04 %), 2.67 %, max 59 | 5.455 % / 0.536 % / 79 | identical |
| qwen3-8-27b | 99/100 | 29.3 | 38461 px (1.85 %), 0.16 %, max 53 | 0.329 % / 0.018 % / 68 | 100/100 | 29.3 | 9219 px (0.44 %), 0.00 %, max 7 | 0.044 % / 0.000 % / 64 | 34659 px, max 53 |
| qwen3-8-flash | 117/119 | 31.3 | 206043 px (9.94 %), 1.51 %, max 66 | 4.469 % / 2.818 % / 78 | 117/119 | 31.3 | 206043 px (9.94 %), 1.51 %, max 66 | 4.469 % / 2.818 % / 78 | identical |
| qwen3-8-max | 53/94 | 30.0 | 131043 px (6.32 %), 3.02 %, max 162 | 5.609 % / 3.913 % / 163 | 87/94 | 30.0 | 119693 px (5.77 %), 0.35 %, max 73 | 0.905 % / 0.051 % / 98 | 69596 px, max 124 |
| google-workspace-48px | 1/1 | 20.2 | identical | 6.140 % / 5.502 % / 129 | 1/1 | 20.2 | identical | 6.140 % / 5.502 % / 129 | identical |

Totals at 32 MiB: fixed passes through 104 of 2374 layers over 28 files; pre-fix 65 of 2374.

## 256 MiB (default), 1080p

| file | layers | fixed peak MiB | pre-fix peak MiB | fixed vs Chromium box px>20 / structural / max | pre-fix vs Chromium box | fixed vs pre-fix render |
|---|---|---|---|---|---|---|
| claude-fable-5-1 | 178 | 36.5 | 36.5 | 3.364 % / 0.973 % / 91 | 3.364 % / 0.973 % / 91 | identical |
| claude-opus-5 | 92 | 37.2 | 37.2 | 0.155 % / 0.000 % / 121 | 0.155 % / 0.000 % / 121 | identical |
| fugu-ultra | 124 | 43.2 | 43.2 | 0.368 % / 0.002 % / 103 | 0.368 % / 0.002 % / 103 | identical |
| gemini-3-1-pro-preview | 98 | 34.2 | 34.2 | 2.155 % / 0.529 % / 196 | 2.155 % / 0.529 % / 196 | identical |
| gemini-3-1-pro-preview-custom-tools | 75 | 56.2 | 56.2 | 5.701 % / 2.712 % / 111 | 5.701 % / 2.712 % / 111 | identical |
| gemini-3-7-flash | 57 | 19.7 | 19.7 | 2.026 % / 0.733 % / 129 | 2.026 % / 0.733 % / 129 | identical |
| gemini-3-8-flash | 118 | 29.3 | 29.3 | 0.777 % / 0.000 % / 105 | 0.777 % / 0.000 % / 105 | identical |
| glm-5-3 | 129 | 38.3 | 38.3 | 0.044 % / 0.000 % / 84 | 0.044 % / 0.000 % / 84 | identical |
| glm-5-3-flash | 79 | 34.8 | 34.8 | 0.198 % / 0.000 % / 81 | 0.198 % / 0.000 % / 81 | identical |
| glm-5v-turbo | 57 | 39.3 | 39.3 | 2.951 % / 0.827 % / 105 | 2.951 % / 0.827 % / 105 | identical |
| gpt-5-2-pro | 53 | 55.2 | 55.2 | 10.488 % / 6.803 % / 148 | 10.488 % / 6.803 % / 148 | identical |
| gpt-5-6-luna-pro | 33 | 28.7 | 28.7 | 0.084 % / 0.000 % / 93 | 0.084 % / 0.000 % / 93 | identical |
| gpt-5-6-sol | 48 | 28.7 | 28.7 | 0.112 % / 0.000 % / 80 | 0.112 % / 0.000 % / 80 | identical |
| gpt-5-6-sol-pro | 41 | 41.7 | 41.7 | 4.448 % / 2.577 % / 115 | 4.448 % / 2.577 % / 115 | identical |
| gpt-5-6-terra-pro | 31 | 19.7 | 19.7 | 5.035 % / 3.195 % / 102 | 5.035 % / 3.195 % / 102 | identical |
| gpt-6-astra | 162 | 28.7 | 28.7 | 0.178 % / 0.000 % / 115 | 0.178 % / 0.000 % / 115 | identical |
| grok-4-5 | 76 | 39.3 | 39.3 | 0.200 % / 0.000 % / 206 | 0.200 % / 0.000 % / 206 | identical |
| kimi-k2-6 | 55 | 34.2 | 34.2 | 0.134 % / 0.000 % / 76 | 0.134 % / 0.000 % / 76 | identical |
| kimi-k3 | 50 | 38.7 | 38.7 | 0.426 % / 0.087 % / 90 | 0.426 % / 0.087 % / 90 | identical |
| muse-spark-1-3 | 49 | 19.7 | 19.7 | 0.150 % / 0.000 % / 110 | 0.150 % / 0.000 % / 110 | identical |
| muse-spark-1-3-contributor | 59 | 19.7 | 19.7 | 0.332 % / 0.020 % / 76 | 0.332 % / 0.020 % / 76 | identical |
| nex-n2-pro | 102 | 44.3 | 44.3 | 0.508 % / 0.048 % / 110 | 0.508 % / 0.048 % / 110 | identical |
| ox-alpha | 94 | 30.6 | 30.6 | 0.232 % / 0.001 % / 135 | 0.232 % / 0.001 % / 135 | identical |
| qwen3-8-2-4t-a95b | 200 | 57.3 | 57.3 | 0.273 % / 0.005 % / 79 | 0.275 % / 0.006 % / 79 | 83769 px, max 2 |
| qwen3-8-27b | 100 | 34.3 | 34.3 | 0.044 % / 0.000 % / 64 | 0.044 % / 0.000 % / 64 | identical |
| qwen3-8-flash | 119 | 46.3 | 46.3 | 1.124 % / 0.360 % / 76 | 1.124 % / 0.360 % / 76 | identical |
| qwen3-8-max | 94 | 49.2 | 49.2 | 0.076 % / 0.000 % / 96 | 0.076 % / 0.000 % / 96 | identical |
| google-workspace-48px | 1 | 20.2 | 20.2 | 6.140 % / 5.502 % / 129 | 6.140 % / 5.502 % / 129 | identical |

