# RAM on a Raspberry Pi Zero: femtovg's footprint vs. the process baseline vs. GPU memory

All "measured" numbers are from `measurements.json` (this Mac, release build, median of steady-state
frames 2-6; `heap` = the counting global allocator in `_logos_full.rs`, exact bytes live on the Rust
heap; `images` = texel bytes of every image in the `ImageStore`; RSS = `ps rss` of the process).
"Pi" numbers are modelled from those counts with the assumptions stated inline.

## 1. What femtovg itself holds (CPU heap)

| structure | how it scales | icons @640x480 (min/median/max) | BuseyBench @640x480 | BuseyBench @1080p |
|---|---|---|---|---|
| Rust heap live after a frame (whole process: usvg tree + fontdb + canvas) | constant | 0.81 / 0.89 / 2.07 MB | 1.18 / 1.50 / 2.42 MB | 1.25 / 1.58 / 2.70 MB |
| Rust heap peak during recording | + per-frame command/vertex/path-cache growth | 0.85 / 0.97 / 2.46 MB | 1.38 / 2.01 / 3.44 MB | 1.46 / 2.09 / 3.73 MB |
| `commands: Vec<Command>` (capacity x ~600 B + drawables) | per command | 8 / 16 / 262 KB | 130 / 505 / 1031 KB | same |
| `verts: Vec<Vertex>` (16 B each; capacity retained across frames) | per vertex | 27 / 77 / 779 KB | 148 / 213 / 573 KB | 223 / 292 / 776 KB |
| per-frame allocation traffic (bytes malloc'd during recording) | per draw | 0.2 / 0.5 / 5.0 MB | 1.2 / 2.3 / 5.4 MB | 1.6 / 2.7 / 6.5 MB |

Three things worth knowing about that table:

* The heap is small and flat: 1-4 MB including the harness's usvg tree and font database. femtovg's
  own retained state after a frame is the vertex Vec capacity, the state stack, gradient LUTs, the
  transient pool's id lists and the turbulence lattice ids - tens to hundreds of KB.
* `commands` is *not* retained: `flush_to_output` does `std::mem::take(&mut self.commands)` and hands
  the Vec to the renderer by value (src/lib.rs:743-751 on corpus-all3), so it is re-grown from zero
  every frame - for a 1407-command BuseyBench frame that is ~11 doublings and ~1.7 MB of memcpy per
  frame; on an ARM11 (~300-600 MB/s memcpy from DRAM, no L2) that is 3-6 ms of pure copying. See
  review.md item 10 and `05-size-command-vec-for-next-frame.cumulative.patch`.
* The per-frame allocation traffic (1-6 MB, 1,000-5,700 mallocs on BuseyBench, 105-2,700 on the icon
  set) is path caches being rebuilt: the harness, like an immediate-mode app, builds a fresh `Path`
  per SVG path per frame, and each fill then allocates its `PathCache` (points, contours) and expanded
  vertex Vecs (review.md item 9). An app that keeps its `Path`s and does not change their transform
  pays none of this after the first frame.

## 2. The process baseline

* This Mac (wgpu + Metal): 15.6 MB RSS right after device creation, +3-4 MB after the usvg tree, then
  RSS = 24-31 MB for the icon set but **86-672 MB for BuseyBench at 640x480** (99-598 MB at 1080p) with
  a 1.5-2.5 MB Rust heap and 6-17 MB of images. The excess (median 178 MB on BuseyBench, 24 MB on
  icons) is Metal residency: per-frame command encoding of 250-1400 commands, pipeline-state objects,
  and the scratch texture `gaussian_blur_filter` creates per blur (src/renderer/wgpu.rs:924) whose
  destruction is deferred until the GPU has finished. Sampled per frame it climbs 279 -> 348 MB over 12
  frames on gpt-6-astra and 526 -> 661 MB on qwen3-8-2-4t-a95b while heap and transients stay flat, so
  it is driver-side residency, not a femtovg leak. **None of this transfers to the Pi**, which runs the
  GL backend on Mesa vc4.
* Pi Zero (GLES2 through EGL on Mesa vc4, no X): a small EGL application's RSS is 12-25 MB (libGLESv2 +
  libEGL + libdrm + Mesa's shader compiler ~6-10 MB of text, plus its heap). *Assumed*, not measured
  here; the range covers Raspbian buster/bullseye reports. femtovg's shaders are compiled once
  (12 program variants), a few hundred KB of driver heap.

## 3. Expected process RSS on the Pi Zero (CPU side, modelled)

| | baseline (assumed) | Rust heap (measured, Mac) | commands + verts + path caches | expected RSS |
|---|---|---|---|---|
| icon set (any of the 8 files) | 12-25 MB | 1-2.5 MB | 0.1-1.5 MB | **15-30 MB** |
| BuseyBench (worst file) | 12-25 MB | 2.5-4 MB | 1.5-2.5 MB | **17-32 MB** |

Both are an order of magnitude under the ~256 MB the process can use. CPU RAM is not the constraint on
this device; the constraint is on the other side of the split.

## 4. GPU memory (CMA, carved out by `gpu_mem`, NOT in the process RSS)

Modelled from the measured image bytes with VideoCore IV facts: every image render target femtovg draws
into gets a stencil attachment (GL backend: `STENCIL_INDEX8` renderbuffer per FBO,
src/renderer/opengl/framebuffer.rs:43-52; on vc4 a stencil-only renderbuffer is backed by the packed
32-bit Z/S tile format, so 4 B/px - the model's central value; 1 B/px optimistic). The screen is
double-buffered color + one Z/S.

| component | icons @640x480 (min/median/max) | BuseyBench @640x480 | icons @1080p | BuseyBench @1080p |
|---|---|---|---|---|
| images in the store (transients + masks + LUTs + lattices) | 0 / 0.5 / 6.2 MB | 6.3 / 10.3 / 17.5 MB | 0 / 2.3 / 28 MB | 19.7 / 39.3 / 78.3 MB |
| of which transient pool at flush | 0 / 0.5 / 5.1 MB | 6.3 / 10.1 / 13.5 MB | 0 / 2.3 / 20.3 MB | 19.7 / 36.5 / 57.3 MB |
| stencil attachments for those targets (4 B/px) | 0 / 0.5 / 6.2 MB | 6.3 / 10.3 / 17.5 MB | 0 / 2.3 / 28 MB | 19.7 / 39.3 / 78.3 MB |
| screen (2 x color + Z/S) | 3.5 MB | 3.5 MB | 23.7 MB | 23.7 MB |
| blur scratch (one store-sized texture + stencil, allocated per blur by the GL backend) | 0 / 0 / 2.5 MB | 1.7 / 2.3 / 2.6 MB | 0 / 0 / 10 MB | 7.1 / 9.8 / 10.4 MB |
| vertex buffer | 0.03 / 0.09 / 1.1 MB | 0.2 / 0.3 / 0.8 MB | 0.06 / 0.16 / 1.5 MB | 0.2 / 0.4 / 1.1 MB |
| **total** | **3.6 / 5.1 / 18.6 MB** | **18.7 / 26.6 / 40.7 MB** | **23.8 / 29.1 / 90.2 MB** | **73.4 / 112.5 / 188.6 MB** |

Reading: at 640x480 everything fits a `gpu_mem=64` split (icons 4-19 MB, BuseyBench 19-41 MB). At 1080p
the icon set fits `gpu_mem=64` except the two files that open a viewport-sized blurred layer
(google-workspace-48px 90 MB, kit 66 MB: their layers are sized by the harness's 1080-px viewport
scissor, not the group's bounds), and **no BuseyBench file fits `gpu_mem=64` (min 73 MB) and most do not
fit `gpu_mem=128` (median 112 MB, max 189 MB)** with the default budget - the pool holds 20-57 MB of
color at the flush and the stencil attachments double it.

## 5. Is the 256 MiB default transient budget coherent on this device?

No, as a default it is not: 256 MiB is larger than the whole GPU split (64-128 MB) and equal to the whole
CPU-usable RAM. The budget is only a ceiling - the pool never holds more than the frame's peak nesting
need (measured: 13.5 MB max at 640x480, 57.3 MB max at 1080p across the corpus, `transient_at_flush`) -
so on non-pathological content the default never binds. But a ceiling above physical GPU memory means
the failure mode on the Pi is a driver allocation failure (`glTexImage2D` -> `GL_OUT_OF_MEMORY`, or the
kernel CMA allocator failing under the vc4 driver) instead of the graceful pass-through the budget exists
to provide. Two corrections make the documented 32-48 MiB recommendation coherent:

1. **Set it** (the API exists: `set_transient_image_budget`; the docs say 32-48 MiB for this device). The
   1080p ladder in the harness README shows 48 MiB renders the corpus identically (1 of 2,373 layers pass
   through); at 640x480 even 16 MiB covers every corpus file with room to spare (max 13.5 MB held).
2. **Count the stencil attachment.** The budget counts color texels only (`transient.rs:88`,
   `width * height * 4`). On the GL backend every transient that becomes a render target - all of them -
   also owns a `STENCIL_INDEX8` renderbuffer, 1-4 B/px depending on the driver's Z/S layout (4 on vc4). A
   48 MiB budget is therefore 60-96 MB of GPU memory on the Pi, on top of the 3.5 MB (640x480) or 24 MB
   (1080p) screen buffers and the blur scratch. With `gpu_mem=128` and a 1080p framebuffer the honest
   budget is ~32 MiB (which costs 1.90% / 0.914% vs. Chromium in the README ladder, 57 layers passing
   through); with `gpu_mem=64` it is ~16 MiB at 640x480 and 1080p BuseyBench is simply out of reach.
   Cheapest fix: let `TransientPool::acquire` charge `width * height * (4 + stencil_bpp)` where the
   renderer reports `stencil_bpp` (a `Renderer` trait default of 0, 1 for wgpu's `Stencil8`, 4 for GL on
   vc4 or 1 elsewhere), so the number the app sets is the number the GPU pays.

The mask images the harness captures are frame-sized and caller-owned (not transients), so a masked
scene adds 1.2 MB (640x480) or 8.3 MB (1080p) per mask plus the same again for its stencil; the corpus
has at most 2 per file.
