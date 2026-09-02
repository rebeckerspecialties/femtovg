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
