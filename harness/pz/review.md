# Hot-path review of the open stack for an ARM11 (Raspberry Pi Zero) CPU

Reviewed tree: /private/tmp/wt-pz at commit 0a56986 (branch pz-measure = corpus-all3, i.e. upstream
master b3dd9a7 with #323 layer masks, #324 clip paths, #334 composite, #336 winding, #338 turbulence and
#339 hairline merged, plus the PZ_STATS instrumentation). Line numbers below are of that commit's
src/lib.rs, src/transient.rs, src/path/cache.rs, src/turbulence.rs and src/renderer/opengl.rs (a copy
of each is under src_head/ next to this file); the instrumentation commit adds the `debug_inspector`
blocks and the `FrameStats` struct, so functions after line ~500 sit about 100 lines lower than on the
PR branches, under the same names.

Everything quantitative comes from three sources, and each number says which:

* **counters** - the `debug_inspector` counters in `measurements.json` (per frame, this Mac, release,
  median of frames 2-6; column names as in measurements.md and the hot-path table below);
* **profile** - `sample` of the harness main thread (release, 640x480, 1 ms sampling; profile/summary.md,
  raw call trees in profile/*.sample.txt), taken with patches 01-05 applied;
* **model** - the ARM11 cost model in section 2, applied to the counters.

Per-frame counter values quoted as "up to N" are the maximum over the 27 BuseyBench files at 640x480
unless stated; the icon set's values are given separately where they differ in kind.

## 1. Where recording time goes (measured on this Mac)

Recording is femtovg's CPU work between the first draw and `flush_to_output`: path flattening,
tessellation, uniform blocks, command list. On this Mac it is 0.03-0.8 ms per frame for every file in the
corpus (measurements.md, "record ms"), and the profile splits it as follows (percent of samples inside
the harness's `draw_nodes`, which also includes the harness's own usvg-to-`Path` conversion, 5-8 %):

| share of recording | Ghostscript_Tiger (305 cmds, no layers) | gpt-6-astra (1261 cmds, 162 layers, 8 clips) | qwen3-8-2-4t-a95b (1407 cmds, 200 layers, 113 blurs) |
|---|---|---|---|
| fill_path_internal + stroke_path_internal (inclusive) | 69 % | 62 % | 53 % |
| of which PathCache::new (flatten + transform), tesselate_bezier inside it | 25 % (18 %) | 19 % (12 %) | 16 % (9 %) |
| of which expand_fill / expand_stroke (vertex generation, incl. calculate_joins) | 30 % / 4 % | 16 % / 16 % | 20 % / 10 % |
| allocator (malloc/free/realloc, all callers) | 27 % | 24 % | 19 % |
| Vec regrowth of any kind (RawVec::grow) | 23 % | 22 % | 22 % |
| begin_layer + end_layer (chain, mask reserve, composite) | 0 | 14 % | 27 % |
| acquire_transient_image (pool scan) | 0 | 5 % | 14 % |
| clip_path + replay | 0 | 4 % | 2 % |
| Params::new | 1 % | 1 % | 3 % |

Three things stand out and drive the ranking in section 4: the allocator and Vec regrowth are a fifth to a
quarter of recording on every file; on layer-heavy files the layer machinery (begin/end_layer, the
transient pool scan) is a quarter of recording; and on all files the tessellation proper
(PathCache::new + expand) is 40-55 %. The profile is of this Mac; section 2 says how each of those
categories scales to an ARM11.

## 2. ARM11 cost model for this code (the "CPU factor")

The track asks for a stated ARM11 slowdown factor against this Mac. The model (model_pi.py) uses 45x
central, 30x optimistic, 60x pessimistic, applied to the measured recording time. Justification:

* Clock: ARM1176JZF-S at 1.0 GHz vs an Apple M4 performance core at ~4.4 GHz: 4.4x.
* Issue width and scheduling: single-issue in-order 8-stage pipeline vs a ~10-wide out-of-order core. On
  branchy scalar code an ARM11 sustains ~0.5-0.8 instructions per cycle; the M4 sustains 4-6 on this code
  (the profile shows no memory stalls to speak of - the whole frame's working set fits its 128 KB L1D /
  16 MB L2). Ratio 5-8x. Combined with the clock: 22-35x for compute-bound loops.
* Floating point: VFP11 executes scalar single precision with 4-cycle FMAC latency and no dual issue; the
  M4 has four 128-bit FP/SIMD pipes. femtovg's tessellation is scalar f32 on both, so this is inside the
  IPC ratio, but `f64` work (turbulence lattice, section 3.11) runs on VFP11's slower double path.
* Memory: the Pi Zero's ARM11 has 16 KB L1 I and D caches (4-way, 32 B lines) and no L2 visible to the
  ARM by default (the BCM2835's 128 KB L2 is the VideoCore's); an L1 miss goes to LPDDR2 at ~100-150 ns,
  i.e. 100-150 cycles, blocking, with no out-of-order window to hide it. The M4 hides an L1 miss in an L2
  hit of ~15 cycles inside its window. So anything that walks memory larger than 16 KB - a 1400-entry
  command list of 496 B each (section 3.10), a 700 KB vertex buffer, a 4000-entry pool free list
  (section 3.8), malloc's free lists - pays 100+ cycles per line instead of ~0: 60-100x on those paths.
  There is also no NEON: memcpy runs at ~300-600 MB/s (LDM/STM), so 1 MB of per-frame copying costs 2-3
  ms by itself.
* Branches: the ARM1176 has a 128-entry branch target address cache with a static fallback and a 3-entry
  return stack; a mispredict costs the 8-stage pipeline. `calculate_joins` (cache.rs:800-938) decides
  ~15 data-dependent branches per point (partial_cmp matches for convexity, three flag tests, two bevel
  tests), and `tesselate_bezier` (cache.rs:307-378) recurses to depth 10 with 12 arguments, deeper than
  the return stack, so every return beyond three levels mispredicts. Expect 30-50 % of cycles in those
  two loops to be mispredict and stack-spill overhead: the top of the compute-bound range.
* Instruction cache: the recording path for one fill (fill_path_internal, PathCache::new,
  tesselate_bezier, expand_fill, calculate_joins, Params::new, append_cmd, the allocator) is ~40-60 KB of
  machine code, more than the 16 KB I-cache; each draw walks through it once, so the I-cache thrashes
  between phases. The Mac profile cannot show this; it argues for the upper half of the range for
  scenes of many small draws (the icon set, the Tiger).

Weighting the profile's split (40-55 % compute-bound tessellation at 22-35x, 20-25 % allocator and Vec
regrowth at 60-100x, the rest mixed) gives 35-55x; 45x central, 30-60x range. Per frame that is, from
the measured Mac recording times: icons 1.3-9 ms (Tiger 24 ms), BuseyBench 12-36 ms. On the Pi those
compete with the GL driver's own per-draw and per-pass CPU cost (Mesa vc4 on ARM11: modelled 60 us per
draw and 150 us per render-pass switch, range 30-120 / 80-300), which for the Tiger's 869 draw calls is
another 52 ms and for BuseyBench 45-320 ms - on this device the driver overhead, not femtovg, is the
larger CPU item for draw-heavy scenes, and the GPU (section 5) dominates both.

## 3. The hot paths, one by one

Format: what it does; per what; allocations per call; branchiness; working set; measured count in the
corpus; ARM11 estimate (model); fix.

### 3.1 `Canvas::clip_path` (lib.rs:1929-1950)

Per clip. Emits `ClipReset(true)` over the **whole render target** if it is the first clip on this target
(1931-1934, `push_target_quad` 1982-1990), then `emit_clip_fill` (1998-2020): `path.cache(&transform)`
(a flatten+transform rebuild unless the path was just drawn under the same transform),
`expand_fill(0.0, ..)` (fans, 2-3 allocations per contour, section 3.9), the fans copied into `verts`, and
**two more whole-target quads** as the resolve pass (2019). Then `path.clone()` (1938) into the
`ClipEntry` - and `Path` derives `Clone` *including* its `RefCell<Option<(u64, PathCache)>>` cache
(path.rs:109-116), so the clone copies the verbs, the coords, the flattened points, every contour and every
contour's freshly expanded fill vertices: 3 + 2 x contours allocations and a memcpy of everything just
built.

* Allocations: 3 + 2c (clone) + 2-3c (expand) per call, c = contours.
* Branchiness: expand_fill's (3.9).
* Working set: the path plus its cache twice.
* GPU: 3 full-target stencil quads per first clip and 2 per nested clip. **Counters**: up to 11
  clip_path calls per frame, 46 full-target quads = 12.1 Mpx at 640x480 and 54-75 Mpx at 1080p
  (qwen3-8-flash / qwen3-8-27b) - 10-15 % of all stencil-plane fragments the frame draws, for a few
  small clips.
* ARM11: the CPU side is small in the corpus (<= 11 calls; profile 3 % on gpt-6-astra); the stencil quads
  are the cost: 12 Mpx at the model's 0.8 Gfrag/s stencil rate is 15 ms per frame at 640x480, 70-90 ms at
  1080p, plus the Z/S tile traffic of three passes over the target.
* Fix: bound every arm/resolve/disarm quad to the running intersection of the clip bounds on the target
  (patch 01: `ClipEntry.armed`, `clip_rect_of`, `push_rect_quad`) - **measured** 111 -> 12.6 Mpx of clip
  quads over BuseyBench at 640x480, 714 -> 63 Mpx at 1080p, pixel-identical on all 70 renders; and keep
  the device-space fans in the entry instead of the `Path` (patch 03, below).

### 3.2 `replay_clip_stack` (lib.rs:1955-1975)

Per `restore()` (or `reset()`) that pops a clip taken on the current target (`pop_clips_to`, 933-943).
Collects `.cloned()` copies of every surviving entry on the target (1957-1961: one Vec allocation plus a
full `Path` + cache clone per survivor, as in 3.1), emits a whole-target `ClipReset`, then re-runs
`emit_clip_fill` for each survivor: the cache key matches the stored transform so the flatten is skipped,
but `expand_fill` runs again (2-3 allocations and a fan rebuild per contour) and two whole-target quads are
pushed per survivor.

* Allocations: 1 + (3 + 2c) x survivors (clones) + (2-3c) x survivors (re-expansion).
* Branchiness: expand_fill's.
* Working set: every surviving clip path, twice.
* GPU: 1 + 2 x survivors full-target stencil quads per replay.
* **Counters**: clip_replays == clip_path_calls in every corpus file (every clip is popped once), but
  clip_replay_entries is 0-2 per frame: BuseyBench nests clips rarely. Cost scales as
  (nesting depth) x (restores inside the nest) per frame - a UI with a 3-deep clip and 50 widgets
  restoring inside it re-expands 150 clip paths and draws 350 full-target stencil quads per frame; the
  corpus does not exercise that, the code does.
* ARM11: per replayed entry roughly the cost of one fill's expand plus a memcpy of the path and cache:
  ~30-100 us modelled; the stencil quads are again the larger term.
* Fix: patch 03 - `ClipEntry` keeps `contours: Vec<Vec<Vertex>>` (the device-space fans built once at
  clip time) and its `armed` rect; a replay `extend_from_slice`s the stored fans into `verts` (no clone,
  no cache, no expand) and the reset/resolve quads are bounded to the survivors' intersection. The
  `pop_clips_to` path takes the stack with `mem::take` while emitting (no `cloned().collect()`).
  Measured: pixel-identical on all 70 renders; allocations -1 to -170 per frame on the clipped files.

### 3.3 `clip_active()` in `append_cmd` (lib.rs:948-951, 1064-1082)

Per command (every fill, stroke, triangle and filter command; not stencil bookkeeping or target
switches). A linear scan of `clip_stack` comparing each entry's `target` with the current one.

* Allocations: none. Branchiness: one compare per entry. Working set: the clip stack (unpatched
  `ClipEntry` is ~130 B with the `Path` inline; patched ~80 B).
* **Counters**: clip_active_scans up to 751 per frame, clip_active_steps up to 521 per frame (gpt-6-astra)
  - the stack is 0-3 deep in the corpus, so the scan is a few loads per command.
* ARM11: 521 steps x ~10 cycles = ~5 us per frame. Negligible now; O(depth) per command by design, so a
  deep clip stack (unusual) would make it O(commands x depth).
* Fix (if ever needed): cache `clip_active` as a bool on the canvas, recomputed on clip push/pop and
  target switch (four sites). Not worth a patch today; noted so the scan is not mistaken for a cost.

### 3.4 `LayerRecord.effects: effects.clone()` (lib.rs:615-632, 1563, 1640)

Per layer. `LayerEffects` (505-512) is `{ opacity: f32, filters: Vec<ImageFilter>, mask: Option<LayerMask> }`;
cloning it allocates once when `filters` is non-empty (ImageFilter is `Copy`, so it is one malloc plus a
memcpy of n x ~88 B).

* Allocations: 1 per filtered layer (0 for plain opacity layers). Branchiness: none. Working set: tiny.
* **Counters**: up to 200 layers per frame, 113 of them filtered (qwen3-8-2-4t-a95b): ~113 mallocs, ~10 KB.
* ARM11: 113 x ~0.3-0.5 us = ~50 us per frame. Small but pure waste, and it sits on the same `begin_layer`
  path as the store acquisition.
* Fix: hold the filters in a `SmallVec<[ImageFilter; 2]>` (SVG chains are one or two filters) or an
  `Rc<[ImageFilter]>` so the clone is a refcount bump; or keep a per-frame `Vec<ImageFilter>` arena on the
  canvas and store a `Range<usize>` in the record. Any of the three is a few lines; not patched here
  because the pool scan and the composite path (3.8, 3.12) dwarf it.

### 3.5 `render_shadow` and the `path.clone()` around it (lib.rs:2260, 2470-2471, 2651-2810)

Per shadowed fill or stroke. `fill_path_internal` first builds the cache for the bounds (2255-2258:
flatten+transform under T), then clones the whole `Path` including that cache (2260) and the paint, and
calls `render_shadow`, which: acquires a coverage transient and (if blurred) a second one (2717, 2726:
two pool scans), `save()`s (a 224 B `State` push), switches target, `clear_rect`s, sets the offset
transform, re-enters `fill_path_internal` on the clone (2755) - whose `path.cache(&T')` misses (T' is T
translated by (-minx, -miny)) and **flattens the path a second time** -, expands it, then `fill_device_rect`
for the SourceIn recolor (2767), `filter_image` for the blur (2773), restores, and `fill_device_rect` for
the composite (2799). Back in the caller, `path.cache(&T)` (2268) misses again because the cache now holds
T', so the path is **flattened a third time** and expanded for the real fill.

* Allocations: 3 + 2c (clone) + 2 x (flatten: points, contours) + 2 x (2-3c) (expands) + 2 x (each
  `fill_device_rect`: a Path, its cache and its expand, ~8 each before patch 06) + 2 commands of 496 B
  + 2 x 6 verts, per shadowed draw. Roughly 25 + 6c allocations per shadowed draw.
* Branchiness: three flattens' and two expands' worth.
* Working set: the path and cache twice, two transients of the padded bounds (GPU).
* GPU per shadow: clear + coverage fill + SourceIn fill + 2 blur passes (2 x area x taps) + composite, plus
  3-4 pass switches with tile store/load of the current target.
* **Counters**: shadows up to 8 per frame in BuseyBench (gemini-3-1-pro-preview-custom-tools), 0 in the
  icon set. The SVG mapping uses shadows only for feDropShadow, so the corpus does not stress this;
  Canvas-2D-style UIs with `shadowBlur` on every button do.
* ARM11: ~three fills' CPU per shadowed draw (modelled ~100-300 us each for a 50-point path) plus the GPU
  passes; a UI drawing 50 shadowed glyph-sized rects per frame would spend 15-45 ms of ARM11 time and
  ~200 pass switches here.
* Fix: the clone is unnecessary - the closure can borrow `path` (the cache `RefMut` is dropped before the
  call): patch 03 does that for fills and strokes (`|canvas| canvas.fill_path_internal(path, ..)`). The
  double re-flatten is a design cost of routing the shadow through the state's transform: the cheapest
  cure is to keep the flattened cache and translate its vertices (the coverage transform is a pure
  device-space translation of T, and fringes are translation-invariant), i.e. an `offset` parameter on the
  drawable emission rather than a new transform key; that is a moderate change and is not patched here.

### 3.6 `apply_layer_mask` (lib.rs:1825-1907) and `reserve_mask_images` (1803-1818)

Per masked layer. At `begin_layer` the mask reserves one (alpha) or two (luminance) store-sized
transients (two pool scans); at `end_layer` the mask pass does `save()`, three `set_render_target`s
(normalized, layer, previous), a `clear_rect`, a `fill_device_rect` to draw the mask image into layer
space (before patch 06: Path + cache + expand, ~8 allocations), a `filter_image` luminance-to-alpha pass
over the whole store (for luminance masks), and a whole-store DestinationIn `fill_path_internal` of a rect
path built inline (1892-1894: another ~8 allocations), then restores.

* Allocations: ~20 per masked layer before patch 06, ~12 after (the inline `store` rect at 1892 is not
  patched; it is the same pattern and should go through `fill_rect_internal` too).
* Branchiness: low. Working set: two store-sized transients (GPU).
* GPU per mask: normalize (store area, image sample) + convert (store area, one tap) + apply (store area,
  image sample, DestinationIn blend) = 3 x store area, 3-4 pass switches each storing/loading the layer
  store's tiles. For a viewport-sized layer at 640x480 that is ~1 Mpx and ~3.7 MB of tile traffic; at
  1080p 6.5 Mpx and 25 MB per mask.
* **Counters**: masks up to 2 per frame; kit and google-workspace-48px each carry one.
* ARM11: CPU ~0.1-0.2 ms per mask; GPU 3-8 ms per viewport-sized mask at 640x480 (model), 20-50 ms at
  1080p - a mask on a full-screen group is a frame's worth of GPU time at 1080p on this device.
* Fix: CPU - route both rect draws through `fill_rect_internal` (patch 06 covers the first; the second is
  a one-line follow-up). GPU - the normalize pass exists to decouple the mask image's storage orientation
  and placement from the layer; when the mask image already is layer-sized and layer-placed (the harness's
  `precapture_masks` makes it so) the normalize + convert could be one pass (luminance-to-alpha sampling
  the mask image directly through its own flags), saving one store-sized pass and two pass switches per
  mask. Not patched: it needs the orientation contract of #323 re-derived for a direct read.

### 3.7 `filter_image_chain` (lib.rs:1414-1500) and the parity pass

Per filtered layer (and per public chain call). Allocates the `passes` Vec (1432), folds adjacent color
matrices, then - the important part - appends an **identity color-matrix pass whenever the number of
storage flips is even** (1449-1452) to pin the "filtered result is stored upright" contract. A lone
Gaussian blur, which is what SVG's feGaussianBlur on a group maps to, has zero flips (its two passes
flip twice), so every blurred layer ran three passes: blur into a scratch (one pool scan, 1463-1476),
blur's second half, identity into the target. The identity pass reads and writes the whole store, clears
it first, and costs two pass switches with the target's tiles stored and loaded each time.

* Allocations: 1 (passes) + the scratch's pool scan per chain; the scratch itself is pooled.
* GPU per lone blur: 3 store-sized passes + a clear + 5 pass switches instead of 2 passes + 3 switches.
* **Counters**: other_filters (which counts the identity passes) was 57 on claude-fable-5-1, 113 on
  qwen3-8-2-4t-a95b, 92 on gemini-3-1-pro-preview: nearly every blurred layer in BuseyBench is a lone blur.
  Filter fragments over the 27 files at 640x480: 766 Mpx, of which the identity passes were ~245 Mpx.
* ARM11/VideoCore: at 1080p the identity passes alone were ~1.1 Gpx per BuseyBench frame set, i.e. a
  full second of the VideoCore's fill rate per file on the heavy ones.
* Fix: patch 02 - `end_layer` recognises the lone-blur chain, acquires the result with the capture's
  flags (PREMULTIPLIED | FLIP_Y), runs `filter_image` directly and composites it exactly like an unfiltered
  capture (the same thing `render_shadow` already does with its blur, 2773); the mask's parity flag follows.
  Measured over BuseyBench at 640x480: filter fragments 766 -> 521 Mpx, pass switches 9395 -> 7685,
  transient bytes held at flush 262 -> 191 MB summed (the blurred result shares the capture's pool class,
  so sibling layers reuse it), and one transient fewer per blurred layer (the four lib tests that counted
  three now count two - patch 02b). Output changes by at most 1 LSB on 7-969 pixels in 8 of 70 renders
  (the dropped pass's extra 8-bit unpremultiply/premultiply round trip), identical scores against the
  Chromium references (patch_equivalence.md).

### 3.8 Transient pool `acquire` (transient.rs:72-96; lib.rs:1309-1333) and `release_all` (109-126)

Per layer store, filtered target, chain scratch, shadow coverage and mask image: 2-4 acquires per layer.
`acquire` scans the `free` Vec linearly (80-84), and for **each** entry calls `images.info(id)` - a
`SlotMap` lookup (image.rs:244, 323) into a store that on a 200-layer frame holds ~15 transients plus the
gradient LUTs and lattices - comparing width, height and flags. A hit `swap_remove`s. `release_all` at the
flush walks every transient and, for each, walks `held` (`contains`) and does a SlotMap lookup for the
byte accounting.

* Allocations: none on a hit; one image (GPU) on a miss.
* Branchiness: a compare chain per entry, data-dependent.
* Working set: `free` (8 B per entry) plus a SlotMap slot (~50 B) per step, scattered.
* **Counters**: transient_acquires up to 432 per frame, of which 96 % are reuses; transient_scan_steps up
  to 4003 per frame (qwen3-8-2-4t-a95b), 2598 (qwen3-8-flash), 2124 (gemini-3-1-pro-preview): ~10 steps
  per acquire because the free list holds every size class the frame has used so far and the wanted class
  is often not at the end. **Profile**: 14 % of recording on qwen3-8-2-4t-a95b, 5 % on gpt-6-astra.
* ARM11: 4003 steps x (a SlotMap load that misses L1 + compares) ~ 4003 x 150-250 cycles = 0.6-1.0 ms per
  frame, and O(acquires x free-list length) - it grows quadratically with the number of distinct
  transient sizes a frame touches (shadows of many sizes, layers of many scissor sizes).
* Fix: bucket the free list by (width, height, flags) - an `FnvHashMap<(u32, u32, u32), Vec<ImageId>>` or,
  cheaper still on ARM11, keep `(width, height, flags, id)` tuples inline in `free` so the scan compares
  three integers from one contiguous 16 B stride without touching the SlotMap; the first makes acquire
  O(1), the second keeps it O(n) but with a 4-10x smaller constant. ~20 lines; not patched here because it
  needs `TransientPool::release` to know the info (pass it from the callers or look it up once there).

### 3.9 `Path::cache` (path.rs:176-197), `PathCache::new` (cache.rs:155-278), `expand_fill` (536-676), `expand_stroke` (679-798)

Per draw. `Path::cache` compares the transform's cache key and rebuilds the cache on a miss:
`PathCache::new` allocates `points` and `contours` and grows them by doubling (no reserve from the verb
count), transforms every point, flattens every cubic recursively (`tesselate_bezier`, 12 arguments, depth
<= 10, a `Point` push per subdivision leaf with an `approx_eq` dedup at 289-305), then a second pass per
contour computes edge directions and bounds. `expand_fill` (#336's version) first walks every contour to
compute `polygon_area` and, for a clockwise one, **reverses the points and recomputes directions**
(556-563), runs `calculate_joins` over every point (~15 branches each, 800-938), reserves, builds a
`triangle_fan_fill` Vec (587), converts it into `contour.fill` with a second `collect` (616-630: 3 verts
per fan step, so the fill is 3(n-2) vertices for an n-point contour), builds the fringe strip into
`contour.stroke` when antialiased, and finally **reverses the reversed contours back** (667-673). The
vertices are then copied a second time into `Canvas::verts` (`extend_from_slice`, lib.rs:2357-2364), and a
third time by the GL driver at `glBufferData` (opengl.rs:1020-1022, STREAM_DRAW, into a CMA buffer on vc4).

* Allocations per draw on a cache miss: 2 (points, contours; more with doubling) + per contour 2-3 (fan,
  fill, stroke) = ~5-8 for a one-contour path. On a hit (same transform, retained `Path`): 0 -
  `contour.fill/stroke` are `clear()`ed and refilled in place, though the `triangle_fan_fill` temp at 587
  is still allocated per contour per expand.
* Branchiness: high - tesselate_bezier's flatness test and recursion, add_point's dedup, calculate_joins's
  sign/flag logic, the bevel/miter selection in the fringe loop. These are the loops the 16 KB I-cache and
  the 3-entry return stack hurt most (section 2).
* Working set: points (40 B each) + fill (16 B x 3(n-2)) + fringe (16 B x 2n) per contour, i.e. ~120 B per
  point plus the copies; the Tiger's frame is 779 KB of vertices at 640x480 (1.1 MB at 1080p), three
  times copied = 2.3-3.3 MB of memory traffic per frame - 5-10 ms of the ARM11's memcpy bandwidth alone.
* **Counters**: path_cache_rebuilds up to 668 per frame (gpt-6-astra) - the harness, like an
  immediate-mode app, builds a fresh `Path` per SVG node per frame, so every draw is a miss; expand_fills
  up to 349 and expand_strokes up to 365 per frame; allocations 1,093-5,686 per BuseyBench frame,
  105-2,675 per icon frame (Tiger 2,675: 226 fills + 78 strokes = 8.8 allocations per draw), of which
  the harness's own `Path` building is 10-1,012. **Profile**: 40-55 % of recording.
* ARM11: the compute-bound part of the factor (22-35x): the Tiger's 0.53 ms becomes ~12-19 ms of
  tessellation plus ~5-10 ms of copying; a 300-node icon at 30-60 fps is only possible with retained
  `Path`s (cache hits) - which femtovg supports and the harness deliberately does not use.
* Fix (cheapest, in-library): reserve `points` from `verbs.len()` and `contours` from the MoveTo count
  in one pre-pass (removes the doubling reallocs, ~3 per path); write the triangle list directly instead
  of fan-then-collect (halves the per-contour allocations and one copy); for #336's normalization,
  compute the fan in reversed index order instead of physically reversing the points twice (removes two
  passes over every clockwise contour). The retained-buffer PathCache reuse work (the separate churn PR
  in progress: 620 -> 144 allocations per frame) is the larger fix and is the one to prioritise for this
  device; none of it is patched here.

### 3.10 `append_cmd` and the command list (lib.rs:1064-1082, 857-870; renderer.rs:95-105)

Per command. `Command` is **496 bytes** (derived from the command_bytes counter: capacity x size; a
`ConcaveFill` or `StencilStroke` carries two `Params` of 52 f32 each by value, params.rs:10-30) plus a
`Vec<Drawable>` (48 B per drawable). `flush_to_output` hands the Vec to the renderer by value
(`std::mem::take`, 862) and starts the next frame from an **empty** Vec, so a 1,407-command frame regrows
it through 11 doublings: ~1.4 MB of reallocation copies per frame on top of the 700 KB of command records
written once.

* Allocations: 11 reallocs per frame for a ~1,400-command frame (record_reallocs counts them among the
  1,700-3,900 per frame), plus one `Vec<Drawable>` per drawable-bearing command.
* Branchiness: low. Working set: 700 KB of records, streamed once by the recorder and once by the
  renderer - 44x the L1, so every 496 B record is 15-16 cache-line misses to write and to read.
* ARM11: the regrowth alone is 1.4 MB x (300-600 MB/s) = 2-5 ms per BuseyBench frame; reading the
  records back in `render` is another 700 KB of misses.
* Fix: patch 05 - `flush_to_output` replaces the Vec with one of `with_capacity(commands.len())` (one
  allocation, no regrowth; measured reallocs -11 per frame and record_alloc_bytes -1.0 to -2.1 MB per
  frame on the 1,000+ command files). The record size itself is the bigger item: moving `Params` out of
  the enum into a side `Vec<Params>` indexed by the command (a `ConcaveFill` becomes two u32 indices)
  shrinks `Command` to ~80 B and cuts the traffic six-fold; that is an internal refactor of both backends'
  `render` loops and is not patched here.

### 3.11 Turbulence lattice cache (lib.rs:1292-1306; turbulence.rs:69-131)

Per turbulence filter pass. A 4-entry LRU keyed by seed, linear scan (trivial); on a miss
`lattice_texels` runs the spec's PRNG (`build_lattice`: 256 x 4 x 2 `random` calls in i64 plus 256
normalizations in f64) and encodes 512 x 256 RGBA8 texels (131,072 texels, 4 f64 rounds each), then
uploads 512 KB; the evicted lattice is deleted after the next flush.

* Allocations: 1 (the 512 KB texel Vec) + the image, per miss; 0 per hit.
* Branchiness: low (fixed loops). Working set: 512 KB (streams through the 16 KB L1).
* **Counters**: turbulence_filters <= 2 per file; seeds are stable across frames, so the corpus pays
  the build once (frame 0) and nothing after.
* ARM11: the build is ~0.5 M f64 operations plus 131 K encodes: on VFP11's double path (~2-3x slower than
  single) ~15-25 ms per new seed, plus the 512 KB upload; a scene that animates `seed` per frame is a
  frame budget per frame. The GPU side is the real cost: the shader takes 8 lattice taps per octave per
  pixel (`filter_taps` model: area x 8 x octaves); a full-frame 4-octave turbulence at 640x480 is 9.8 M
  dependent, nearest-filtered taps - ~20 ms at the model's 0.5 Gtap/s.
* Fix: nothing needed for stable seeds. For animated seeds, build the lattice in `f32` (the encode
  quantizes to 1/255 anyway) and keep the capacity; or animate `base_frequency` / an offset instead of
  the seed. GPU: cap octaves on this device (each octave is a full extra tap set).

### 3.12 `fill_device_rect` - every layer composite, shadow blit and mask draw (lib.rs:1787-1797)

Not in the track's list, but the counters put it above most that are. `end_layer` (1739), `render_shadow`
(2767, 2799) and `apply_layer_mask` (1859) all composite through `fill_device_rect`, which built a `Path`,
`rect()`ed it, and called `fill_path_internal`: `PathCache::new` (points + contours allocations, a
transform of 4 points, directions and bounds), `expand_fill` (polygon_area, calculate_joins over 4 points,
fan Vec, collect), `path_fill_is_rect`, and only then either the unclipped image blit or a `ConvexFill` -
all to produce six vertices that are the rect's corners.

* Allocations: ~8 per composite (Path verbs + coords, cache points + contours, fan, fill, drawables Vec,
  plus a `State` push where `save()` surrounds it).
* **Counters**: expand_fills 349 on qwen3-8-2-4t-a95b against ~150 real SVG fills: 200 of the frame's
  expansions were layer composites; the 200-layer files spent ~1,600 of their 4,869-5,686 allocations
  here. **Profile**: `end_layer` 11-16 % of recording.
* ARM11: ~8 mallocs + a 4-point flatten + expand per layer ~ 30-60 us modelled, x 200 layers = 6-12 ms
  per BuseyBench frame; for an icon with a couple of groups it is 2-3 % of recording.
* Fix: patch 06 - `fill_rect_internal` transforms the four corners, does the same shadow / early-out /
  unclipped-blit decisions as `fill_path_internal`, and otherwise emits the `ConvexFill` with the six fan
  vertices `expand_fill` would have produced (same order, same winding normalization for mirrored
  transforms). **Measured**: allocations over the 27 BuseyBench files at 640x480 65,394 -> 47,817 per
  frame set (-27 %; qwen3-8-2-4t-a95b 4,700 -> 3,187, gpt-6-astra 5,616 -> 4,474, claude-fable-5-1
  3,843 -> 2,589), record_alloc_bytes 37 -> 35 MB summed, Mac recording time 10.08 -> 9.16 ms summed
  (claude-fable-5-1 0.655 -> 0.457 ms, qwen3-8-2-4t-a95b 0.771 -> 0.551 ms); bit-identical on all 70
  renders (patch_equivalence.md); 105/105 lib tests.

### 3.13 The GL backend's per-command and per-target costs (opengl.rs) - what the Pi pays that this Mac does not

The measurements above stop at the command list; on the Pi the GL backend and Mesa's vc4 driver run on
the same ARM11. Per command (`render`, 989-1096): `set_composite_operation` (a `glBlendFuncSeparate`),
`set_uniforms` (660-700: `UniformArray::from(paint)` packs the 52 floats and `set_config` uploads them as
11 vec4 uniforms - a `glUniform4fv` the vc4 driver turns into a shader-uniform stream rewrite - then two
`glBindTexture`s), a program switch when the shader type changes (`select_main_program`, 941-972: a
`glUseProgram` plus four texture rebinds and a view upload), and 1-3 `glDrawArrays`. A concave fill is
two uniform uploads and three draws; a stencil stroke two uploads and three draws; a clip fill three
draws. Per image render target: `set_target` (722-765) creates a `Framebuffer` on first use with a
`STENCIL_INDEX8` renderbuffer (framebuffer.rs:43-52; on vc4 a packed 32-bit Z/S tile buffer, 4 B/px), a
completeness check, and a `glViewport`; each switch is a vc4 render job boundary (tile store + load of the
target). Per Gaussian blur (852-928): `images.alloc` of a source-sized scratch texture (889), its FBO and
stencil renderbuffer, two draws, `images.remove` (920) - a CMA buffer allocation and free per blur per
frame, 113 times per frame on qwen3-8-2-4t-a95b.

* Model: 60 us per draw call, 150 us per pass switch, 600 us per scratch texture (ranges in model.md):
  BuseyBench 376-2,461 draw calls, 94-984 pass switches (after patches 01-02: 89-768) and 4-113 blurs per
  frame -> 45-320 ms of driver CPU per frame, more than femtovg's own recording (12-36 ms) on every
  BuseyBench file; icons 25-184 draws (Tiger 869) -> 1.5-11 ms (Tiger 52 ms).
* Fix: patch 04 keeps the four most recently used blur scratch sizes alive across frames
  (`blur_scratches`, MRU) instead of allocating and freeing per blur - removes the per-blur CMA
  allocation, FBO creation and completeness check. Type-checks on the GL backend; not measurable on this
  Mac (wgpu). Caveat for the Pi: four cached scratches at 1080p are 4 x (8.3 MB color + 8.3 MB stencil) =
  66 MB of GPU memory outside the transient budget; set BLUR_SCRATCH_CAPACITY to 1-2 for a 64-128 MB
  gpu_mem, or better, make the Canvas acquire the blur's intermediate from the transient pool and record
  the blur as two `RenderFilteredImage` passes, so both backends stop allocating per blur and the scratch
  is budgeted (a moderate change, not patched).

## 4. The three that hurt most on an ARM11, and the cheapest fix for each

1. **Allocation churn in the recording path** (3.9 + 3.12 + 3.10): 1,000-5,700 mallocs and 1-6 MB of
   allocation traffic per frame, a fifth to a quarter of recording on every file even on this Mac's
   allocator; on an ARM11 with no L2 each malloc/free is a pointer chase into DRAM (60-100x). Cheapest
   fixes, in order of yield: patch 06 (the layer/shadow/mask composites no longer build and tessellate a
   `Path`: -27 % allocations over BuseyBench, -10 % recording time, zero pixel change), patch 05 (no
   command-Vec regrowth: -11 reallocs and -1 to -2 MB of memcpy per big frame), and the PathCache reuse
   work already in progress for the per-draw caches; in the library, `PathCache::new` reserving from the
   verb count and `expand_fill` writing its triangle list directly (3.9).
2. **Full-target stencil quads and the redundant parity pass** (3.1, 3.2, 3.7): GPU-side, but they are
   what makes the clip and blur features expensive out of proportion on a 1 Gpix/s tiler with a shared
   1.5 GB/s bus - 12-75 Mpx of stencil quads and ~245-1,100 Mpx of identity passes per BuseyBench frame
   set. Patches 01 + 02 + 03: clip quads 111 -> 12.6 Mpx (640x480) and 714 -> 63 Mpx (1080p), filter
   fragments 766 -> 521 Mpx, pass switches 9,395 -> 7,685, transient bytes -27 %; the modelled Pi frame
   time of the BuseyBench median drops 931 -> 844 ms at 640x480 and 5.8 -> 5.3 s at 1080p (still
   non-interactive: section 5), and the clipped icons gain 1-2 ms of a 5-25 ms frame.
3. **Linear scans that grow with the frame** (3.8, and the driver-side per-blur allocation in 3.13): the
   transient pool's free-list scan is 14 % of recording on the 200-layer file and O(acquires x sizes);
   the GL blur scratch is a CMA allocation per blur. Cheapest fixes: bucket the free list by
   (w, h, flags) or keep the info inline in `free` (~20 lines, not patched); patch 04 for the blur scratch
   with the capacity caveat above.

The `clip_active` scan (3.3), the `effects.clone()` (3.4) and the lattice cache (3.11) are real but
measured at microseconds per frame on this corpus; they are listed so the numbers are on record.

## 5. What this means for the Pi Zero (from model.md / patched_all6.md, central assumptions)

* Non-pathological content at 640x480 (the icon set): 5-25 ms modelled frames for six of the eight
  files (clipdemo, splash-logo, duckduckgo at 60 fps; kit, mr-settodefault, fox at 30 fps), GPU-bound on
  the layered ones and driver/CPU-bound on the draw-heavy ones; the Tiger (869 draw calls) is ~77 ms
  (10-30 fps, driver per-draw cost dominant); google-workspace-48px is ~59 ms because the harness opens a
  viewport-sized blurred + masked layer (its blur is 2 x 0.26 Mpx x 25 taps per frame) - an application
  scissoring the group to its 48 px bounds would be at 60 fps. At 1080p the same set is 17-136 ms:
  splash-logo and fox at 30 fps, the rest 10-30 fps or worse, the two viewport-layer files
  non-interactive.
* BuseyBench: every file is non-interactive on this device at either resolution - 300-3,600 ms at
  640x480 and 2-20 s at 1080p modelled, GPU fill and tile traffic dominated (hundreds of Mpx of layer
  clears, captures, blur taps and composites per frame; 46-1,000 Mpx of pass store/load); the CPU side
  (12-36 ms femtovg + 45-320 ms driver) would not be the limit even if it were free. The patches take
  10-20 % off; nothing on the CPU side changes the verdict.
* RAM (ram.md): CPU-side RSS on the Pi is modelled at 15-32 MB for everything in the corpus - not a
  constraint; GPU memory is: 4-41 MB at 640x480 (fits gpu_mem=64), 24-190 MB at 1080p (BuseyBench does
  not fit gpu_mem=64 and mostly not 128), the 256 MiB default transient budget is larger than the whole
  GPU split and the documented 32-48 MiB is only coherent if the stencil attachment (4 B/px on vc4) is
  counted alongside the color.

## 6. Patch status

| patch | what | measured effect (this Mac, corpus) | output | tests |
|---|---|---|---|---|
| 01-clip-bounded-quads | arm/resolve/disarm quads bounded to the clip's armed rect | clip quads 111 -> 12.6 Mpx (BuseyBench 640x480), 714 -> 63 Mpx (1080p); icons 6.1 -> 1.9 Mpx | pixel-identical (70/70) | lib 105/105; full suite (wgpu GPU tests included) all green, test_full_patched.log |
| 02-lone-blur-no-parity-pass (+02b tests) | a lone Gaussian blur keeps the capture's parity; no identity pass, one transient fewer | filter Mpx 766 -> 521, pass switches 9,395 -> 7,685, transient MB 262 -> 191 (BuseyBench 640x480) | <= 1 LSB on 7-969 px in 8/70 renders; Chromium scores unchanged | 4 lib tests updated (02b) |
| 03-clip-entries-keep-fans-no-path-clones | ClipEntry keeps device-space fans; replay copies them; shadows borrow the path | allocations -1 to -170 per frame on clipped files | pixel-identical | lib 105/105 |
| 04-gl-blur-scratch-cache | GL backend reuses blur scratch textures (MRU 4) | not measurable here (wgpu); type-checks | n/a | n/a; capacity caveat in 3.13 |
| 05-size-command-vec-for-next-frame | next frame's command Vec pre-sized to this frame's length | reallocs -11/frame, alloc bytes -1 to -2 MB/frame on 1,000+ command files | pixel-identical | lib 105/105 |
| 06-fill-device-rect-direct-triangles | composites/shadow blits/mask draws emit their two triangles directly | allocations 65,394 -> 47,817 (-27 %) and record ms 10.08 -> 9.16 summed over BuseyBench 640x480 | pixel-identical (70/70 vs 01-05) | lib 105/105 |

The individual files 02, 03 and 05 are cumulative (each includes the ones before it, as left by the
previous attempt); `pz-all.cumulative.patch` is the whole set including 02b and 06 and is exactly the
working tree of /private/tmp/wt-pz against commit 0a56986 (verified with `git apply --check --reverse`).
Nothing is committed or pushed.
