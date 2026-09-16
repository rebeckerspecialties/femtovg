# Browser-conformance harness: capture, framing, comparison

How every rendering claim in the femtovg conformance PRs was measured. The
point is reproducibility: the same scene, the same framing, the same metric,
so a number in a PR body means something.

## Renderers

**femtovg**: offscreen wgpu examples (`_logos_full.rs`, `_logos_pivot.rs`,
`_chainmx.rs` here) that render a 460x260 `Rgba8Unorm` texture and read it back
to PPM. They are `#![cfg(feature = "wgpu")]` and must stay *untracked* in
`examples/` when working in the femtovg repo: a wgpu-gated example with no
`main` breaks the featureless `cargo build --examples` CI job (that outage
happened). Build: `cargo build --release --example _logos_full --features wgpu`.
`_logos_full.rs <scale> <out.ppm> <file.svg> [dark]` (wgpu + usvg 0.48).

**Chromium** (headless shell from the puppeteer cache, `--disable-gpu` so the
software Skia path is deterministic):

    chrome-headless-shell --headless --disable-gpu --screenshot=out.png \
      --window-size=460,260 --default-background-color=FFFFFFFF file://$PWD/ref.html

**Firefox Developer Edition** (double-dash flags, needs a writable profile dir):

    firefox --headless --no-remote --profile /tmp/ffprof --window-size=460,260 \
      --screenshot out.png file://$PWD/ref.html

"Could not find profile folder" means macOS TCC is blocking the terminal from
Firefox's own profile registry; re-grant Files-and-Folders / Full Disk Access.
When Firefox is available, the Chromium-vs-Firefox diff is the tolerance
floor: femtovg only needs to land inside the browsers' own disagreement.

## Framing (the part that must match exactly)

Both sides draw a 460x260 canvas with a pivot zoom about the centre, then fit
the SVG into a 200x200 box at (130,30):

    // femtovg
    canvas.translate(230,130); canvas.scale(s,s); canvas.translate(-230,-130);
    canvas.translate(130,30); canvas.scale(200 / max(w,h));   // w,h = usvg tree.size()

    <!-- browser: make_ref.py emits this -->
    <svg width=460 height=260><g transform="translate(230,130) scale(S) translate(-230,-130)">
      <svg x=130 y=30 width=200 height=200 viewBox="..." preserveAspectRatio="xMinYMin meet" ...root attrs...>

Zoom ladders: 8-11 steps in and out (e.g. 0.6 .. 2.35) for a feature PR; a
0.7 / 1.3 / 2.1 triple for corpus sweeps. Canvas 2D references use the same
`ctx.translate(230,130); ctx.scale(s,s); ctx.translate(-230,-130)` framing.

## Metric (`compare.py`)

* `|a-c|.max(channel) > 20/255` -> percent of differing pixels.
* 2-px binary erosion of that mask -> "structural" percent. AA ribbons are 1-2
  px wide and disappear; what survives is real geometry/color divergence.
* Red overlay: differing pixels painted (255,0,0) on the femtovg render;
  evidence strips are rows of femtovg-before / femtovg-after / reference /
  diff-before / diff-after, one column per zoom.
* Subtle-hue classes (gradient interpolation space) hide under 20/255: use a
  threshold of 8 and/or probe known pixels against a hand-computed
  expectation (e.g. straight vs premultiplied midpoint over white).
* Thin-fill / AA-fringe classes: compare coverage-weighted ink at 2x/4x/8x -
  a ratio that converges toward 1 as shapes thicken is the fringe signature.
* `--threshold N` (default 20) and `--exact`. `--exact` adds a second line:
  the count of pixels that differ at all (delta >= 1), their mean delta, the
  bounding box of that set and the bounding box of the above-threshold set.
  Use threshold 8 and `--exact` whenever the content under test is faint -
  a group at opacity 0.14 can move a pixel by at most ~36/255 and mostly by
  a few counts, so a *complete* displacement or drop of that group survives
  neither 20/255 nor the erosion. Measured on `qwen3-8-2-4t-a95b` at 1x
  against Chromium 131 with the pre-review #323 build, whose nested mask
  (the `faceMask`-masked skin-texture rect at opacity 0.14 inside the
  `softDrop` group) landed displaced by the outer layer's capture origin:
  default `0.62 % / 0.000 %`, `--threshold 8` `1.98 % / 0.022 %`, `--exact`
  33,144 px (27.71 %) at mean delta 3.34 over the whole 200x200 box - all
  three read as "AA only". The probe that isolates it is an ablation: remove
  the group from the SVG and diff with-vs-without on each side. Chromium:
  7,228 px (6.04 %) change, bbox (185,50)-(277,191) = the face, max delta 35,
  0.000 % structural even at threshold 8. femtovg: 0 px change - the group
  contributed nothing. So for low-opacity layers report the ablation's
  `--exact` count and bbox, not the sweep percentage.

## Bisecting (env probes built into `_logos_full.rs`)

`PATH_RANGE=lo:hi` draw only those path indices (contact sheets of single
paths find the offending path fast); `PATH_DUMP=1` print segments;
`GRAD_DUMP=1` gradient stops + transform; `TREE_DUMP=1` usvg group tree
(mask/clip/filter/opacity); `NO_MASK=1`, `MASK_ONLY=1`, `SHOW_CAPTURE=1`;
`FORCE_SOLID=1` replaces gradient paints with magenta - the fastest way to
tell a geometry bug from a paint bug; `NO_CLIP=1`, `NO_OPACITY=1`,
`NO_BLEND=1` drop one feature class at a time (a render that *improves*
when a feature is dropped points at that feature's wiring), and
`CLIP_SHOW=1` paints each clip region magenta instead of clipping with it
(an empty clip region is invisible - and clips everything).

Other techniques that paid off:
* Keep pre-fix and post-fix binaries side by side (md5 them) and diff their
  outputs directly; "0 pixels changed" is itself a finding.
* Turn a `PATH_DUMP` into a pure-femtovg repro (segments -> `move_to /
  line_to / bezier_to`) with a `MODE` env var per hypothesis.
* Isolated references: `<defs>` + one `<path>` in the same nested-svg
  template. Always crop both images with the same slice - a crop edge once
  masqueraded as a rendering "crack".
* Build the pre-stack branch too, to separate regressions from pre-existing
  bugs.

## usvg wiring gotchas (all in `_logos_full.rs`)

* usvg 0.48 resolves `<use>`, folds units/percentages into gradient
  transforms, normalises radials to unit circle + transform; pass the
  transform via `with_gradient_transform`, radials via
  `two_point_radial_gradient_stops(fx,fy,0,cx,cy,r)`.
* Clip-path content transforms are relative to the clip root: walk the
  whole clip subtree (a `<use>` inside `<clipPath>` becomes a Group wrapping
  the path - collecting only direct Path children yields an empty clip, which
  correctly clips everything) and bake `group.abs_transform() *
  clip.transform() * path.abs_transform()` into the points before
  `clip_path`.
* `viewBox` needs no harness handling: usvg folds the viewBox-to-size
  transform into a synthetic root group, so `abs_transform()` already
  includes it. `<text>` needs `Options::fontdb_mut().load_system_fonts()` or
  it silently converts to nothing.
* Masks: draw content under the referencing group's `abs_transform()`, and
  **pre-capture every mask image before any `begin_layer`** - femtovg has no
  render-target getter, so a capture inside a live layer cannot restore to
  the parent layer image. Mask images: canvas-sized, `PREMULTIPLIED | FLIP_Y`.
* Fill/stroke opacity via `set_global_alpha` (no getter); wire dasharray,
  dashoffset, caps, joins, miter limit; fill rule per path.
* Not femtovg bugs: CSS `var()` fills (usvg -> black), `@keyframes` /
  `offset-path` animation state, CSS-hidden frames (usvg ignores `<style>`).
* Searchfox "SVG" downloads are HTML pages; `make_ref.py` unwraps them.

Known non-femtovg residuals in the corpus: CSS `mix-blend-mode` (femtovg has
Porter-Duff composites only - `corpus/banner.svg`'s `color-burn` group is
the driver), `feDropShadow` (a multi-input filter primitive, deferred), and
text set in fonts the machine lacks.

## femtovg facts that bite comparisons

* Alpha is premultiplied throughout; images without `PREMULTIPLIED` get
  re-premultiplied on sampling; render targets store flipped -> chain/layer
  targets need `PREMULTIPLIED | FLIP_Y`.
* `clear_rect` is deferred to flush, `update_image` is immediate.
* Two-stop gradients only take the shader path at stop offsets exactly 0/1;
  anything else goes through the 256-texel LUT. Browsers (Canvas and SVG)
  interpolate stops in straight, not premultiplied, space.
* Thin filled shapes render bolder than browsers (fringe AA, femtovg#327);
  Gaussian blur kernels differ (#325, ~8% px>8 at sigma 3, edges only,
  compounds in chains); clip edges are single-sample.

## Effect-chain matrix (`_chainmx.rs`)

Spec strings such as `sepia:1,blur:3,bright:1.4` on a structured 256x256
source: 16-px checkerboard (60,120,220)/(240,200,60), disc at (96,72) r=40
(200,30,30), semi-transparent bar rows 160-200 premultiplied (20,90,20,128).
The Chromium page builds the identical source via `putImageData` with
*straight* alpha (40,180,40,128) and applies `ctx.filter`; both composite
over white. Pure colour-matrix chains match Chromium to 0.00%; blur-bearing
chains carry the #325 kernel residual.

## Evidence conventions

Evidence PNGs, driver SVGs and reductions live on this `demo-assets` branch
and are embedded in PR bodies via raw.githubusercontent URLs. Every PR shows
before / after / reference with overlays, a per-zoom table (percent and
structural percent), and attaches the real-world driver file.

## Environment notes

`/private/tmp` is wiped between sessions on this machine (worktrees, harness
sources, corpus copies): keep anything worth keeping in this branch. Per-
worktree `CARGO_TARGET_DIR`s are ~2.3 GB each - share one across worktrees.

## Mapping SVG filters onto a backend that cannot run them all

Two rules, both learned from the BuseyBench corpus (`corpus/buseybench/`, 27
AI-generated 1024x1024 portraits), where getting either wrong moves a single
render by 5-9% of the frame. `_logos_full.rs` implements both, behind
`SKIP_UNSUPPORTED_FILTERS=1` and `VIEWPORT_CLIP=1`.

**1. A filter that never consumes the source replaces it - drop the subtree.**
An `feTurbulence`/`feFlood`/`feImage` chain synthesises its output from
nothing, so the shape carrying the filter is scaffolding the author never meant
to be seen - and since such a rect usually has no `fill`, it defaults to
**black**. Drawing it unfiltered paints a black wash over the artwork: three
corpus portraits came out 15-18% too dark that way. Classify by input, not by
primitive kind - if no primitive takes `SourceGraphic` or `SourceAlpha`, skip
the subtree; otherwise (`feDropShadow`, `feGaussianBlur`) draw it, applying
whatever the backend supports. Skipping on primitive kind alone is wrong in the
other direction: two portraits are wrapped whole in an `feDropShadow` group,
and dropping those erased the entire face.

*The case the input test cannot decide:* `feComposite operator="in"
in2="SourceGraphic"` uses the source as a **stencil**, so its colour never
reaches the output even though the chain does consume it. The input test keeps
that subtree and paints the black rect (`claude-opus-5.svg`, 3.65% structural).
The answer is not a cleverer scan but running the chain - see the next section,
which takes that file to 0.01%.

**2. An SVG viewport clips - scissor to it.** Content is `overflow: hidden` at
the viewport. Skip the scissor and anything pushed past the edge spills into
the page; the visible case is a blurred shape larger than the viewBox.
`qwen3-8-flash.svg` strokes a 470px-radius ellipse at 260px width under a 34px
blur, and without the clip its halo covers the surrounding page - 8.97% of the
frame, 5.19% structural, against 1.86%/0.04% with it.

With both rules the corpus lands at browser parity: mean structural difference
**0.24%** against Chromium, against a Chromium-vs-Firefox envelope of 0.19%,
and 26 of 27 files under 0.5%.

## Running feTurbulence chains and group shadows

Two more mappings, added with `ImageFilter::Turbulence` (fork branch
`fe-turbulence`) and the `begin_layer` shadow rule on #322. Both are in
`_logos_full.rs` and both can be switched off for A/B runs (`NO_TURBULENCE=1`,
`NO_SHADOW=1`); `PLAN_DUMP=1` prints each translated chain and `NOISE_ONLY=1`
draws a chain's output opaque and in place.

**3. `feTurbulence -> feColorMatrix* [-> feComposite in Source*]` runs as a
chain.** Every grain and skin-texture filter in the corpus has this shape. The
filter region is mapped to device pixels through the group's transform and a
noise image of that size is generated with a `transform` that puts the noise
in the group's user space, so it scales with the artwork like a browser's
does. The chain runs in the primitives' `color-interpolation-filters` space
(linearRGB unless the file says otherwise) and ends with
`ImageFilter::LinearRgbToSrgb`, which is what makes the constant-colour rows
of a grain matrix (`0.55 0.36 0.24` in linear) come out as the browser's
`(0.77, 0.63, 0.53)` rather than a much darker tint. A chain that never
consumes the source replaces it: the noise image is drawn alone under the
group's opacity and mask. `feComposite operator="in" in2="SourceGraphic"` (or
`SourceAlpha`) is Porter-Duff source-in against the source, which femtovg has
as `CompositeOperation::SourceIn`: the group gets a layer, the source draws
into it, the noise draws over it with `SourceIn`, and `end_layer` applies the
group opacity. The one pitfall met on the way: a layer shifts device space to
its own origin through the state transform, so a device-space rect drawn after
`reset_transform()` lands in the wrong place - draw the noise through the
group's own transform, as the paths are drawn.

Still unrunnable, by design of the backend rather than the harness: chains that
end in `feBlend mode="multiply"` against the source (fugu-ultra, gpt-5-2-pro,
gpt-5-6-sol, gpt-5-6-sol-pro, glm-5v-turbo) need separable blend modes
(femtovg/femtovg#332) - their effect is a darkening of a few percent, below the
20/255 threshold, which is why those files sit at 0.00-0.31% regardless - and
`feDisplacementMap` (ox-alpha's hair). Those groups still draw their source
unfiltered, per rule 1.

**4. `feDropShadow` on a group is the shadow state around `begin_layer`.** Set
`shadow_color`/`shadow_offset`/`shadow_blur` (offset and 2σ blur scaled to
device pixels) before `begin_layer`, and the layer's result casts one shadow
at `end_layer`; inside the layer the state resets, so children are not each
shadowed. The group needs a layer for this even at full opacity. Before the
#322 fix the shadow was suppressed at the composite, so these groups drew
shadowless.

Corpus effect (`busey-turbulence-metrics.json`, same refs and thresholds as
above): mean structural vs Chromium **0.237% -> 0.053%**, vs Firefox 0.223% ->
0.051% - inside the 0.19% browser-vs-browser envelope by a factor of three.
Attribution by switching one mapping off at a time: the group shadow alone
takes the mean to 0.205% (gemini-3-1-pro-preview 0.35 -> 0.03,
-custom-tools 0.47 -> 0.03, kimi-k3 / nex-n2-pro / qwen3-8-flash to 0.00),
turbulence alone to 0.087% (claude-opus-5 3.65 -> 0.01, qwen3-8-max 0.46 ->
0.04). Evidence: `busey-turbulence.png` (full frames with diff overlays) and
`busey-turbulence-detail.png` (3x crops against both browsers).

## Sub-pixel probe (`subpx.svg`, `subpx_ink.py`)

A 200x200 SVG rendered 1:1 in the harness frame: white discs of radius 0.25
to 3 px and white lines 0.2 to 2 px wide on `#202020`, each shape once on a
pixel corner/boundary and once on a pixel centre. `subpx_ink.py` sums coverage
per shape and prints it against the exact area (`pi r^2`, or the width per
unit length), so a renderer is judged against arithmetic and the browsers only
confirm they render coverage exactly (Chromium: 0.87-1.02x on discs, 0.99-1.00x
on lines). What it found on the BuseyBench eyes, which matched the browsers at
4x zoom and not at 1x:

* Every `<circle>` usvg emits is clockwise, so femtovg/femtovg#308's clockwise
  dilation (fixed by #336) added a pixel of radius to every catchlight, pupil
  and iris rim: a 0.5 px disc drew 9.6x its ink, r = 3 px 1.77x, r = 20 px 1.10x
  (`pi (r+1)^2` to within 2 %). With #336 discs are within 8 % of exact from
  1 px up; below that the fringe model leaves a +-1 px^2 residual (the sub-pixel
  half of femtovg/femtovg#327).
* Strokes thinner than a pixel drew at the square of their width ratio
  (nanovg's hairline rule): 0.2 px lines at 0.18x, 0.5 px at 0.25x. Skia scales
  alpha linearly and both browsers render exact coverage; the `hairline-coverage`
  branch does the same (0.99-1.01x after).

Corpus effect on top of everything above: #336 takes the mean pixel difference
vs Chromium from 2.33 % to 0.93 % and structural from 0.053 % to 0.027 %; the
hairline fix to 0.85 % / 0.026 % (Firefox 0.74 % / 0.025 %). Evidence
`busey-eyes-subpixel.png`; metrics `busey-336-metrics.json`,
`busey-all-fixes-metrics.json`.

## Other framings: 1080p (`FRAME_W`, `FRAME_H`, `BOX`, `BOX_X`, `BOX_Y`)

`_logos_full.rs` and `make_ref.py` read the same five variables, so a browser
page and a femtovg render can be framed identically at any size; `compare.py`
now compares over the common area and `boxstats.py` reports percentages of the
frame and of the SVG box separately, plus the mean delta. 1080p portrait: 
`FRAME_W=1920 FRAME_H=1080 BOX=1080 BOX_X=420 BOX_Y=0`, `--window-size=1920,1080`
for the browsers (Firefox needs `--profile $(mktemp -d)` to screenshot headless).

**What 1080p found on gpt-6-astra (2026-09-07).** At 460x260 the file is at
0.45 % of its box above 20/255 and 0.000 % structural against both browsers.
At 1080p it is **7.6 % / 3.1 % structural** - and none of it is antialiasing,
blur kernels or filters: it is #322's transient-image budget. The file opens
162 layers in one frame (opacity groups and blurred shading), each sized to
the 1080 px viewport scissor plus blur padding (~5 MB), some 800 MB requested
against the 256 MiB default; past the budget a layer degrades to pass-through,
which silently drops its blur *and* its group opacity, so the shading blobs
paint sharp and dark. `TRANSIENT_BUDGET_MB=4096` takes the same render to
**0.18 % / 0.000 %** (mean delta 1.4/255; the browser envelope is 0.02 %).
Sizing layers to their own bounding box (`LAYER_BBOX_SCISSOR=1`) does not
rescue it on its own - the sum still exceeds the budget and the later, more
visible layers are the ones that degrade (10.5 % / 5.5 %) - so the fix is
reuse, not sizing: a layer's image is free for the next layer as soon as its
end_layer composite is recorded, since commands run in order. Evidence
`busey-astra-1080p.png` (frames and diff maps) and `busey-astra-1080p-detail.png`
(3x cheek crops). Ruled out by ablation on the reference side: capping the
browser's blur sigma at femtovg's 8 px changes the diff by 0.01 points;
removing every stroke from both sides removes 2.3 points of ribbons but no
structure.

**Corpus-wide at 1080p (`busey_1080.py`, `summ_1080.py`, `busey-1080p-metrics.json`,
`busey-1080p-summary.txt`).** 26 of 27 files request more than the 256 MiB
transient budget per frame with viewport-sized layers (250 MB to 2.4 GB; 31 to
200 layers each), and 24 of 27 render differently because of it. Mean over the
corpus, % of the SVG box: **9.9 % / 7.0 % structural with the default budget,
1.5 % / 0.7 % with it lifted** (Firefox 1.5 % / 0.7 %; envelope 0.15 %).
qwen3-8-flash goes from 69 % / 63 % to 1.1 % / 0.4 %, claude-opus-5 from
27 % / 25 % to 0.15 % / 0.00 %. `poolsim.py` models a frame from `LAYER_LOG=1`:
no file nests layers deeper than one, so a pool that frees a layer's images at
`end_layer` peaks at 20-39 MB viewport-sized and 20-22 MB bounding-box-sized
(the largest single blurred layer, four images), against the gigabytes
requested today; bounding-box sizing is what cuts the bytes moved per frame
(3.2 GB to 285 MB on gpt-6-astra), which is the Raspberry Pi Zero's actual
constraint. Ten files stay above 0.05 % structural with the budget lifted
(gpt-5-2-pro 6.8 %, gpt-5-6-terra-pro 3.2 %, gemini-3-1-pro-preview-custom-tools
2.7 %, gpt-5-6-sol-pro 2.6 %, ...) - those are separate 1080p-scale items,
not yet attributed.

**Pool landed (#322, 2026-09-08).** With the within-frame transient pool
(reuse after `end_layer`, stores rounded to 64 px) and the default 256 MiB
budget, every corpus file at 1080p renders exactly as it did with the budget
lifted - mean 1.5 % / 0.7 % structural of the box, gpt-6-astra 0.18 % /
0.000 % - and `transient_image_bytes()` at the flush reads 20-94 MB (mean 49,
gpt-6-astra 29) where the frames requested 0.25-2.4 GB before
(`busey-1080p-pooled-metrics.json`, `LAYER_STATS=1`). Scissoring each group to
usvg's layer bounding box on top (`LAYER_BBOX_SCISSOR=1`) is not a win now
that nothing degrades: it multiplies size classes (mean 57 MB held) and the
bbox excludes the reach of the group shadow the harness casts, so
gemini-3-1-pro-preview goes from 2.2 % to 4.8 %
(`busey-1080p-pooled-bbox-metrics.json`). The harness also reports the bytes
held at the flush under `LAYER_STATS=1`.

**Pi Zero framing (2026-09-09, `pi_budget.py`, `busey-1080-pi-budget.json`).**
The pooled build after #322's review round (8 px shadow stores, quadrature
blur reach) holds 20-57 MB at the flush (mean 35) with the default budget.
`TRANSIENT_BUDGET_MB` walks the budget down: at 48 MiB - the guidance for a
Pi Zero, whose whole GPU share is 64-128 MB with 8 MB for the 1080p
framebuffer - the corpus renders the same (mean 1.55 % / 0.699 %, one of
2,373 layers passing through); 32 MiB costs 1.90 % / 0.914 % (57 layers pass
through, more lose their filter scratch and composite unfiltered); 16 MiB
6.78 % / 4.479 % (1,278 layers). `LAYER_STATS=1` now also prints the layers
`begin_layer` refused (pass-through), which is what the ladder counts. The
2x pivot zoom of gpt-6-astra (`_logos_full 2.0 ...` against
`make_ref.py ... 2.0`) matches Chromium at 0.20 % of the frame while holding
50 MB: stores are bounded by the scissor under the zoom transform, the
device-pixel-ratio case.

**Rebase validation drivers (2026-09-12).** `mkrefs.py` renders the Chromium
131 references for BuseyBench at 460x260, the Google Workspace icon ladder
and the noodles file (`--force-device-scale-factor=1`, or a Retina host
screenshots at 2x); `validate.py` and `validate_clip.py` run a harness binary
(`BIN`) over those plus the clip scene and print the compare.py numbers. Run
both against the previous build and the new one and diff the `.ppm` outputs:
a refactor that changes no pixels is bit-identical (the #323 mask rewrite was
on 36 of 40 frames, within 1/255 on the gradient-mask file; the #324 per-target
clip rewrite on 32 of 32).

**Zoom triple sweep (2026-09-16).** `validate.py` now runs the corpus at
1x, 2x and 4x (`--zooms`, default `1,2,4`; the pivot framing keeps the SVG
centre at (230,130) at every zoom, so 2x and 4x are crops of the same
artwork, the device-pixel-ratio case) and prints one table with a column
per zoom plus the per-zoom mean and the files above 0.05 % structural.
References are `chr_<name>_<zoom>.png` under `--refs`; `--make-refs`
renders missing ones with `make_ref.py` and chrome-headless-shell.
`--single-zoom Z` keeps the old behaviour (one zoom, the one-line summary,
`chr_<name>.png` accepted, `--gws` for the icon ladder); `--files a,b,c`
restricts the sweep; `--json` dumps the numbers. Three-file proof against
the pre-review #323 build (Chromium 131, 460x260, px>20 / structural):

    file                 zoom 1.0          zoom 2.0          zoom 4.0
    gpt-6-astra          0.15 % / 0.000    0.21 % / 0.000    0.37 % / 0.000
    kimi-k3              0.63 % / 0.000    1.45 % / 0.000    1.12 % / 0.005
    qwen3-8-2-4t-a95b    0.62 % / 0.000    1.00 % / 0.000    0.92 % / 0.000
    mean (3 files)       0.47 % / 0.000    0.89 % / 0.000    0.80 % / 0.002

## Build modes: exact #323 versus the full stack (`harness_clip`, `harness_turbulence`)

`_logos_full.rs` uses two APIs that are not in #323: `Canvas::clip_path`
(#324) and `ImageFilter::Turbulence` / `LinearRgbToSrgb` (#338). Both are
behind rustc cfgs so the headline numbers can be reproduced against the
exact #323 tree (master + layer-effects) as well as against the whole open
stack:

    export CARGO_TARGET_DIR=<the one build tree>
    # exact #322/#323 API surface: clip paths drawn unclipped, feTurbulence
    # chains left to SKIP_UNSUPPORTED_FILTERS (their groups are dropped)
    cargo build --example _logos_full --features wgpu
    # the full stack (#324 clip, #338 turbulence)
    cargo rustc --example _logos_full --features wgpu -- --cfg harness_clip --cfg harness_turbulence

`cargo rustc -- --cfg ...` applies the cfgs to the example crate only, so it
does not recompile the dependencies. `RUSTFLAGS="--cfg harness_clip --cfg
harness_turbulence" cargo build --example _logos_full --features wgpu` is
equivalent for the binary but re-fingerprints every dependency (about 2 GB
more in the target tree; do not use it on a full disk). Either cfg can be
set on its own. `LAYER_STATS=1` prints which build produced a frame and what
it left out:

    harness cfgs: clip=false turbulence=false
    filters skipped (SKIP_UNSUPPORTED_FILTERS): 3
    feTurbulence chains not run (no harness_turbulence): 3
    clip paths drawn unclipped (no harness_clip): 15

The gate was proved on one tree that has every API (corpus-all3): the
no-cfg build compiles and renders the two mask reductions bit-identically
to the full build (they use neither feature), and the full-cfg build renders
`qwen3-8-2-4t-a95b`, `gpt-6-astra`, `kimi-k3` and both reductions at 1x, 2x
and 4x bit-identically to the binary built before the gates were added.

## Mask reductions (`corpus/mask-*.svg`, 2026-09-16)

Two files written for the #323 review, to show what the corpus cannot.
The Google Workspace icon's mask (`google-workspace-48px.svg`) is
`mask-type:alpha` and its radial gradient's stops (`#ff63a0` at 0.62,
`#ff4c45` at 1, no `stop-opacity`) are fully opaque, so neither the stop
colours nor its `gradientTransform="matrix(21.9576 0 0 19.2967 14.47 24.2)"`
affect the coverage: the mask is 1 everywhere inside its path (confirmed by
reading the file; the review is right).

* `corpus/mask-luminance-radial-transform.svg` - a luminance mask whose
  radial gradient carries `translate rotate scale` and stops black -> white
  -> gray, over a solid blue rect (top half), and the same idea nested - a
  masked group inside a translated masked group (bottom half). The halves
  split at device row 130 at every pivot zoom. Chromium 131 and Firefox
  agree on it (0.00 % / 0.000 %, max delta 2 at 1x).
* `corpus/mask-nested-origin-reduction.svg` - the `qwen3-8-2-4t-a95b` skin
  texture reduced to high contrast: the same `softDrop` feDropShadow group
  (an outer layer) around the same `faceMask`-masked rect (an inner masked
  layer), fill solid red instead of feTurbulence, opacity 1 instead of 0.14,
  over a yellow face on blue. Correct output is an all-red face silhouette.
  Chromium and Firefox agree (0.00 % / 0.000 %, max delta 13).

Pre-review #323 build against Chromium 131 (px>20 / structural, 460x260):

    file                                   zoom 1.0            zoom 2.0            zoom 4.0
    mask-luminance-radial-transform        6.86 % / 6.140 %    10.22 % / 8.704 %   0.00 % / 0.000 %
      rows < 130 (single mask)             0.00 % / 0.000 %    0.00 % / 0.000 %    0.00 % / 0.000 %
      rows >= 130 (nested)                13.71 % / 12.281 %   20.44 % / 17.408 %  0.00 % / 0.000 %
    mask-nested-origin-reduction           5.58 % / 5.099 %    13.01 % / 11.100 %  0.31 % / 0.023 %

The single luminance mask matches at every zoom (max delta 2-3): stop
colours and the gradient transform are honoured. The nested cases are
displaced by the outer layer's capture origin, which under `VIEWPORT_CLIP`
is the scissor-clipped box origin: (130,30) at 1x, (30,0) at 2x, (0,0) at
4x. On the reduction at 1x that puts the inner mask entirely off its rect -
femtovg paints 0 red pixels and 6,422 yellow where Chromium paints 6,521 red
and 0 yellow (the whole face flips); at 2x the red silhouette lands 30 px to
the right (bbox x 194-318 against 164-296, 6,955 yellow pixels exposed on
the face's left edge); at 4x, with the origin at (0,0), it matches. The
luminance file's nested blob is cut to a quarter at 1x and shifted at 2x the
same way. This is the review's `a_nested_layers_mask_rect_is_root_device_space`
finding made visible at opacity 1; in the corpus the same displacement
hides under opacity 0.14 (see the ablation under Metric).
