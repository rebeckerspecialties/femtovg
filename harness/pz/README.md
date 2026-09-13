# Will the open stack work well on a Raspberry Pi Zero? - measurements, model, review, RAM

Question: with #323 masks, #324 clip paths, #336 winding, #338 turbulence and #339 hairline on top of
merged #322 layers (transient pool), how does femtovg behave on a Pi Zero (ARM11 1 GHz, 16 KB L1, no L2,
VideoCore IV GLES2 ~1 Gpix/s, ~1.5 GB/s shared, 256 MB usable) for non-pathological SVG content, with
BuseyBench as the stress end?

## Answer in brief

* **Non-pathological content at 640x480 works** (modelled, central assumptions): of the eight
  demo-assets/Tiger files, three render at 60 fps (clipdemo 3 ms, splash-logo 5 ms, duckduckgo 8 ms),
  three at 30 fps (kit 23 ms, mr-settodefault 17 ms, fox 20 ms), and two at 10-30 fps for reasons the
  application controls: google-workspace-48px (59 ms) because the harness opens a viewport-sized blurred
  and masked layer instead of scissoring the 48 px group, and the Tiger (77 ms) because its 869 draw calls
  are driver-CPU-bound on an ARM11 (52 ms of the 77 are the modelled vc4 per-draw cost; femtovg's own
  recording is 24 ms). At 1080p the same set is 17-136 ms: two files at 30 fps, four at 10-30 fps, the two
  viewport-layer files non-interactive.
* **BuseyBench is non-interactive on this device at either resolution**: 300-3,600 ms per frame at
  640x480 and 2-20 s at 1080p (modelled), because it is GPU fill and tile-traffic bound - 27-250 Mpx of
  fragments and 45-400 Mpx of pass store/load per frame at 640x480 (measured counts) against a 1 Gpix/s
  tiler on a 1.5 GB/s bus - and the CPU (12-36 ms femtovg + 45-320 ms driver, modelled) would not be the
  limit even if it were free. The patches here take 10-20 % off; nothing changes the verdict.
* **CPU RAM is not a constraint** (15-32 MB expected process RSS on the Pi for anything in the corpus);
  **GPU memory is**: 4-41 MB at 640x480 fits gpu_mem=64, but 1080p BuseyBench needs 73-190 MB, and the
  256 MiB default transient budget exceeds the whole GPU split. The documented 32-48 MiB is coherent only
  if the stencil attachment every image target carries (4 B/px on vc4, not budgeted today) is counted.
* **The stack's hot paths are mostly fine on an ARM11; three things hurt** (review.md section 4):
  allocation churn in recording (1,000-5,700 mallocs per frame; patch 06 removes 27 % of BuseyBench's,
  patch 05 the command-Vec regrowth), full-target stencil quads and the redundant blur parity pass on the
  GPU side (patches 01-03: clip quads 111 -> 12.6 Mpx, filter fragments 766 -> 521 Mpx over BuseyBench
  at 640x480), and the transient pool's linear free-list scan (14 % of recording on a 200-layer frame;
  fix described, not patched). Six patches are provided; all pixel-exact except patch 02 (<= 1 LSB on
  8/70 renders, Chromium scores unchanged); 309/309 tests pass on the patched tree.

## What is measured and what is modelled

Measured (this Mac, Apple M4 Max, wgpu/Metal, release build, median of frames 2-6 of a 6-frame run):
per-frame command counts by type, fragments per pass type computed from the recorded triangles, pass
switches and tile store/load areas, vertex bytes, heap allocations (a counting global allocator in the
harness), Rust heap live/peak, transient bytes, femtovg recording CPU time (harness usvg->Path conversion
subtracted), wgpu encode time, GPU submit+wait time, RSS (`ps`) and `/usr/bin/time -l` peak RSS, and a
`sample` profile of the recording phase. Modelled: every Pi Zero number - fragment rates per pass type,
bus bandwidth, ARM11 slowdown factor (45x central, 30-60x), vc4 driver per-draw/per-pass costs, stencil
bytes per pixel, EGL baseline RSS - with the assumption table in model.md and the justification in
review.md section 2.

## Files

| file | what |
|---|---|
| measurements.md / measurements.json | step 2: per file x framing measured table (commands, full-target stencil quads and Mpx, pixels touched, tile store/load, blurs, transient MB, vertex KB, allocations, record/encode/GPU ms, heap, RSS); JSON has every counter |
| model.md / model.json / model_pi.py | step 3: Pi Zero model, assumption table (central/optimistic/pessimistic), per-file GPU/CPU/frame ms, fps verdicts, GPU memory |
| review.md | step 4: hot-path review with file:line references, per-path allocation/branchiness/working-set/frequency, ARM11 cost model justification, top 3 + cheapest fixes, patch status |
| ram.md | step 5: femtovg's own footprint vs process baseline vs GPU memory; expected Pi RSS; transient budget coherence |
| profile/summary.md, profile/*.sample.txt | `sample` profiles of the recording phase (Tiger, gpt-6-astra, qwen3-8-2-4t-a95b) |
| patched_all6.md / .json | before/after all six patches, both framings, measured counts and modelled Pi times (patched_all5.md: patches 01-05; patched_640x480.md: 01-03 only, from the previous attempt) |
| patch_equivalence.md | pixel-for-pixel comparison of patched vs unpatched renders (70 renders), attribution of the <= 1 LSB deltas to patch 02, Chromium-closeness check, and the pre-existing multi-frame stencil artifact found on the way |
| 01-clip-bounded-quads.patch | clip arm/resolve/disarm quads bounded to the armed rect instead of the whole target |
| 02-lone-blur-no-parity-pass.cumulative.patch (+ 02b-lone-blur-pool-class-tests.patch) | a lone Gaussian blur layer skips the identity parity pass and one transient; the four lib tests that counted the old transient count |
| 03-clip-entries-keep-fans-no-path-clones.cumulative.patch | ClipEntry keeps device-space fans (no Path clone, no re-expansion on replay); shadow closures borrow the path |
| 04-gl-blur-scratch-cache.patch | GL backend keeps blur scratch textures across frames (capacity caveat in review.md 3.13) |
| 05-size-command-vec-for-next-frame.cumulative.patch | next frame's command Vec pre-sized (no regrowth copies) |
| 06-fill-device-rect-direct-triangles.patch | layer composites, shadow blits and mask draws emit their two triangles directly instead of building and tessellating a Path |
| pz-all.cumulative.patch | the whole set (= working tree of /private/tmp/wt-pz vs commit 0a56986); pz-all-5.cumulative.patch is the set before 02b/06 |
| test_full_patched.log | `cargo check` (GL backend, with and without debug_inspector) and `cargo test --release --features wgpu,debug_inspector --no-fail-fast` on the patched tree: 30 targets, 309 passed, 0 failed (24 wgpu GPU test binaries) |
| run_matrix.py, model_patched.py | the measurement driver and the before/after modeller |
| bin/ | the three harness binaries used for the equivalence checks (all five patches, all six, and all six minus patch 02's branch) |
| src_head/ | copies of the reviewed sources at commit 0a56986, for the line numbers in review.md |
| assets/ | the eight non-pathological SVGs (demo-assets top-level files + Ghostscript_Tiger) |

Files 02, 03 and 05 are cumulative as the previous attempt left them (each contains the earlier ones);
02b and 06 are standalone hunks on top of pz-all-5.

## Worktree and reproduction

* Worktree /private/tmp/wt-pz, branch pz-measure, commit 0a56986 (corpus-all3 + PZ_STATS
  instrumentation: examples/_logos_full.rs, debug_inspector counters in src/lib.rs, src/path.rs,
  src/path/cache.rs, src/image.rs). The working tree additionally carries pz-all.cumulative.patch
  (uncommitted, as asked). Nothing was pushed.
* Build: `CARGO_TARGET_DIR=/private/tmp/wt-pz/target cargo build --release --features wgpu,debug_inspector --example _logos_full`
* Measure: `S=<scratchpad> BIN=<binary> python3 run_matrix.py [busey@640x480 icons@640x480 busey@1080p icons@1080p]`
  (env per run: FRAME_W/FRAME_H/BOX/BOX_X/BOX_Y for the framing, SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1
  PZ_STATS=1 FRAMES=6); then `S=<scratchpad> python3 model_pi.py` (unpatched) or
  `python3 model_patched.py <patched.json> <out.md>`.
* Profile: `FRAMES=N <binary> 1.0 out.ppm file.svg & sample $! 12 1 -mayDie -file out.txt`.
