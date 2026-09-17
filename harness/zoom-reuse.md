# Zooming through #340: what a frame recomputes, and retaining the transient pool across flushes

Date 2026-09-16. Machine: Apple M4 Max, macOS 27.0, wgpu 30 on Metal. Every binary is a debug build (the
disk rules forbid a release build), so wall times are debug times: the ratios and the counts are the evidence,
not the absolute milliseconds. Framing is the playbook's (`harness/README.md`): 460x260, pivot zoom about
(230,130), SVG in a 200 px box at (130,30), `SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1 LAYER_STATS=1`,
default 256 MiB transient budget; 0 layers passed through and 0 filters skipped in every run below.

Question: how does #340 (the quadrature blur split) perform while zooming in and out, and can calculations be
reused across zoom frames? Short answer: the split's cost is the pass count, quadratic in `sigma * zoom`, and it
is pixel work on content that changes with the zoom - nothing there is reusable. What every frame did recompute
needlessly, zoom or no zoom, is its transient images: the pool deleted every layer store, filter scratch and
shadow coverage at the flush and the next frame allocated them again (4-25 textures per frame on these files,
each with a Stencil8 companion the wgpu backend creates the first time the store is a render target). A
prototype that retains released transients across the flush (`pool-retain`, 8ad0eb8 in `/private/tmp/wt-pc`)
takes that to 0 per frame at a fixed zoom and to 0 on 20-29 of 39 sweep frames (23-26 % of the master count
over the sweep), for -16..-24 % frame time on the icon and -4..-8 % on a 57-layer file here; the Pi Zero model prices
each texture allocation at 600 us, so the same counts are worth 2-15 ms per frame there.

## 1. Measurements

### 1a. Wall per frame vs zoom, before and after the split (fixed zooms)

Binaries: `_logos_full_prequad` (md5 7596fc6e500e10e016916730008149ee, the full stack without the split) and
`_logos_full_quad` (md5 6ee1458fb7bc6e7a35af92c71d1fc3b0, with it), both `--cfg harness_clip --cfg
harness_turbulence`. Wall per frame = (FRAMES=11 - FRAMES=1) / 10 of the process wall, median of 3 interleaved
pairs; bytes = `transient bytes held at flush` (LAYER_STATS, the frame's peak, identical for FRAMES=1 and 11).

| file (layers/frame) | zoom | wall/frame prequad | quad | split delta | bytes at flush prequad | quad | icon blur passes |
|---|---|---|---|---|---|---|---|
| google-workspace-48px (1) | 0.6 | 3.68 ms | 3.69 ms | +0.02 | 589,824 | 589,824 | 1 |
| | 1.1 | 4.30 | 4.62 | +0.32 | 1,638,400 | 2,048,000 | 2 |
| | 1.6 | 4.12 | 6.36 | +2.24 | 1,966,080 | 3,440,640 | 4 |
| | 2.1 | 4.43 | 9.22 | +4.78 | 2,621,440 | 5,160,960 | 7 |
| | 2.35 | 4.70 | 11.11 | +6.41 | 2,621,440 | 5,734,400 | 9 |
| gemini-3-1-pro-preview-custom-tools (75) | 0.6 | 104.38 | 98.16 | -6.23 | 889,344 | 889,344 | |
| | 1.1 | 97.56 | 97.28 | -0.28 | 2,940,928 | 3,350,528 | |
| | 1.6 | 101.10 | 102.92 | +1.81 | 5,933,056 | 6,621,184 | |
| | 2.1 | 101.23 | 109.92 | +8.68 | 8,135,168 | 12,329,472 | |
| | 2.35 | 100.86 | 108.03 | +7.17 | 6,984,192 | 9,994,240 | |
| qwen3-8-flash (119) | 0.6 | 124.14 | 122.10 | -2.03 | 996,592 | 996,592 | |
| | 1.1 | 124.85 | 121.51 | -3.33 | 3,377,568 | 3,377,568 | |
| | 1.6 | 127.08 | 123.56 | -3.52 | 6,298,848 | 9,051,360 | |
| | 2.1 | 126.42 | 125.27 | -1.16 | 9,180,952 | 10,082,072 | |
| | 2.35 | 128.31 | 129.42 | +1.11 | 8,198,432 | 12,218,144 | |
| claude-fable-5-1 (178) | 0.6 | 138.89 | 138.17 | -0.72 | 740,512 | 740,512 | |
| | 1.1 | 142.99 | 136.21 | -6.79 | 2,398,080 | 2,398,080 | |
| | 1.6 | 138.96 | 135.51 | -3.44 | 5,219,488 | 5,219,488 | |
| | 2.1 | 142.43 | 143.13 | +0.70 | 6,981,056 | 7,636,416 | |
| | 2.35 | 142.67 | 139.24 | -3.43 | 5,683,328 | 8,632,448 | |

* The icon's blur is stdDeviation 2.38 user units x 4.17 fit = 9.9 device px at zoom 1, so its pass count is
  `ceil((9.9 z / 8)^2)` = 1, 2, 4, 7, 9 at the five zooms. The split's cost follows it: +0.02 ms at one pass,
  +6.41 ms at nine (about 0.8 ms per pass, two full-store draws each, on a 640 x 448 px padded store), and the
  store grows with the true reach (bytes 2.6 -> 5.7 MB at 2.35: five pooled images padded by 3 sigma + 2 = 72 px
  instead of the old 8 px cap's 26 px). This is the only cost in the table that grows superlinearly with zoom, and it is #340's
  by design (the reach it renders is the one the browsers render).
* On the three BuseyBench files the split moves wall by -6.8..+8.7 ms against a noise band of about +-5 ms
  (their sigmas are 0.3-12.5 device px at 1.6, so most blurs stay one pass), while their bytes rise 0-51 % at the
  zooms where a blur crosses the 8 px bound. Their wall is flat across a 17x range of store area (gemini 97-110
  ms from 0.6 to 2.35): the frame is bound by the per-layer command encode in this debug build (0.5-0.9 ms per
  layer: 75 layers 98 ms, 119 layers 122 ms, 178 layers 136 ms), not by pixels. `record_ms` (usvg walk +
  tessellation, before `flush_to_output`) is only 2-3.5 ms of it; the rest is `renderer.render` encode plus GPU.

### 1b. The zoom sweep (ZOOM_SWEEP="0.6:2.35:40", the split tree)

`harness.rs` (this directory's copy of `_logos_full.rs`) adds `ZOOM_SWEEP="lo:hi:n"`: n frames whose zoom
steps lo -> hi and back (a triangle over the n frames, hi at the midpoint), each frame re-rendering the whole
scene at its own zoom, and prints one `FRAME` line per frame (also under `FRAME_LOG=1` with a fixed zoom):
zoom, wall ms (frame start to `device.poll` return), record ms, transient bytes at the flush and after it, and
`created` = live wgpu textures before the flush minus live after the previous flush minus the harness's own
mask/noise images (`wgpu::Instance::generate_report().hub.textures.num_kept_from_user`, no library hook). The
copy also deletes the harness's per-frame mask and turbulence-noise images after each flush (the original leaks
1-4 per frame), so they do not count. Built as `examples/_zoom.rs` in `/private/tmp/wt-all3` with the two cfgs
(`bin/_zoom_quad` here, md5 53e08d32a8e415ad74a25d876d80109b); the tree's own sources are untouched.

| file | sweep wall/frame (median, frames 1-39; 2 runs) | record | created/frame under the sweep (min-max, median) | created over frames 1-39 | created/frame at the fixed zooms 0.6/1.1/1.6/2.1/2.35 (frames 1-10) | bytes at flush over the sweep |
|---|---|---|---|---|---|---|
| icon | 5.95 / 5.53 ms | 0.35 | 4-5, 5 | 190 | 4/5/5/5/5 | 0.56-5.47 MiB |
| gemini-3-1-pro | 98.1 / 97.7 | 2.2 | 10-17, 11 | 465 | 9/10/12/17/13 | 0.85-11.76 |
| qwen3-8-flash | 123.1 / 121.8 | 3.5 | 16-25, 22 | 850 | 14/14/20/18/19 | 0.95-12.25 |
| claude-fable-5-1 | 134.1 / 136.2 | 3.1 | 9-14, 9 | 410 | 9/9/12/13/13 | 0.71-8.22 |

* Images created per frame under the sweep equal the fixed-zoom count at the same zoom (gemini at 2.13: 17 in
  both) and `bytes_after_flush` is 0 on every frame: the pool retains nothing, so a zoom step costs no more
  allocation than a repeated frame does - every frame pays the full set. Frame 0 adds the gradient textures
  (the gradient store keeps those across frames: icon +1, gemini +8, qwen +21, claude +13, once).
* `textures_after_flush` on the icon is a constant 5 (target, wgpu's empty texture, the screen stencil, one
  gradient, the kept horizontal blur buffer): the blur buffer is replaced, not accumulated, when its size
  changes. With retention it becomes 12 (below): each retained store keeps its Stencil8 companion.
* Per-frame wall along the sweep tracks the zoom on the icon (3.6 ms at 0.6, 10.6 ms at 2.31, the pass count
  again) and is flat on the others (gemini 94-118 ms with no trend).

### 1c. Size classes along the sweep

Stores round to 64 px per axis. The icon's single store changes class on 8 of the 19 up-leg steps (per-image
bytes 147,456 -> 262,144 -> 327,680 -> 409,600 -> 589,824 -> 688,128 -> 786,432 -> 1,032,192 -> 1,146,880: the
box grows 18 device px per 0.09 zoom step, the blur pad faster), i.e. a class lasts 2-3 sweep frames. On the
multi-layer files the frame's transient total changes on 16/19 (gemini-3-1-pro), 19/19 (qwen), 19/19 (claude)
up-leg steps because some layer's class flips almost every step, but each layer's own class persists for the
same 2-3 frames; the prototype's `created` counts below are the direct measure of how much that leaves reusable.

## 2. What a frame recomputes, and what of it is reusable

Read from `/private/tmp/wt-le` (branch `blur-quadrature`, 05b17b3): `src/transient.rs`, `Canvas::begin_layer`
/ `end_layer` / `filter_image_chain` / `render_shadow` in `src/lib.rs`, `gaussian_blur_filter` in
`src/renderer/wgpu.rs`.

| recomputed per frame | cost | zoom-specific? | reusable across frames? |
|---|---|---|---|
| Pass plan `filter_passes()` per chain (fold, split, parity), `blur_passes()` | one `Vec<ImageFilter>` of <= passes+1 Copy items per layer/chain; microseconds; part of the 0.3-3.5 ms `record_ms` | the pass count depends on `sigma * zoom` | cacheable but there is nothing to gain: the whole record phase is 0.3 % (icon) to 3 % (qwen) of the frame |
| Gaussian coefficients `gaussian_blur_coefficients(sigma)` | one sqrt + one exp per blur pass, in `render` | no | same: unmeasurable |
| Layer store, mask coverage, filter result + scratches, shadow coverage + blur (the pool) | a texture allocation each (`device.create_texture`), plus a Stencil8 companion per store the first time it is a render target (`stencil_buffer_for_textures`), plus their first clear; **`release_all` deletes every non-held transient at the flush: confirmed** (`bytes_after_flush=0`, `created` = the whole set every frame: icon 4-5, gemini-3-1-pro 9-17, qwen 14-20, claude 9-13, gemini-3-7-flash 6-7, gemini-3-8-flash 7-9 per frame; the same under the sweep) | the sizes are (a class lasts 2-3 sweep frames), the churn is not: a fixed zoom recreates 100 % | yes: at a fixed zoom 100 % of it, under the sweep the frames whose classes did not change - measured below |
| wgpu horizontal blur buffer | kept across passes and frames, replaced only when a blur's source size or format differs from the previous blur's; under the sweep at least one replacement per frame, within a frame one per size change between consecutive blurs (0-3 per frame on these files: every layer here shares the viewport scissor, so a frame has 2-3 store classes) | yes, one per zoom step | already reused; a small by-size set (the parked GL patch 04's shape) would remove the in-frame replacements; minor |
| Blur/composite pixel work, the split's extra passes | the GPU term, plus in this debug build the per-pass encode (0.8 ms per pass on the icon) | yes: quadratic in `sigma * zoom` (pass count) times store area | no: it is the rendering of content that changed. Only a scene-level cache of a static layer's filtered result would skip it, outside the pool's scope |
| Per-layer command encode (`renderer.render`: pass switches, bind groups, pipelines) | 0.5-0.9 ms per layer here, 95+ % of the multi-layer frames | no, flat across zoom | not reusable across frames by construction (commands are re-recorded); the debug build inflates it |

The largest real cost per frame on the multi-layer files is the every-frame encode, not anything zoom-specific;
the only zoom-specific cost that grows faster than linearly is #340's pass count, which is real work. The
largest *reusable* cost is the pool's per-frame allocation: every store and its stencil companion, every frame.
That is what the prototype retains.

## 3. Prototype: `pool-retain` (8ad0eb8, `/private/tmp/wt-pc`, off upstream/master 384060f)

`src/transient.rs`: the flush (`end_frame`, replacing `release_all`) keeps every released transient on the free
list for the frames to come; deletes those no frame took for `RETAIN_FRAMES = 2` consecutive frames (at the
second idle frame's flush) and any never released; and evicts, least recently used first, the retained images
this frame has not touched whenever an acquire would otherwise pass the budget (a fresh allocation, or a reuse
after the budget was lowered) and again at the flush. Each transient carries the frame of its last acquire or
release; only an image untouched since the last flush is ever deleted mid-frame, because a touched one may be
read by a command the flush has yet to execute. Held images (layers open across the flush) are unchanged.
`bytes` counts retained images, so `transient_image_bytes()` is now what the frame drew through plus what recent
frames left for it, bounded by the budget together; docs updated at `transient_image_bytes`,
`set_transient_image_budget`, `filter_image_chain`, the pool module. Invariants: (1) bytes <= budget after every
acquire and flush whenever untouched retained images can make it so, (2) an acquire fails only when it would
have failed without retention (retention never costs admission), (3) nothing referenced by a pending command is
deleted, (4) at a fixed zoom with a stable scene the pool holds exactly one frame's working set and allocates
nothing after the first frame, (5) under a class change the old class lives two more frames unless the budget
needs the room. Tests: four existing tests that asserted deletion at the flush now assert retention (reasoned
messages); four new tests cover reuse without allocation across frames, the two-idle-frame lifetime (drawn every
other frame keeps the store), eviction of an untouched retained store under a one-store budget with a touched
store staying put (and the third size refused as before), and the trim after a lowered budget at the next
acquire and at the flush. `cargo test --features wgpu` (109 lib + doc/example suites) and `cargo test` (default,
27 suites) pass; rustfmt clean.

Measured with the same harness copy built as the gated `_logos_full` (no clip/turbulence cfgs; master's harness
draws clip paths unclipped and skips feTurbulence, so only files without either are used: the icon and the two
BuseyBench files without clip or turbulence content, gemini-3-7-flash and gemini-3-8-flash) on upstream/master
(`bin/_gated_master`, md5 77ede79cd59eddbd0aa7fc6cd12ae1da) and on pool-retain (`bin/_gated_retain`, md5
14ce121c0c884625edb91ab7a8243c08); neither has the split. Fixed zooms: FRAMES=11, median over frames 1-10 of 3
runs; sweep: frames 1-39 of 2 runs.

| file (layers) | zoom | wall/frame master | pool-retain | delta | created/frame master -> retain | bytes at flush (retained after) | live textures after flush master -> retain |
|---|---|---|---|---|---|---|---|
| icon (1) | 0.6 | 4.19 ms | 3.35 ms | -0.84 (-20 %) | 4 -> 0 | 0.56 MiB (0.56) | 4 -> 12 |
| | 1.1 | 4.55 | 3.44 | -1.11 (-24 %) | 4 -> 0 | 1.56 (1.56) | 4 -> 12 |
| | 1.6 | 4.44 | 3.43 | -1.00 (-23 %) | 4 -> 0 | 1.88 (1.88) | 4 -> 12 |
| | 2.1 | 4.40 | 3.66 | -0.74 (-17 %) | 4 -> 0 | 2.50 (2.50) | 4 -> 12 |
| | 2.35 | 4.43 | 3.71 | -0.72 (-16 %) | 4 -> 0 | 2.50 (2.50) | 4 -> 12 |
| gemini-3-7-flash (57) | 0.6 | 58.64 | 54.76 | -3.88 (-7 %) | 6 -> 0 | 0.61 (0.61) | 17 -> 29 |
| | 1.1 | 59.61 | 54.94 | -4.67 (-8 %) | 6 -> 0 | 1.92 (1.92) | 17 -> 29 |
| | 1.6 | 59.54 | 55.37 | -4.17 (-7 %) | 7 -> 0 | 3.48 (3.48) | 17 -> 31 |
| | 2.1 | 58.64 | 56.15 | -2.49 (-4 %) | 6 -> 0 | 3.89 (3.89) | 15 -> 27 |
| | 2.35 | 58.20 | 55.62 | -2.58 (-4 %) | 6 -> 0 | 4.41 (4.41) | 15 -> 27 |
| gemini-3-8-flash (118) | 0.6 | 112.80 | 104.20 | -8.60 (-8 %) | 7 -> 0 | 0.67 (0.67) | 19 -> 33 |
| | 1.1 | 108.86 | 105.40 | -3.46 (-3 %) | 7 -> 0 | 2.17 (2.17) | 19 -> 33 |
| | 1.6 | 106.66 | 110.76 | +4.10 (+4 %) | 9 -> 0 | 4.34 (4.34) | 19 -> 37 |
| | 2.1 | 110.50 | 107.93 | -2.57 (-2 %) | 7 -> 0 | 4.44 (4.44) | 19 -> 33 |
| | 2.35 | 105.79 | 106.66 | +0.86 (+1 %) | 7 -> 0 | 5.03 (5.03) | 19 -> 33 |

| file | sweep wall/frame master -> retain (median) | sum of frames 1-39 | images created over the sweep master -> retain | retain: frames with 0 creations / max per frame | peak bytes at flush master -> retain | peak retained after a flush |
|---|---|---|---|---|---|---|
| icon | 4.17 -> 3.82 ms (-8 %) | 177 -> 150 ms | 156 -> 40 (26 %) | 29 of 39 / 4 | 2.50 -> 4.69 MiB (1.9x) | 4.69 MiB |
| gemini-3-7-flash | 59.10 -> 55.72 (-6 %) | 2338 -> 2187 | 242 -> 56 (23 %) | 21 of 39 / 8 | 5.02 -> 8.30 (1.65x) | 7.27 |
| gemini-3-8-flash | 106.47 -> 110.83 (+4 %) | 4190 -> 4346 | 285 -> 66 (23 %) | 20 of 39 / 7 | 5.84 -> 9.47 (1.62x) | 8.38 |

* Fixed zoom: the pool creates nothing after frame 0 on every file and zoom; the bytes are unchanged (the
  working set is retained, not grown) and the live texture count rises by exactly two per store (the store and
  its stencil companion now survive). The frame-time gain is 0.7-1.1 ms on the icon (4 stores + 4 stencils per
  frame, about 0.25 ms per pair on this Mac in debug) and 2.5-4.7 ms on gemini-3-7-flash (6-7 stores); on
  gemini-3-8-flash (7-9 stores, 118 layers, 105-113 ms) it is inside the +-4 ms noise of the encode-bound
  frame.
* Sweep: creations fall to 23-26 % of master's and to 0 on 20-29 of 39 frames; the rest are the frames where a
  class changed (icon: 4 images on each of its 10 class switches, 5 up and 5 down; the down leg recreates the
  classes the up leg visited 20 frames earlier, beyond the two-frame window). The price is memory on a switch:
  the old class stays two more frames beside the new one, so the peak at a flush is 1.6-1.9x master's here (the
  budget evicts it first when the room is needed; at 256 MiB it never is on these files). A retention window of
  one frame would halve the after-flush residue but not the peak at the switching frame, which is old + new
  regardless.
* The harness's `transient bytes held at flush` (LAYER_STATS) on pool-retain includes the retained set; readers
  comparing against the #340 evidence should use the master binary's figure as the frame's peak.

## 4. Recommendation

Its own PR, off master, independent of #340 (the split changes nothing about what is retained; the two touch
different code, one doc paragraph aside). Small: `transient.rs` (+128/-43 lines), docs, tests. It removes the one
per-frame cost that is pure churn (every store and stencil companion, every frame) and does so with the
existing budget as the only knob, so no integration changes; the visible semantic change is that
`transient_image_bytes()` includes the retained set (documented) and that the texture count between frames is
the working set rather than zero.

Pi Zero class (the harness/pz model, `us_per_tex_alloc` = 600 us, range 300-1500, "CMA BO alloc + FBO
validate"): the per-frame recreation this removes is 4-25 pool images per frame on these files, i.e. 2.4-15 ms
of modelled CPU per frame at a fixed zoom (the icon 2.4 ms; gemini-3-8-flash 4-5; claude-fable 5-8; qwen 8-12),
plus the GL backend's per-image framebuffer with its stencil renderbuffer, which its `framebuffers` map also
drops at `delete_image` and would likewise survive. Against BuseyBench's 300-3,600 ms modelled frames that is
under 3 %; against the icon class (tens of ms: clipdemo 34 -> 16 ms with the six parked patches) it is 7-15 %,
and under a zoom 74-77 % of it still goes. Memory: the budget (32-48 MiB there) bounds live + retained
together, and a fresh store evicts untouched retained ones before it fails, so admission is unchanged; what
changes is that a static scene keeps its working set resident between frames (already its in-frame peak) and a
zoom step briefly holds old + new classes up to the budget. Not measured on the device; the model's allocation
term is the claim.
