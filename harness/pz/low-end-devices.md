# Low-end targets beyond the Pi Zero: iPhone XS (Apple A12), Amlogic S905X2 (Mali-G31 MP2) and S905 (Mali-450 MP3) TV boxes - modelled frame times for BuseyBench and the icon set

Date 2026-09-16. Extends harness/pz/model_pi.py (the Pi Zero cost model) to three more device profiles with the same structure: per-pass-type fragment rates, a texture-tap rate, a bus bandwidth for the tile store/load traffic, a CPU slowdown factor against this Mac for femtovg's recording, and per-draw / per-pass / per-texture-allocation driver costs, plus one added GPU-side term per render-pass boundary. Inputs are the measured per-frame counts in harness/pz/measurements.json (this Mac, Apple M4 Max, release build, median of frames 2-6 of the corpus-all3 tree before the #323 review fixes; 70 rows = 27 BuseyBench + 8 icon files x the 640x480 and 1080p framings). Model: `model_devices.py` (harness/pz/, copied from the scratchpad); every number below is modelled unless marked measured. `frame` = max(CPU, GPU) under the central assumptions (perfect overlap); the range in parentheses is optimistic-overlapped to pessimistic-serial. Classes: 60 fps <= 16.7 ms, 30 fps <= 33.3 ms, 10-30 fps <= 100 ms, otherwise non-interactive.

## Answer in brief

* **iPhone XS (A12, Metal via wgpu)**: the only one of the three new targets where BuseyBench is interactive at all, and only at 640x480: 640x480: icons median 1.1 ms (8/0/0/0 at 60/30/10-30/non), BuseyBench median 80 ms, p90 220 ms, worst 365 ms (0/3/13/11); 1080p: icons median 3.4 ms (7/1/0/0 at 60/30/10-30/non), BuseyBench median 424 ms, p90 1.2 s, worst 1.9 s (0/0/0/27). At 1080p every BuseyBench file is over 100 ms: 272-1,754 Mpx of tile store/load and 0.35-7.87 Gtaps of blur per frame against a 34 GB/s bus and a 4-core GPU, plus 100-1,000 render-pass boundaries; CPU recording is 3.1x this Mac and never the limit (GPU/CPU >= 14x). The icon set is 60 fps at both framings except google-workspace-48px at 1080p (21 ms, 30 fps).
* **Android TV box, S905X2 / Mali-G31 MP2 (GLES 3.2)**: 640x480: icons median 9.4 ms (6/0/2/0 at 60/30/10-30/non), BuseyBench median 620 ms, p90 1.8 s, worst 2.9 s (0/0/0/27); 1080p: icons median 30 ms (1/3/3/1 at 60/30/10-30/non), BuseyBench median 3.6 s, p90 10.9 s, worst 16.8 s (0/0/0/27); 4k: icons median 103 ms (0/0/2/6 at 60/30/10-30/non), BuseyBench median 17.6 s, p90 50.3 s, worst 80.1 s (0/0/0/27). Fill and ALU rates are the Pi Zero's class (20.8 GFLOPS FP32, 1.3 Gpix/s; glmark2-es2 offscreen ~1.4x a VideoCore IV), so BuseyBench is non-interactive at every resolution; what the box has over the Pi is a 3.3x bus (tile traffic 3.3x cheaper) and a Cortex-A53 that is 24x this Mac instead of 45x, which is why the icon set does better than on the Pi (1080p median 30 ms vs 64 ms); 4K is 4-5x 1080p.
* **Older TV box, S905 / Mali-450 MP3 (GLES2, FP16 fragment shaders)**: 640x480: icons median 12 ms (5/1/2/0 at 60/30/10-30/non), BuseyBench median 821 ms, p90 2.7 s, worst 4.3 s (0/0/0/27); 1080p: icons median 38 ms (1/3/3/1 at 60/30/10-30/non), BuseyBench median 4.8 s, p90 16.2 s, worst 25.1 s (0/0/0/27); 4k: icons median 134 ms (0/0/2/6 at 60/30/10-30/non), BuseyBench median 23.6 s, p90 75.0 s, worst 120.7 s (0/0/0/27). Same verdicts as the S905X2 with 35 % longer frames at the median, plus a correctness caveat: Utgard runs femtovg's `precision highp` fragment shader at FP16, so gradients, the rounded scissor mask and the two-point radial solve lose precision at 1080p and 4K.
* **Pi Zero** (unchanged from model.md): 640x480: icons median 19 ms (3/3/2/0 at 60/30/10-30/non), BuseyBench median 931 ms, p90 2.2 s, worst 3.6 s (0/0/0/27); 1080p: icons median 64 ms (0/2/4/2 at 60/30/10-30/non), BuseyBench median 5.8 s, p90 13.8 s, worst 20.0 s (0/0/0/27).
* **The pathological mechanism is the same on every device**: BuseyBench frames are 31-200 viewport-sized layers (`VIEWPORT_CLIP=1` scissors every layer to the 1080-px box), each costing a store + load of a 1088x1088 RGBA8 target and a clear + composite over it, and 4-113 Gaussian blurs run over that whole target (0.35-7.87 Gtaps per frame at 1080p). Tile traffic is 35-67 % and blur taps 18-52 % of the modelled GPU time on every file (Pi profile; the shares move by a few points between devices); render-pass boundaries 1-3 % on the TV boxes; full-target clip stencil quads (24 files) at most 1.1 %; masks (13 files apply 1-2 viewport-sized masks) and feTurbulence (6 files, 25-30 % of their taps at the noise rate) are second-order. The CPU is never the limit on BuseyBench on any device (recording + driver 8 ms-68 ms on the iPhone, 53 ms-413 ms on the S905X2, 62 ms-486 ms on the S905, 57 ms-353 ms on the Pi, always under the GPU time); Ghostscript_Tiger is the one CPU-bound file (869 draw calls: 76 ms on the Pi, 34-42 ms on the boxes, 3.6 ms on the iPhone at 640x480).
* **What changes it**: application-side scissoring of each layer to its group's bounds is the lever that moves verdicts - the layer bboxes the fixed harness logs cover 3-12 % (median 6 %) of the viewport-sized store for BuseyBench at 1080p, so the modelled BuseyBench median drops 2.3-6.1x: on the iPhone XS at 640x480 BuseyBench goes from 0/3/13/11 to 3/9/14/1 (60/30/10-30/non), with the six patches as well 5/9/13/0; at 1080p 10 of 27 files become 10-30 fps (13 with the patches), none reach 30 fps. On the S905X2 at 640x480 scissoring + patches bring 9 of 27 files into the 10-30 fps class (4 on the S905, 1 on the Pi Zero) and none to 30 fps; at 1080p and 4K the boxes stay non-interactive on every file. The six parked patches alone take 18-27 % off the BuseyBench medians and change verdicts only on the iPhone at 640x480 (0/3/13/11 -> 0/6/13/8). Caveat measured on the fixed binary: the harness's `LAYER_BBOX_SCISSOR=1` raises the transient pool's peak up to 3.1x at the default budget (claude-fable-5-1 36.5 -> 86.9 MiB at 1080p) because every distinct layer size becomes its own pool class that is never reused within the frame, and at 48 MiB it then refuses 89/178 of that file's layers; the scissoring estimate assumes the pool hands a smaller request a larger free image (or releases within the frame), which it does not today.
* **The #323 review fixes change nothing at 640x480** (the fixed binary refuses no layer on any of the 35 files at 48, 32 or 16 MiB; peaks <= 13.5 MiB) and change only budget-refused layers at 1080p: at 48 MiB 3 files lose nested layers (gemini-3-1-pro-preview-custom-tools 3/75, gpt-5-2-pro 7/53, qwen3-8-max 7/94), a modelled 4.0-13.1 % of their frame on every device; at 32 MiB 16 files lose 1-41 layers (0.5-43.5 %, qwen3-8-max the top). No verdict changes: the frames stay non-interactive, and a refused layer also drops its opacity and filter, so this is degradation, not optimisation.

## What is measured, what is modelled

Measured (this Mac): per frame and file, the fragments rasterised per pass type (colour, image-sampling, stencil-only, clear), the texture taps of blur/turbulence passes, the pixels stored/loaded at render-pass boundaries, pass switches, the draw-call mix, blur count, femtovg recording CPU time, wgpu encode time and Metal GPU time (measurements.json, produced by run_matrix.py on the pz-measure tree). Modelled: everything device-specific, below. The model is model_pi.py's, verbatim (the Pi Zero rows reproduce model.md to the millisecond), with the device table as a parameter and one added term, a GPU-side cost per render-pass boundary (`us_per_pass_gpu`, 0 for the Pi so its rows stay model.md's; fitted on this Mac's Metal GPU time, see the profiles):

```
GPU ms  = colour_frag/colour_rate + image_frag/image_rate + stencil_frag/stencil_rate + clear_frag/clear_rate
        + blur_taps/tap_rate (+ turbulence taps/noise_rate)
        + (store_px + load_px) * 4 B * (1 + zs_fraction) / bandwidth + pass_switches * us_per_pass_gpu
CPU ms  = femtovg_record_ms(Mac) * cpu_factor + draws * us_per_draw + pass_switches * us_per_pass + blurs * us_per_tex_alloc
frame   = max(CPU, GPU)   [range: optimistic max(...) .. pessimistic CPU + GPU]
```

4K (3840x2160, box 2160 at 840,0) is not measured; each pixel-type count is extrapolated from the file's 1080p value with the file's own measured 640x480 -> 1080p exponent (area ratio 5.06 -> 4.0; exponents clamped to 0.8-1.5, e.g. claude-fable-5-1 taps 1.12, so taps grow 4.7x while tile pixels grow 4.0-4.3x), draw calls / passes / recording unchanged. The fixed harness was run at 4K only for layer counts, pass-throughs and transient bytes (section 1).

## Device profiles (central, optimistic, pessimistic) and sources

### Pi Zero: Raspberry Pi Zero (BCM2835: ARM11 1 GHz, VideoCore IV GLES2 via Mesa vc4, LPDDR2 ~1.5 GB/s shared)

API: OpenGL ES 2 (femtovg GL backend, Mesa vc4). Resolutions modelled: 640x480, 1080p.

| parameter | central | optimistic | pessimistic | unit | basis |
|---|---|---|---|---|---|
| color_gfrag | 0.4 | 0.6 | 0.3 | Gfrag/s | VideoCore IV: 1 Gpix/s trivial fill, 24-29 GFLOPS QPU (12 QPUs x 4 lanes x 250-300 MHz x 2); femtovg's main shader ~60 scalar ops/fragment + blend |
| image_gfrag | 0.3 | 0.5 | 0.2 | Gfrag/s | +1 TMU fetch per fragment |
| stencil_gfrag | 0.8 | 1.0 | 0.6 | Gfrag/s | no colour math, no blend |
| clear_gfrag | 1.0 | 1.2 | 0.8 | Gfrag/s | tile clear near peak |
| tap_gtap | 1.0 | 1.5 | 0.7 | Gtap/s | linear reads along one axis |
| noise_gtap | 0.5 | 0.8 | 0.35 | Gtap/s | dependent nearest taps, scattered |
| bandwidth_gbs | 1.5 | 2.0 | 1.0 | GB/s | LPDDR2 shared with the ARM |
| zs_fraction | 0.5 | 0.0 | 1.0 | fraction of passes | packed 32-bit Z/S tile loaded/stored when stencil is touched |
| us_per_pass_gpu | 0.0 | 0.0 | 0.0 | us (GPU) | not in model_pi.py; 0 keeps these rows equal to model.md (a vc4 bin+render job per pass would add ~5-10 % to BuseyBench) |
| cpu_factor | 45.0 | 30.0 | 60.0 | x this Mac | ARM1176 1 GHz, single-issue, 16 KB L1, no L2 (review.md section 2) |
| us_per_draw | 60.0 | 30.0 | 120.0 | us (CPU) | Mesa vc4 state validation + uniform upload |
| us_per_pass | 150.0 | 80.0 | 300.0 | us (CPU) | FBO bind + job submit ioctl + tile setup |
| us_per_tex_alloc | 600.0 | 300.0 | 1500.0 | us (CPU) | CMA BO alloc + FBO validate |
| stencil_bpp | 4 | 1 | 4 | B/px | vc4 packed depth24/stencil8 |

### iPhone XS: iPhone XS (Apple A12: 2x Vortex 2.49 GHz, 4-core Apple GPU ~1.13 GHz, LPDDR4X-4266 34.1 GB/s), Metal via wgpu

API: Metal (femtovg wgpu backend). Resolutions modelled: 640x480, 1080p.

| parameter | central | optimistic | pessimistic | unit | basis |
|---|---|---|---|---|---|
| color_gfrag | 6.0 | 9.0 | 4.0 | Gfrag/s | 576 GFLOPS FP32 (4 cores, ~1.13 GHz) / ~60 flops per fragment = 9.6 Gfrag/s ideal, x0.6 occupancy/blend |
| image_gfrag | 5.0 | 8.0 | 3.0 | Gfrag/s | +1 bilinear fetch; 27.8 GTexel/s (GFXBench Texturing offscreen) is not the limit |
| stencil_gfrag | 15.0 | 25.0 | 10.0 | Gfrag/s | no colour math; ROP 4-8 px/clk/core, stencil in tile memory |
| clear_gfrag | 30.0 | 60.0 | 15.0 | Gfrag/s | tile clears |
| tap_gtap | 12.0 | 20.0 | 8.0 | Gtap/s | 27.8 GTexel/s peak, 1-D blur taps, 4 FMA per tap |
| noise_gtap | 4.0 | 8.0 | 2.5 | Gtap/s | dependent nearest taps into the 512x256 lattice + ~30 ALU per octave |
| bandwidth_gbs | 25.0 | 30.0 | 18.0 | GB/s | LPDDR4X-4266 64-bit = 34.1 GB/s peak; GPU-achievable share |
| zs_fraction | 0.5 | 0.0 | 1.0 | fraction of passes | TBDR stores the Stencil8 tile when the pass stores it |
| us_per_pass_gpu | 60.0 | 30.0 | 120.0 | us (GPU) | this Mac's Metal GPU time fits 25-27 us per pass switch (R^2 0.97, 70 frames; the tile term is unmeasurable at 546 GB/s); A12 taken at 2-4x (1.13 GHz, 4 cores) |
| cpu_factor | 3.1 | 2.5 | 4.0 | x this Mac | Geekbench 6 single-core: M4 Max 4060 / iPhone XS 1306 (A12 Vortex 2.49 GHz, 128 KB L1, 8 MB L2) |
| us_per_draw | 2.2 | 1.8 | 2.9 | us (CPU) | wgpu/Metal encode fitted on this Mac: 0.72 us x draws + 18.4 us x passes + 15.3 us x blurs (R^2 0.996, 70 frames), x cpu_factor |
| us_per_pass | 57.0 | 46.0 | 74.0 | us (CPU) | same fit (render-pass encoder creation) |
| us_per_tex_alloc | 47.0 | 38.0 | 61.0 | us (CPU) | same fit (blur scratch texture per blur) |
| stencil_bpp | 1 | 1 | 1 | B/px | wgpu Stencil8 |

### S905X2 / Mali-G31 MP2: Android 9 TV box, Amlogic S905X2 (4x Cortex-A53 1.8 GHz, Mali-G31 MP2 650 MHz GLES 3.2, DDR4 32-bit ~8.5-10.7 GB/s peak)

API: OpenGL ES 3.2 (femtovg GL backend, Arm proprietary driver). Resolutions modelled: 640x480, 1080p, 4k.

| parameter | central | optimistic | pessimistic | unit | basis |
|---|---|---|---|---|---|
| color_gfrag | 0.4 | 0.6 | 0.25 | Gfrag/s | Mali-G31 MP2 650 MHz: 20.8 GFLOPS FP32 (2 cores x 8 FMA/clk), highp runs at FP32 on Bifrost, ~60 flops/fragment at ~0.85 utilisation = 0.3 Gfrag/s ALU-bound; pixel rate 1.3 Gpix/s (uni-pixel) or 2.6 (dual-pixel); held at the Pi Zero's central 0.4 because glmark2-es2 offscreen puts the G31 MP2 ~1.4x a VideoCore IV |
| image_gfrag | 0.32 | 0.5 | 0.2 | Gfrag/s | +1 bilinear texel (1 texel/clk/core = 1.3 Gtexel/s) |
| stencil_gfrag | 1.2 | 2.0 | 0.7 | Gfrag/s | pixel-rate bound, 1.3-2.6 Gpix/s |
| clear_gfrag | 1.3 | 2.6 | 0.8 | Gfrag/s | tile clear |
| tap_gtap | 1.1 | 1.6 | 0.7 | Gtap/s | 1.3 Gtexel/s peak, bilinear RGBA8 at full rate |
| noise_gtap | 0.4 | 0.7 | 0.25 | Gtap/s | dependent taps + octave ALU |
| bandwidth_gbs | 5.0 | 7.0 | 3.5 | GB/s | DDR4-2133..2666 x32 = 8.5-10.7 GB/s peak (S905X2: DDR3/4/LPDDR4 up to 3200 MT/s; ODROID-C4 ships DDR4-2640 x32); GPU-achievable share, bus shared with CPU, VPU and scanout |
| zs_fraction | 0.5 | 0.0 | 1.0 | fraction of passes | Mali writes the Z/S tile back unless the app invalidates it (femtovg does not) |
| us_per_pass_gpu | 200.0 | 100.0 | 400.0 | us (GPU) | an FBO switch ends the tiler job and starts a fragment job (assumption with range) |
| cpu_factor | 24.0 | 18.0 | 32.0 | x this Mac | Cortex-A53 1.8 GHz: Snapdragon 450 (8x A53 1.8 GHz) Geekbench 6 single-core 169 vs M4 Max 4060 = 24x |
| us_per_draw | 25.0 | 12.0 | 50.0 | us (CPU) | Arm proprietary GLES driver on an A53: per-draw descriptor build + state validation (Arm: draw calls are the driver's most expensive path; no published figure, assumption with range) |
| us_per_pass | 300.0 | 150.0 | 600.0 | us (CPU) | FBO switch = tile-buffer flush + new job chain + kernel job submit |
| us_per_tex_alloc | 500.0 | 250.0 | 1500.0 | us (CPU) | glTexImage2D + FBO for the blur scratch |
| stencil_bpp | 4 | 1 | 4 | B/px | stencil renderbuffer backed by D24S8 unless the driver packs S8 |

### S905 / Mali-450 MP3: Android TV box, Amlogic S905 (4x Cortex-A53 1.5 GHz, Mali-450 MP3 750 MHz GLES2, DDR3 32-bit ~7.5 GB/s peak)

API: OpenGL ES 2 (femtovg GL backend, Arm Utgard driver; fragment shaders FP16 only). Resolutions modelled: 640x480, 1080p, 4k.

| parameter | central | optimistic | pessimistic | unit | basis |
|---|---|---|---|---|---|
| color_gfrag | 0.25 | 0.4 | 0.15 | Gfrag/s | Mali-450 MP3 750 MHz (Utgard): 3 fragment processors x ~6.75 GFLOPS (9 GFLOPS/GHz per FP, Wikipedia Mali-400) = 20 GFLOPS FP16; highp is silently FP16; VLIW packing ~0.7 |
| image_gfrag | 0.2 | 0.35 | 0.12 | Gfrag/s | +1 texel |
| stencil_gfrag | 1.5 | 2.2 | 1.0 | Gfrag/s | 1 px/clk/FP = 2.25 Gpix/s peak |
| clear_gfrag | 1.5 | 2.2 | 1.0 | Gfrag/s | tile clear |
| tap_gtap | 0.8 | 1.5 | 0.5 | Gtap/s | 1 texel/clk/FP = 2.25 Gtexel/s peak; the 24-iteration blur loop is unrolled on Utgard |
| noise_gtap | 0.25 | 0.5 | 0.15 | Gtap/s | 10-octave dependent-fetch loop, unrolled |
| bandwidth_gbs | 4.0 | 5.5 | 2.5 | GB/s | DDR3-1866 x32 = 7.5 GB/s peak (ODROID-C2: DDR3 32-bit / 912 MHz); shared |
| zs_fraction | 0.5 | 0.0 | 1.0 | fraction of passes | as G31 |
| us_per_pass_gpu | 250.0 | 120.0 | 500.0 | us (GPU) | as G31, older job manager |
| cpu_factor | 29.0 | 22.0 | 40.0 | x this Mac | Cortex-A53 1.5 GHz: 169 x 1.5/1.8 = 141 vs 4060 = 29x |
| us_per_draw | 30.0 | 15.0 | 60.0 | us (CPU) | Mali-450 GLES2 driver on an A53 (assumption with range) |
| us_per_pass | 350.0 | 150.0 | 700.0 | us (CPU) | as G31, older driver |
| us_per_tex_alloc | 600.0 | 300.0 | 1500.0 | us (CPU) | as G31 |
| stencil_bpp | 4 | 1 | 4 | B/px | D24S8 |

Sources (fetched or search-indexed 2026-09-16; figures as reported by the page):

* Apple A12: Wikipedia, https://en.wikipedia.org/wiki/Apple_A12 - 4-core Apple-designed GPU ('50% faster graphics than A11'), 2x Vortex 2.49 GHz, L1 128 KB I + 128 KB D, L2 8 MB, LPDDR4X, TSMC N7.
* A12 GPU clock and FLOPS estimate: cpu-monkey / nanoreview / topcpu, https://www.cpu-monkey.com/en/cpu-apple_a12_bionic , https://nanoreview.net/en/soc/apple-a12-bionic - GPU 1.13 GHz, 576 GFLOPS FP32 (third-party estimates; Apple publishes neither).
* A12 memory: gsmarena iPhone XS review / cpu-monkey, https://www.gsmarena.com/apple_iphone_xs-review-1827p5.php - 4 GB LPDDR4X-4266, 34.1 GB/s.
* A12 GPU benchmarks: Notebookcheck A12 Bionic GPU pages, https://www.notebookcheck.net/A12Z-Bionic-GPU-vs-A12-Bionic-GPU-vs-A12X-Bionic-GPU_10326_8896_9351.247598.0.html - GFXBench T-Rex offscreen avg 247 fps (226-274), Manhattan 3.0 offscreen avg 125 fps (107-139); GFXBench device page (search index) Texturing offscreen 27,760 / 25,293 MTexels/s, https://gfxbench.com/device.jsp?benchmark=gfx40&did=67528629&os=iOS&api=metal&hwtype=iGPU&hwname=Apple+A12+GPU
* Geekbench 6 CPU: iPhone XS single-core 1306, https://browser.geekbench.com/ios_devices/iphone-xs ; M4 Max single-core 4060, https://browser.geekbench.com/mac-benchmarks ; topcpu.net GB6 single-core ladder (A12 1301, Snapdragon 450 169, Snapdragon 439 200, Helio P22 234, Unisoc SC9863A 165), https://www.topcpu.net/en/soc-r/geekbench-6-single-core
* Geekbench 6 Metal (GPU cross-check): iPhone XS Max 6,525, https://browser.geekbench.com/v6/compute/5407115 (iPhone XS runs 4,707-5,552, https://browser.geekbench.com/v6/compute/4497116 ); M4 Max 40-core 192,532, https://browser.geekbench.com/v6/compute/3331943 (wccftech summary https://wccftech.com/m4-max-gpu-benchmarks-revealed/ ).
* Amlogic S905X2: CNX Software comparison, https://www.cnx-software.com/2018/10/21/comparison-s905x-s905x2-s905x2-processors/ - 4x Cortex-A53 (18,400 DMIPS, marketed 2.0 GHz, boxes run 1.8), Mali-G31 MP2 up to 850 MHz, DDR3/DDR4/LPDDR3/4 up to 3200 MT/s, 12 nm; boxes at 1.8 GHz / 650 MHz: droix benchmarks https://droix.net/blogs/s905x2-and-s905y2-benchmark-results/ (H96 Max X2: Antutu 3D 1080p 8,146 vs S905X 3,099; 3DMark Ice Storm Extreme graphics 4,571 vs 3,709), androidpctv https://androidpctv.com/comparative-amlogic-s905x2-s905y2/ (G31 MP2 650 MHz, '2.6 Gpix/s').
* Mali-G31: Arm product page https://www.arm.com/products/silicon-ip-multimedia/gpu/mali-g31 (OpenGL ES 3.2, Vulkan, AFBC); Wikipedia Mali table https://en.wikipedia.org/wiki/Mali_(processor) (G31: 1-6 cores, 4 or 8 shading units per core, fillrate 0.5 Gpix/s per core @ 1 GHz, 650 MHz typical); gadgetversus https://gadgetversus.com/graphics-card/arm-mali-g31-mp2-vs-arm-mali-450/ (G31 MP2 650 MHz, 16 shading units, 20.8 GFLOPS FP32); hwpure https://hwpure.com/hardware/videocards/mali-g31-mp2 (~20 GFLOPS, GLES 3.2 / Vulkan 1.1; Allwinner H618 box: 3DMark Ice Storm Extreme 4,352, Aztec Ruins 2.5 fps).
* ODROID-C4 (S905X3, same Mali-G31 MP2 at 650 MHz): Hardkernel https://www.hardkernel.com/shop/odroid-c4/ - 'Mali-G31 MP2 ~50% faster than Mali-450MP in ODROID-C2 (glmark2-es2 --off-screen)', DDR4 2640 MT/s 32-bit; ameridroid https://ameridroid.com/blogs/ameriblogs/new-product-odroid-c4 (glmark2-es2 ~300).
* Raspberry Pi 3B glmark2-es2 (VideoCore IV @ 300 MHz, vc4 Mesa 19.1): windowed 84, offscreen 218, https://gist.github.com/janisozaur/baf7b07c5e5128826cdb7108f1a4dd54 ; Pi Zero QPUs at 300 MHz (VPU 400): https://www.lambda-v.com/texts/programming/gpu/gpu_raspi.html (28.8 GFLOPS at 300 MHz).
* Amlogic S905 / Mali-450 MP3: CNX S905 vs S905X https://www.cnx-software.com/2016/07/31/amlogic-s905-vs-s905x-benchmarks-comparison/ (4x A53 1.5 GHz, Mali-450 MP 750 MHz; Antutu 3D 1080p 3,979 / 3,099, Ice Storm Extreme graphics 3,698 / 3,709); ODROID-C2 DDR3 32-bit 912 MHz https://www.hardkernel.com/shop/odroid-c2/ ; Notebookcheck Mali-450 MP4 https://www.notebookcheck.net/ARM-Mali-450-MP4.116281.0.html (T-Rex offscreen avg 10.4 fps at ~700 MHz); hwpure Mali-450 MP https://hwpure.com/hardware/videocards/mali-450-mp (S905X box: T-Rex ES2.0 11 fps, Ice Storm Extreme 4,179).
* Mali-400/450 fragment precision: Arm community 'Floating point precision of Fragment Shader in Mali-400 MP2', https://community.arm.com/developer/tools-software/graphics/f/discussions/11195/floating-point-precision-of-fragment-shader-in-mali-400-mp2 - only FP16 in fragment shaders, highp has no effect; Wikipedia Mali-400 MP https://en.wikipedia.org/wiki/Mali-400_MP (1.2-5.4 GFLOPS per fragment processor at 200-600 MHz).
* Mali driver cost: Arm community 'Overhead of the Driver' (Peter Harris: draw calls are the most expensive path in the driver after uploads and shader compile), https://community.arm.com/support-forums/f/mobile-graphics-and-gaming-forum/48848/overhead-of-the-driver/170762 - qualitative only; the us/draw and us/pass values are assumptions with ranges.

### Cross-checks

* **Pi Zero**: the pi_zero rows reproduce model.md exactly (same assumptions, same code path, per-pass GPU term 0).
* **iPhone XS vs the measured Mac GPU time**: scaling this Mac's Metal GPU time by the Geekbench 6 Metal ratio (192,532 / 6,525 = 29.5x; the bandwidth ratio 546 / 34.1 = 16x is the floor) is an independent estimate. Over the 27 BuseyBench frames the rate model is 0.97x the scaled Mac time at the median at 1080p (range 0.42-1.60x) and 0.28x at 640x480 (0.15-0.58x). The 1080p agreement is the meaningful one: at 640x480 this Mac's GPU time is almost entirely fixed per-pass latency (claude-fable-5-1 17.1 ms for 639 passes at 640x480 vs 30.5 ms at 1080p for 5x the pixels, i.e. ~25 us per pass), and a fixed latency does not scale with the 29.5x core-count ratio, so the scaled Mac time overstates the A12 there. The added `us_per_pass_gpu` term (60 us per pass on the A12) is the model's own account of that cost; it is 5-40 % of the A12's 640x480 BuseyBench frame.
* **The three low-end GPUs are one class on simple fills**: glmark2-es2 offscreen Pi 3B (VC4 @ 300 MHz, the Pi Zero's QPU clock) 218, ODROID-C4 (G31 MP2 @ 650) ~300, ODROID-C2 (Mali-450 MP3 @ 750) ~200 (C4 = 1.5x C2 per Hardkernel); 3DMark Ice Storm Extreme graphics S905X2 4,571 vs S905X 3,709 (1.23x). Their ALU budgets are 20-29 GFLOPS each. The model therefore gives the G31 MP2 the Pi Zero's fragment rates, the Mali-450 MP3 25-40 % lower ones (FP16 VLIW), and separates the boxes from the Pi by bus (5 / 4 vs 1.5 GB/s) and CPU (24x / 29x vs 45x), and charges them a per-pass GPU cost the Pi model omits.
* **wgpu/Metal driver cost**: a least-squares fit of the measured encode_ms over the 70 frames gives 0.72 us per draw, 18.4 us per pass switch, 15.3 us per blur (scratch texture) with R^2 0.996; the icon files without passes run 0.8-4.4 us per draw. The iPhone uses those times x 3.1.

## Summary: median / p90 / worst modelled frame per device x resolution x set

Verdict counts are 60 fps / 30 fps / 10-30 fps / non-interactive. `patched` = the six parked patches (harness/pz/*.patch, count reductions from patched_all6.md); `scissored` = every layer scissored to its group's layer bbox (estimate, see section 3); `both` = patches + scissoring.

| device | resolution | set | n | median ms | p90 ms | worst ms | 60/30/10-30/non | patched: median / worst (verdicts) | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Pi Zero | 640x480 | icons | 8 | 19 | 67 | 76 | 3/3/2/0 | 19 / 77 (3/3/2/0) | 15 / 76 (4/2/2/0) | 14 / 77 (4/2/2/0) |
| Pi Zero | 640x480 | busey | 27 | 931 | 2,189 | 3,639 | 0/0/0/27 | 763 / 2,657 (0/0/0/27) | 306 / 971 (0/0/0/27) | 252 / 739 (0/0/1/26) |
| Pi Zero | 1080p | icons | 8 | 64 | 190 | 296 | 0/2/4/2 | 65 / 231 (1/2/3/2) | 37 / 267 (0/3/4/1) | 30 / 209 (1/4/2/1) |
| Pi Zero | 1080p | busey | 27 | 5,829 | 13,755 | 20,045 | 0/0/0/27 | 4,364 / 14,439 (0/0/0/27) | 1,649 / 4,152 (0/0/0/27) | 1,399 / 3,167 (0/0/0/27) |
| iPhone XS | 640x480 | icons | 8 | 1.1 | 4.1 | 5.2 | 8/0/0/0 | 1.1 / 4.0 (8/0/0/0) | 1.1 / 4.9 (8/0/0/0) | 1.1 / 3.7 (8/0/0/0) |
| iPhone XS | 640x480 | busey | 27 | 80 | 220 | 365 | 0/3/13/11 | 66 / 264 (0/6/13/8) | 36 / 122 (3/9/14/1) | 30 / 94 (5/9/13/0) |
| iPhone XS | 1080p | icons | 8 | 3.4 | 13 | 21 | 7/1/0/0 | 3.4 / 16 (8/0/0/0) | 2.2 / 19 (7/1/0/0) | 2.0 / 15 (8/0/0/0) |
| iPhone XS | 1080p | busey | 27 | 424 | 1,207 | 1,858 | 0/0/0/27 | 318 / 1,315 (0/0/0/27) | 119 / 331 (0/0/10/17) | 101 / 251 (0/0/13/14) |
| S905X2 / Mali-G31 MP2 | 640x480 | icons | 8 | 9.4 | 38 | 45 | 6/0/2/0 | 9.3 / 35 (6/0/2/0) | 7.6 / 41 (6/0/2/0) | 7.5 / 35 (6/1/1/0) |
| S905X2 / Mali-G31 MP2 | 640x480 | busey | 27 | 620 | 1,848 | 2,914 | 0/0/0/27 | 466 / 2,079 (0/0/0/27) | 175 / 583 (0/0/6/21) | 142 / 442 (0/0/9/18) |
| S905X2 / Mali-G31 MP2 | 1080p | icons | 8 | 30 | 102 | 188 | 1/3/3/1 | 31 / 140 (2/2/3/1) | 21 / 166 (2/4/1/1) | 16 / 125 (4/2/1/1) |
| S905X2 / Mali-G31 MP2 | 1080p | busey | 27 | 3,582 | 10,883 | 16,803 | 0/0/0/27 | 2,649 / 11,788 (0/0/0/27) | 719 / 2,087 (0/0/0/27) | 572 / 1,542 (0/0/0/27) |
| S905X2 / Mali-G31 MP2 | 4k | icons | 8 | 103 | 400 | 671 | 0/0/2/6 | 101 / 509 (0/0/3/5) | 98 / 584 (0/0/4/4) | 71 / 445 (0/0/5/3) |
| S905X2 / Mali-G31 MP2 | 4k | busey | 27 | 17,585 | 50,281 | 80,100 | 0/0/0/27 | 12,969 / 55,639 (0/0/0/27) | 3,018 / 9,489 (0/0/0/27) | 2,374 / 6,948 (0/0/0/27) |
| S905 / Mali-450 MP3 | 640x480 | icons | 8 | 12 | 47 | 60 | 5/1/2/0 | 12 / 45 (6/0/2/0) | 9.3 / 55 (6/0/2/0) | 9.2 / 42 (6/0/2/0) |
| S905 / Mali-450 MP3 | 640x480 | busey | 27 | 821 | 2,733 | 4,262 | 0/0/0/27 | 626 / 3,026 (0/0/0/27) | 223 / 766 (0/0/3/24) | 182 / 579 (0/0/4/23) |
| S905 / Mali-450 MP3 | 1080p | icons | 8 | 38 | 134 | 253 | 1/3/3/1 | 39 / 188 (2/2/3/1) | 23 / 224 (1/4/2/1) | 20 / 167 (2/4/1/1) |
| S905 / Mali-450 MP3 | 1080p | busey | 27 | 4,838 | 16,236 | 25,087 | 0/0/0/27 | 3,528 / 17,541 (0/0/0/27) | 934 / 2,913 (0/0/0/27) | 737 / 2,140 (0/0/0/27) |
| S905 / Mali-450 MP3 | 4k | icons | 8 | 134 | 516 | 899 | 0/0/2/6 | 134 / 678 (0/0/3/5) | 100 / 781 (0/0/4/4) | 85 / 592 (0/0/5/3) |
| S905 / Mali-450 MP3 | 4k | busey | 27 | 23,610 | 75,002 | 120,730 | 0/0/0/27 | 17,346 / 83,662 (0/0/0/27) | 3,897 / 13,354 (0/0/0/27) | 3,060 / 9,726 (0/0/0/27) |

## Per-file modelled frame times

Columns: modelled GPU ms and CPU ms (central), frame ms with the optimistic-pessimistic range, verdict; then the frame ms and verdict with the six patches, with layer scissoring, and with both. iPhone tables add the Mac-GPU x 29.5 cross-check.

### Pi Zero @ 640x480

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 6.3 | 76 | 76 (42-145) | 10-30 | 77 10-30 | 76 10-30 | 77 10-30 |
| clipdemo | icons | 0 | 0 | 5.3 | 2.8 | 5.3 (3.8-13) | 60 | 2.7 60 | 5.3 60 | 2.7 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 7.9 | 6.1 | 7.9 (4.6-24) | 60 | 7.9 60 | 6.1 60 | 6.0 60 |
| fox-with-box-on-cloud | icons | 0 | 0 | 5.4 | 19 | 19 (11-41) | 30 | 20 30 | 19 30 | 20 30 |
| google-workspace-48px | icons | 1 | 1 | 63 | 7.8 | 63 (38-117) | 10-30 | 48 10-30 | 58 10-30 | 45 10-30 |
| kit | icons | 2 | 0 | 25 | 7.4 | 25 (14-57) | 30 | 23 30 | 12 60 | 11 60 |
| mr-settodefault | icons | 2 | 0 | 16 | 19 | 19 (11-58) | 30 | 17 30 | 19 30 | 17 30 |
| splash-logo | icons | 0 | 0 | 2.8 | 4.6 | 4.6 (2.7-12) | 60 | 4.7 60 | 4.6 60 | 4.7 60 |
| claude-fable-5-1 | busey | 178 | 54 | 2,652 | 238 | 2,652 (1,548-4,886) | non | 1,976 non | 677 non | 543 non |
| claude-opus-5 | busey | 92 | 48 | 2,119 | 176 | 2,119 (1,254-3,804) | non | 1,539 non | 580 non | 439 non |
| fugu-ultra | busey | 124 | 13 | 878 | 127 | 878 (492-1,814) | non | 796 non | 315 non | 297 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 2,150 | 235 | 2,150 (1,245-4,205) | non | 1,520 non | 698 non | 498 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 1,677 | 178 | 1,677 (989-3,202) | non | 1,238 non | 497 non | 375 non |
| gemini-3-7-flash | busey | 57 | 9 | 446 | 120 | 446 (251-1,024) | non | 373 non | 154 non | 137 non |
| gemini-3-8-flash | busey | 118 | 42 | 1,088 | 193 | 1,088 (600-2,367) | non | 858 non | 411 non | 331 non |
| glm-5-3 | busey | 129 | 59 | 1,685 | 233 | 1,685 (965-3,417) | non | 1,263 non | 544 non | 424 non |
| glm-5-3-flash | busey | 79 | 23 | 994 | 107 | 994 (584-1,901) | non | 763 non | 306 non | 249 non |
| glm-5v-turbo | busey | 57 | 27 | 931 | 101 | 931 (549-1,775) | non | 696 non | 286 non | 223 non |
| gpt-5-2-pro | busey | 53 | 16 | 563 | 76 | 563 (320-1,141) | non | 446 non | 208 non | 171 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 342 | 57 | 342 (197-705) | non | 277 non | 130 non | 110 non |
| gpt-5-6-sol | busey | 48 | 4 | 327 | 64 | 327 (182-711) | non | 286 non | 120 non | 110 non |
| gpt-5-6-sol-pro | busey | 41 | 9 | 462 | 72 | 462 (270-929) | non | 359 non | 154 non | 126 non |
| gpt-5-6-terra-pro | busey | 31 | 9 | 361 | 61 | 361 (210-738) | non | 277 non | 121 non | 98 10-30 |
| gpt-6-astra | busey | 162 | 31 | 1,363 | 275 | 1,363 (769-2,960) | non | 1,111 non | 493 non | 422 non |
| grok-4-5 | busey | 76 | 21 | 652 | 118 | 652 (361-1,412) | non | 532 non | 252 non | 212 non |
| kimi-k2-6 | busey | 55 | 32 | 855 | 104 | 855 (494-1,691) | non | 640 non | 280 non | 215 non |
| kimi-k3 | busey | 50 | 9 | 424 | 67 | 424 (243-870) | non | 349 non | 162 non | 139 non |
| muse-spark-1-3 | busey | 49 | 24 | 641 | 101 | 641 (366-1,325) | non | 476 non | 214 non | 164 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 632 | 90 | 632 (359-1,293) | non | 485 non | 222 non | 177 non |
| nex-n2-pro | busey | 102 | 6 | 699 | 108 | 699 (393-1,454) | non | 654 non | 261 non | 252 non |
| ox-alpha | busey | 94 | 27 | 1,207 | 129 | 1,207 (694-2,309) | non | 925 non | 327 non | 268 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 3,639 | 356 | 3,639 (2,108-6,842) | non | 2,657 non | 971 non | 739 non |
| qwen3-8-27b | busey | 100 | 39 | 1,438 | 158 | 1,438 (844-2,764) | non | 1,068 non | 424 non | 332 non |
| qwen3-8-flash | busey | 119 | 55 | 2,246 | 210 | 2,246 (1,314-4,147) | non | 1,653 non | 674 non | 519 non |
| qwen3-8-max | busey | 94 | 40 | 1,422 | 153 | 1,422 (816-2,726) | non | 1,067 non | 419 non | 331 non |

### Pi Zero @ 1080p

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 33 | 82 | 82 (46-194) | 10-30 | 83 10-30 | 82 10-30 | 83 10-30 |
| clipdemo | icons | 0 | 0 | 34 | 3.3 | 34 (25-57) | 10-30 | 16 60 | 34 10-30 | 16 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 46 | 6.7 | 46 (26-92) | 10-30 | 46 10-30 | 27 30 | 27 30 |
| fox-with-box-on-cloud | icons | 0 | 0 | 32 | 22 | 32 (23-85) | 30 | 27 30 | 32 30 | 27 30 |
| google-workspace-48px | icons | 1 | 1 | 296 | 8.4 | 296 (175-515) | non | 231 non | 267 non | 209 non |
| kit | icons | 2 | 0 | 145 | 7.7 | 145 (81-279) | non | 136 non | 70 10-30 | 68 10-30 |
| mr-settodefault | icons | 2 | 0 | 91 | 20 | 91 (54-191) | 10-30 | 85 10-30 | 39 10-30 | 33 30 |
| splash-logo | icons | 0 | 0 | 17 | 5.5 | 17 (10-37) | 30 | 17 30 | 17 30 | 17 30 |
| claude-fable-5-1 | busey | 178 | 54 | 15,609 | 237 | 15,609 (9,123-26,385) | non | 11,528 non | 3,788 non | 3,028 non |
| claude-opus-5 | busey | 92 | 48 | 12,332 | 179 | 12,332 (7,293-20,460) | non | 8,890 non | 3,285 non | 2,473 non |
| fugu-ultra | busey | 124 | 13 | 4,706 | 126 | 4,706 (2,635-8,674) | non | 4,265 non | 1,649 non | 1,562 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 13,337 | 236 | 13,337 (7,827-23,186) | non | 9,319 non | 3,845 non | 2,717 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 9,951 | 181 | 9,951 (5,876-17,173) | non | 7,220 non | 2,806 non | 2,076 non |
| gemini-3-7-flash | busey | 57 | 9 | 2,701 | 122 | 2,701 (1,530-5,012) | non | 2,226 non | 877 non | 777 non |
| gemini-3-8-flash | busey | 118 | 42 | 6,688 | 194 | 6,688 (3,729-12,424) | non | 5,178 non | 2,332 non | 1,866 non |
| glm-5-3 | busey | 129 | 59 | 11,298 | 235 | 11,298 (6,575-19,899) | non | 8,310 non | 3,259 non | 2,518 non |
| glm-5-3-flash | busey | 79 | 23 | 5,829 | 108 | 5,829 (3,427-10,111) | non | 4,430 non | 1,729 non | 1,399 non |
| glm-5v-turbo | busey | 57 | 27 | 5,931 | 102 | 5,931 (3,533-10,114) | non | 4,364 non | 1,646 non | 1,265 non |
| gpt-5-2-pro | busey | 53 | 16 | 3,767 | 78 | 3,767 (2,203-6,581) | non | 2,888 non | 1,181 non | 954 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 2,049 | 57 | 2,049 (1,177-3,681) | non | 1,639 non | 755 non | 636 non |
| gpt-5-6-sol | busey | 48 | 4 | 1,947 | 65 | 1,947 (1,081-3,648) | non | 1,699 non | 711 non | 656 non |
| gpt-5-6-sol-pro | busey | 41 | 9 | 2,723 | 71 | 2,723 (1,607-4,737) | non | 2,090 non | 824 non | 681 non |
| gpt-5-6-terra-pro | busey | 31 | 9 | 2,307 | 61 | 2,307 (1,351-4,051) | non | 1,747 non | 722 non | 580 non |
| gpt-6-astra | busey | 162 | 31 | 8,958 | 279 | 8,958 (5,128-16,239) | non | 7,129 non | 2,980 non | 2,533 non |
| grok-4-5 | busey | 76 | 21 | 4,203 | 119 | 4,203 (2,357-7,752) | non | 3,349 non | 1,507 non | 1,251 non |
| kimi-k2-6 | busey | 55 | 32 | 5,715 | 105 | 5,715 (3,353-9,936) | non | 4,209 non | 1,647 non | 1,254 non |
| kimi-k3 | busey | 50 | 9 | 2,334 | 68 | 2,334 (1,373-4,088) | non | 1,877 non | 755 non | 647 non |
| muse-spark-1-3 | busey | 49 | 24 | 4,515 | 101 | 4,515 (2,635-7,934) | non | 3,284 non | 1,285 non | 977 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 4,187 | 92 | 4,187 (2,414-7,452) | non | 3,160 non | 1,324 non | 1,053 non |
| nex-n2-pro | busey | 102 | 6 | 3,746 | 110 | 3,746 (2,091-6,942) | non | 3,496 non | 1,396 non | 1,349 non |
| ox-alpha | busey | 94 | 27 | 8,085 | 132 | 8,085 (4,696-13,789) | non | 6,072 non | 1,919 non | 1,571 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 20,045 | 353 | 20,045 (11,862-33,369) | non | 14,439 non | 4,152 non | 3,167 non |
| qwen3-8-27b | busey | 100 | 39 | 9,339 | 159 | 9,339 (5,542-16,024) | non | 6,828 non | 2,516 non | 1,962 non |
| qwen3-8-flash | busey | 119 | 55 | 14,381 | 213 | 14,381 (8,471-24,029) | non | 10,450 non | 3,948 non | 3,018 non |
| qwen3-8-max | busey | 94 | 40 | 9,648 | 155 | 9,648 (5,620-16,394) | non | 7,067 non | 2,418 non | 1,879 non |

### iPhone XS @ 640x480

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | Mac GPU x29.5 | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 0.4 | 3.6 | 3.6 (2.9-5.3) | 51 | 60 | 3.6 60 | 3.6 60 | 3.6 60 |
| clipdemo | icons | 0 | 0 | 0.3 | 0.1 | 0.3 (0.2-0.7) | 15 | 60 | 0.1 60 | 0.3 60 | 0.1 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 0.6 | 0.4 | 0.6 (0.4-1.6) | 23 | 60 | 0.6 60 | 0.4 60 | 0.4 60 |
| fox-with-box-on-cloud | icons | 0 | 0 | 0.3 | 1.0 | 1.0 (0.8-1.8) | 23 | 60 | 1.0 60 | 1.0 60 | 1.0 60 |
| google-workspace-48px | icons | 1 | 1 | 5.2 | 1.1 | 5.2 (3.0-10) | 32 | 60 | 4.0 60 | 4.9 60 | 3.7 60 |
| kit | icons | 2 | 0 | 2.0 | 0.9 | 2.0 (1.1-4.8) | 27 | 60 | 1.9 60 | 1.2 60 | 1.2 60 |
| mr-settodefault | icons | 2 | 0 | 1.2 | 1.2 | 1.2 (1.0-3.6) | 22 | 60 | 1.1 60 | 1.2 60 | 1.1 60 |
| splash-logo | icons | 0 | 0 | 0.2 | 0.2 | 0.2 (0.2-0.6) | 8.4 | 60 | 0.2 60 | 0.2 60 | 0.2 60 |
| claude-fable-5-1 | busey | 178 | 54 | 265 | 44 | 265 (141-510) | 514 | non | 195 non | 83 10-30 | 67 10-30 |
| claude-opus-5 | busey | 92 | 48 | 216 | 31 | 216 (115-404) | 371 | non | 156 non | 68 10-30 | 52 10-30 |
| fugu-ultra | busey | 124 | 13 | 75 | 23 | 75 (42-165) | 275 | 10-30 | 68 10-30 | 39 10-30 | 37 10-30 |
| gemini-3-1-pro-preview | busey | 98 | 96 | 190 | 46 | 190 (107-390) | 561 | non | 134 non | 84 10-30 | 60 10-30 |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 146 | 32 | 146 (83-293) | 398 | non | 108 non | 59 10-30 | 45 10-30 |
| gemini-3-7-flash | busey | 57 | 9 | 38 | 13 | 38 (21-86) | 146 | 10-30 | 32 30 | 19 30 | 17 30 |
| gemini-3-8-flash | busey | 118 | 42 | 96 | 32 | 96 (53-216) | 416 | 10-30 | 76 10-30 | 52 10-30 | 42 10-30 |
| glm-5-3 | busey | 129 | 59 | 147 | 40 | 147 (82-311) | 453 | non | 111 non | 67 10-30 | 53 10-30 |
| glm-5-3-flash | busey | 79 | 23 | 85 | 19 | 85 (48-172) | 303 | 10-30 | 66 10-30 | 36 10-30 | 29 30 |
| glm-5v-turbo | busey | 57 | 27 | 80 | 18 | 80 (46-161) | 235 | 10-30 | 60 10-30 | 33 30 | 26 30 |
| gpt-5-2-pro | busey | 53 | 16 | 49 | 14 | 49 (27-106) | 248 | 10-30 | 39 10-30 | 25 30 | 21 30 |
| gpt-5-6-luna-pro | busey | 33 | 7 | 29 | 8.2 | 29 (16-62) | 177 | 30 | 24 30 | 15 60 | 12 60 |
| gpt-5-6-sol | busey | 48 | 4 | 28 | 9.2 | 28 (15-63) | 135 | 30 | 25 30 | 15 60 | 14 60 |
| gpt-5-6-sol-pro | busey | 41 | 9 | 39 | 9.9 | 39 (22-81) | 139 | 10-30 | 31 30 | 17 30 | 14 60 |
| gpt-5-6-terra-pro | busey | 31 | 9 | 31 | 8.4 | 31 (18-65) | 211 | 30 | 24 30 | 14 60 | 11 60 |
| gpt-6-astra | busey | 162 | 31 | 117 | 37 | 117 (65-259) | 407 | non | 96 10-30 | 59 10-30 | 51 10-30 |
| grok-4-5 | busey | 76 | 21 | 57 | 19 | 57 (32-128) | 240 | 10-30 | 46 10-30 | 31 30 | 26 30 |
| kimi-k2-6 | busey | 55 | 32 | 75 | 19 | 75 (42-155) | 256 | 10-30 | 56 10-30 | 34 10-30 | 26 30 |
| kimi-k3 | busey | 50 | 9 | 37 | 11 | 37 (21-79) | 143 | 10-30 | 30 30 | 19 30 | 16 60 |
| muse-spark-1-3 | busey | 49 | 24 | 56 | 16 | 56 (31-120) | 250 | 10-30 | 42 10-30 | 26 30 | 20 30 |
| muse-spark-1-3-contributor | busey | 59 | 20 | 55 | 15 | 55 (31-118) | 205 | 10-30 | 42 10-30 | 27 30 | 21 30 |
| nex-n2-pro | busey | 102 | 6 | 59 | 18 | 59 (33-129) | 235 | 10-30 | 56 10-30 | 31 30 | 30 30 |
| ox-alpha | busey | 94 | 27 | 118 | 23 | 118 (63-235) | 409 | non | 90 10-30 | 41 10-30 | 34 10-30 |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 365 | 68 | 365 (194-716) | 981 | non | 264 non | 122 non | 94 10-30 |
| qwen3-8-27b | busey | 100 | 39 | 124 | 28 | 124 (70-250) | 319 | non | 92 10-30 | 50 10-30 | 40 10-30 |
| qwen3-8-flash | busey | 119 | 55 | 226 | 38 | 226 (120-435) | 429 | non | 165 non | 80 10-30 | 62 10-30 |
| qwen3-8-max | busey | 94 | 40 | 141 | 28 | 141 (75-281) | 419 | non | 105 non | 52 10-30 | 41 10-30 |

### iPhone XS @ 1080p

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | Mac GPU x29.5 | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 2.0 | 4.0 | 4.0 (3.2-8.4) | 73 | 60 | 4.1 60 | 4.0 60 | 4.1 60 |
| clipdemo | icons | 0 | 0 | 1.9 | 0.2 | 1.9 (1.1-3.3) | 25 | 60 | 0.9 60 | 1.9 60 | 0.9 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 2.8 | 0.5 | 2.8 (1.6-5.6) | 38 | 60 | 2.8 60 | 1.7 60 | 1.7 60 |
| fox-with-box-on-cloud | icons | 0 | 0 | 1.8 | 1.1 | 1.8 (1.1-4.4) | 43 | 60 | 1.5 60 | 1.8 60 | 1.5 60 |
| google-workspace-48px | icons | 1 | 1 | 21 | 1.1 | 21 (12-37) | 63 | 30 | 16 60 | 19 30 | 15 60 |
| kit | icons | 2 | 0 | 9.0 | 0.9 | 9.0 (5.0-17) | 80 | 60 | 8.5 60 | 4.7 60 | 4.5 60 |
| mr-settodefault | icons | 2 | 0 | 5.5 | 1.3 | 5.5 (3.2-11) | 93 | 60 | 5.2 60 | 2.5 60 | 2.2 60 |
| splash-logo | icons | 0 | 0 | 0.9 | 0.3 | 0.9 (0.5-2.1) | 72 | 60 | 0.9 60 | 0.9 60 | 0.9 60 |
| claude-fable-5-1 | busey | 178 | 54 | 1,388 | 44 | 1,388 (744-2,372) | 916 | non | 999 non | 286 non | 227 non |
| claude-opus-5 | busey | 92 | 48 | 1,139 | 31 | 1,139 (608-1,920) | 712 | non | 808 non | 263 non | 196 non |
| fugu-ultra | busey | 124 | 13 | 320 | 23 | 320 (182-590) | 376 | non | 288 non | 119 non | 113 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 985 | 46 | 985 (570-1,699) | 985 | non | 685 non | 280 non | 199 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 736 | 33 | 736 (427-1,261) | 755 | non | 531 non | 203 non | 151 non |
| gemini-3-7-flash | busey | 57 | 9 | 188 | 14 | 188 (108-342) | 208 | non | 152 non | 63 10-30 | 55 10-30 |
| gemini-3-8-flash | busey | 118 | 42 | 464 | 32 | 464 (265-850) | 499 | non | 355 non | 168 non | 134 non |
| glm-5-3 | busey | 129 | 59 | 817 | 40 | 817 (472-1,424) | 809 | non | 595 non | 234 non | 181 non |
| glm-5-3-flash | busey | 79 | 23 | 424 | 19 | 424 (246-732) | 437 | non | 318 non | 125 non | 101 non |
| glm-5v-turbo | busey | 57 | 27 | 440 | 18 | 440 (256-748) | 444 | non | 321 non | 119 non | 92 10-30 |
| gpt-5-2-pro | busey | 53 | 16 | 273 | 14 | 273 (158-476) | 328 | non | 206 non | 86 10-30 | 69 10-30 |
| gpt-5-6-luna-pro | busey | 33 | 7 | 145 | 8.2 | 145 (83-257) | 169 | non | 114 non | 54 10-30 | 45 10-30 |
| gpt-5-6-sol | busey | 48 | 4 | 131 | 9.3 | 131 (74-242) | 309 | non | 113 non | 50 10-30 | 46 10-30 |
| gpt-5-6-sol-pro | busey | 41 | 9 | 198 | 9.9 | 198 (115-343) | 275 | non | 150 non | 60 10-30 | 49 10-30 |
| gpt-5-6-terra-pro | busey | 31 | 9 | 167 | 8.4 | 167 (97-290) | 250 | non | 125 non | 52 10-30 | 41 10-30 |
| gpt-6-astra | busey | 162 | 31 | 629 | 37 | 629 (361-1,123) | 654 | non | 493 non | 212 non | 180 non |
| grok-4-5 | busey | 76 | 21 | 292 | 19 | 292 (167-530) | 309 | non | 229 non | 107 non | 89 10-30 |
| kimi-k2-6 | busey | 55 | 32 | 419 | 19 | 419 (242-722) | 431 | non | 306 non | 119 non | 90 10-30 |
| kimi-k3 | busey | 50 | 9 | 169 | 11 | 169 (98-298) | 224 | non | 134 non | 56 10-30 | 48 10-30 |
| muse-spark-1-3 | busey | 49 | 24 | 329 | 16 | 329 (190-571) | 322 | non | 237 non | 92 10-30 | 70 10-30 |
| muse-spark-1-3-contributor | busey | 59 | 20 | 299 | 16 | 299 (172-527) | 378 | non | 223 non | 95 10-30 | 75 10-30 |
| nex-n2-pro | busey | 102 | 6 | 252 | 18 | 252 (144-466) | 323 | non | 234 non | 100 10-30 | 96 10-30 |
| ox-alpha | busey | 94 | 27 | 710 | 23 | 710 (381-1,219) | 491 | non | 518 non | 141 non | 115 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 1,858 | 68 | 1,858 (992-3,164) | 1,515 | non | 1,315 non | 331 non | 251 non |
| qwen3-8-27b | busey | 100 | 39 | 686 | 28 | 686 (399-1,172) | 674 | non | 497 non | 181 non | 141 non |
| qwen3-8-flash | busey | 119 | 55 | 1,311 | 38 | 1,311 (701-2,221) | 847 | non | 935 non | 313 non | 237 non |
| qwen3-8-max | busey | 94 | 40 | 857 | 28 | 857 (459-1,467) | 598 | non | 614 non | 183 non | 141 non |

### S905X2 / Mali-G31 MP2 @ 640x480

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 4.9 | 34 | 34 (20-69) | 10-30 | 35 10-30 | 34 10-30 | 35 10-30 |
| clipdemo | icons | 0 | 0 | 3.3 | 1.3 | 3.3 (1.9-7.8) | 60 | 1.5 60 | 3.3 60 | 1.5 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 4.6 | 3.4 | 4.6 (2.6-14) | 60 | 4.6 60 | 3.4 60 | 3.4 60 |
| fox-with-box-on-cloud | icons | 0 | 0 | 3.6 | 9.0 | 9.0 (5.5-21) | 60 | 9.4 60 | 9.0 60 | 9.4 60 |
| google-workspace-48px | icons | 1 | 1 | 45 | 6.8 | 45 (28-87) | 10-30 | 34 10-30 | 41 10-30 | 31 30 |
| kit | icons | 2 | 0 | 13 | 5.7 | 13 (7.1-33) | 60 | 12 60 | 6.2 60 | 5.9 60 |
| mr-settodefault | icons | 2 | 0 | 9.6 | 9.8 | 9.8 (6.1-33) | 60 | 9.1 60 | 9.8 60 | 9.1 60 |
| splash-logo | icons | 0 | 0 | 1.7 | 2.2 | 2.2 (1.4-6.5) | 60 | 2.2 60 | 2.2 60 | 2.2 60 |
| claude-fable-5-1 | busey | 178 | 54 | 2,174 | 268 | 2,174 (1,257-4,171) | non | 1,558 non | 409 non | 323 non |
| claude-opus-5 | busey | 92 | 48 | 1,841 | 190 | 1,841 (1,073-3,434) | non | 1,307 non | 393 non | 293 non |
| fugu-ultra | busey | 124 | 13 | 524 | 136 | 524 (302-1,184) | non | 464 non | 175 non | 164 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 1,399 | 285 | 1,399 (856-2,984) | non | 986 non | 398 non | 286 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 1,144 | 201 | 1,144 (713-2,345) | non | 838 non | 290 non | 219 non |
| gemini-3-7-flash | busey | 57 | 9 | 269 | 92 | 269 (158-649) | non | 217 non | 92 10-30 | 86 10-30 |
| gemini-3-8-flash | busey | 118 | 42 | 620 | 199 | 620 (353-1,504) | non | 482 non | 223 non | 180 non |
| glm-5-3 | busey | 129 | 59 | 1,061 | 247 | 1,061 (637-2,332) | non | 781 non | 301 non | 235 non |
| glm-5-3-flash | busey | 79 | 23 | 669 | 117 | 669 (413-1,365) | non | 499 non | 176 non | 142 non |
| glm-5v-turbo | busey | 57 | 27 | 636 | 110 | 636 (396-1,294) | non | 466 non | 167 non | 129 non |
| gpt-5-2-pro | busey | 53 | 16 | 350 | 85 | 350 (207-774) | non | 270 non | 118 non | 97 10-30 |
| gpt-5-6-luna-pro | busey | 33 | 7 | 217 | 53 | 217 (131-476) | non | 170 non | 75 10-30 | 62 10-30 |
| gpt-5-6-sol | busey | 48 | 4 | 189 | 58 | 189 (108-445) | non | 160 non | 65 10-30 | 59 10-30 |
| gpt-5-6-sol-pro | busey | 41 | 9 | 303 | 64 | 303 (185-639) | non | 228 non | 87 10-30 | 71 10-30 |
| gpt-5-6-terra-pro | busey | 31 | 9 | 236 | 55 | 236 (144-509) | non | 176 non | 70 10-30 | 55 10-30 |
| gpt-6-astra | busey | 162 | 31 | 823 | 242 | 823 (481-1,912) | non | 650 non | 271 non | 230 non |
| grok-4-5 | busey | 76 | 21 | 377 | 118 | 377 (216-900) | non | 301 non | 138 non | 116 non |
| kimi-k2-6 | busey | 55 | 32 | 553 | 117 | 553 (337-1,186) | non | 409 non | 159 non | 123 non |
| kimi-k3 | busey | 50 | 9 | 270 | 66 | 270 (161-595) | non | 216 non | 94 10-30 | 80 10-30 |
| muse-spark-1-3 | busey | 49 | 24 | 401 | 101 | 401 (241-898) | non | 293 non | 119 non | 91 10-30 |
| muse-spark-1-3-contributor | busey | 59 | 20 | 390 | 96 | 390 (231-867) | non | 292 non | 123 non | 98 10-30 |
| nex-n2-pro | busey | 102 | 6 | 418 | 108 | 418 (242-938) | non | 385 non | 144 non | 138 non |
| ox-alpha | busey | 94 | 27 | 931 | 142 | 931 (533-1,857) | non | 684 non | 187 non | 152 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 2,914 | 414 | 2,914 (1,677-5,748) | non | 2,079 non | 583 non | 442 non |
| qwen3-8-27b | busey | 100 | 39 | 962 | 173 | 962 (594-1,979) | non | 698 non | 240 non | 187 non |
| qwen3-8-flash | busey | 119 | 55 | 1,859 | 232 | 1,859 (1,076-3,576) | non | 1,331 non | 442 non | 335 non |
| qwen3-8-max | busey | 94 | 40 | 1,097 | 173 | 1,097 (628-2,205) | non | 798 non | 250 non | 195 non |

### S905X2 / Mali-G31 MP2 @ 1080p

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 25 | 38 | 38 (22-106) | 10-30 | 38 10-30 | 38 10-30 | 38 10-30 |
| clipdemo | icons | 0 | 0 | 21 | 1.6 | 21 (12-39) | 30 | 8.7 60 | 21 30 | 8.7 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 23 | 3.7 | 23 (13-47) | 30 | 23 30 | 15 60 | 15 60 |
| fox-with-box-on-cloud | icons | 0 | 0 | 21 | 10 | 21 (12-52) | 30 | 17 30 | 21 30 | 17 30 |
| google-workspace-48px | icons | 1 | 1 | 188 | 7.1 | 188 (118-324) | non | 140 non | 166 non | 125 non |
| kit | icons | 2 | 0 | 65 | 5.9 | 65 (35-126) | 10-30 | 59 10-30 | 28 30 | 26 30 |
| mr-settodefault | icons | 2 | 0 | 49 | 11 | 49 (28-102) | 10-30 | 45 10-30 | 19 30 | 15 60 |
| splash-logo | icons | 0 | 0 | 9.6 | 2.7 | 9.6 (5.5-20) | 60 | 9.6 60 | 9.6 60 | 9.6 60 |
| claude-fable-5-1 | busey | 178 | 54 | 12,307 | 267 | 12,307 (7,170-20,811) | non | 8,686 non | 1,642 non | 1,273 non |
| claude-opus-5 | busey | 92 | 48 | 10,300 | 191 | 10,300 (6,037-17,254) | non | 7,233 non | 1,782 non | 1,303 non |
| fugu-ultra | busey | 124 | 13 | 2,513 | 136 | 2,513 (1,476-4,572) | non | 2,199 non | 621 non | 583 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 8,363 | 285 | 8,363 (5,278-14,469) | non | 5,813 non | 1,567 non | 1,109 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 6,372 | 203 | 6,372 (4,042-10,952) | non | 4,585 non | 1,174 non | 870 non |
| gemini-3-7-flash | busey | 57 | 9 | 1,505 | 93 | 1,505 (906-2,733) | non | 1,176 non | 323 non | 283 non |
| gemini-3-8-flash | busey | 118 | 42 | 3,520 | 200 | 3,520 (2,086-6,435) | non | 2,649 non | 842 non | 671 non |
| glm-5-3 | busey | 129 | 59 | 6,855 | 249 | 6,855 (4,274-11,942) | non | 4,903 non | 1,245 non | 954 non |
| glm-5-3-flash | busey | 79 | 23 | 3,668 | 118 | 3,668 (2,305-6,319) | non | 2,682 non | 724 non | 572 non |
| glm-5v-turbo | busey | 57 | 27 | 3,906 | 110 | 3,906 (2,494-6,651) | non | 2,806 non | 719 non | 544 non |
| gpt-5-2-pro | busey | 53 | 16 | 2,340 | 86 | 2,340 (1,462-4,063) | non | 1,733 non | 505 non | 400 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 1,192 | 53 | 1,192 (730-2,106) | non | 910 non | 321 non | 263 non |
| gpt-5-6-sol | busey | 48 | 4 | 995 | 59 | 995 (577-1,829) | non | 825 non | 258 non | 235 non |
| gpt-5-6-sol-pro | busey | 41 | 9 | 1,735 | 64 | 1,735 (1,092-2,997) | non | 1,268 non | 359 non | 286 non |
| gpt-5-6-terra-pro | busey | 31 | 9 | 1,434 | 55 | 1,434 (899-2,490) | non | 1,043 non | 306 non | 239 non |
| gpt-6-astra | busey | 162 | 31 | 5,120 | 244 | 5,120 (3,116-9,120) | non | 3,875 non | 1,155 non | 960 non |
| grok-4-5 | busey | 76 | 21 | 2,257 | 118 | 2,257 (1,346-4,086) | non | 1,736 non | 568 non | 467 non |
| kimi-k2-6 | busey | 55 | 32 | 3,582 | 118 | 3,582 (2,257-6,183) | non | 2,590 non | 669 non | 507 non |
| kimi-k3 | busey | 50 | 9 | 1,484 | 67 | 1,484 (926-2,596) | non | 1,142 non | 347 non | 288 non |
| muse-spark-1-3 | busey | 49 | 24 | 2,775 | 102 | 2,775 (1,738-4,823) | non | 1,967 non | 496 non | 374 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 2,464 | 97 | 2,464 (1,520-4,327) | non | 1,794 non | 516 non | 405 non |
| nex-n2-pro | busey | 102 | 6 | 1,972 | 108 | 1,972 (1,151-3,595) | non | 1,786 non | 535 non | 512 non |
| ox-alpha | busey | 94 | 27 | 6,229 | 144 | 6,229 (3,619-10,572) | non | 4,448 non | 755 non | 605 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 16,803 | 413 | 16,803 (9,847-28,383) | non | 11,788 non | 1,855 non | 1,392 non |
| qwen3-8-27b | busey | 100 | 39 | 6,018 | 174 | 6,018 (3,816-10,291) | non | 4,257 non | 1,027 non | 785 non |
| qwen3-8-flash | busey | 119 | 55 | 11,758 | 234 | 11,758 (6,875-19,770) | non | 8,272 non | 2,087 non | 1,542 non |
| qwen3-8-max | busey | 94 | 40 | 7,525 | 174 | 7,525 (4,377-12,763) | non | 5,322 non | 1,048 non | 797 non |

### S905X2 / Mali-G31 MP2 @ 4k

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 101 | 38 | 101 (63-233) | non | 101 non | 101 non | 101 non |
| clipdemo | icons | 0 | 0 | 104 | 1.6 | 104 (60-181) | non | 55 10-30 | 104 non | 55 10-30 |
| duckduckgo-com_2x | icons | 1 | 0 | 100 | 3.7 | 100 (56-181) | non | 100 non | 62 10-30 | 62 10-30 |
| fox-with-box-on-cloud | icons | 0 | 0 | 94 | 10 | 94 (56-177) | 10-30 | 80 10-30 | 94 10-30 | 80 10-30 |
| google-workspace-48px | icons | 1 | 1 | 671 | 7.1 | 671 (415-1,133) | non | 509 non | 584 non | 445 non |
| kit | icons | 2 | 0 | 284 | 5.9 | 284 (152-515) | non | 259 non | 118 non | 111 non |
| mr-settodefault | icons | 2 | 0 | 208 | 11 | 208 (118-379) | non | 191 non | 77 10-30 | 62 10-30 |
| splash-logo | icons | 0 | 0 | 42 | 2.7 | 42 (24-77) | 10-30 | 42 10-30 | 42 10-30 | 42 10-30 |
| claude-fable-5-1 | busey | 178 | 54 | 56,316 | 267 | 56,316 (32,867-93,025) | non | 39,554 non | 6,837 non | 5,277 non |
| claude-opus-5 | busey | 92 | 48 | 46,258 | 191 | 46,258 (27,127-76,006) | non | 32,411 non | 7,557 non | 5,504 non |
| fugu-ultra | busey | 124 | 13 | 10,382 | 136 | 10,382 (6,135-17,976) | non | 9,034 non | 2,356 non | 2,213 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 41,506 | 285 | 41,506 (26,570-68,786) | non | 28,691 non | 6,583 non | 4,634 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 29,125 | 203 | 29,125 (18,567-48,366) | non | 20,875 non | 4,938 non | 3,639 non |
| gemini-3-7-flash | busey | 57 | 9 | 7,174 | 93 | 7,174 (4,382-12,240) | non | 5,506 non | 1,344 non | 1,175 non |
| gemini-3-8-flash | busey | 118 | 42 | 17,585 | 200 | 17,585 (10,673-30,109) | non | 12,969 non | 3,491 non | 2,771 non |
| glm-5-3 | busey | 129 | 59 | 37,176 | 249 | 37,176 (23,620-61,801) | non | 26,254 non | 5,498 non | 4,181 non |
| glm-5-3-flash | busey | 79 | 23 | 16,587 | 118 | 16,587 (10,482-27,642) | non | 12,051 non | 3,018 non | 2,374 non |
| glm-5v-turbo | busey | 57 | 27 | 19,569 | 110 | 19,569 (12,624-32,199) | non | 13,939 non | 3,190 non | 2,392 non |
| gpt-5-2-pro | busey | 53 | 16 | 13,699 | 86 | 13,699 (8,813-22,560) | non | 9,886 non | 2,280 non | 1,767 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 5,455 | 53 | 5,455 (3,359-9,241) | non | 4,137 non | 1,389 non | 1,132 non |
| gpt-5-6-sol | busey | 48 | 4 | 4,514 | 59 | 4,514 (2,637-7,870) | non | 3,712 non | 1,087 non | 991 non |
| gpt-5-6-sol-pro | busey | 41 | 9 | 8,274 | 64 | 8,274 (5,289-13,700) | non | 5,951 non | 1,474 non | 1,161 non |
| gpt-5-6-terra-pro | busey | 31 | 9 | 7,215 | 55 | 7,215 (4,577-12,005) | non | 5,178 non | 1,357 non | 1,051 non |
| gpt-6-astra | busey | 162 | 31 | 27,623 | 244 | 27,623 (17,212-46,467) | non | 20,419 non | 5,195 non | 4,268 non |
| grok-4-5 | busey | 76 | 21 | 11,829 | 118 | 11,829 (7,229-20,139) | non | 8,897 non | 2,505 non | 2,045 non |
| kimi-k2-6 | busey | 55 | 32 | 19,264 | 118 | 19,264 (12,340-31,854) | non | 13,774 non | 3,015 non | 2,262 non |
| kimi-k3 | busey | 50 | 9 | 7,172 | 67 | 7,172 (4,599-11,853) | non | 5,368 non | 1,363 non | 1,103 non |
| muse-spark-1-3 | busey | 49 | 24 | 16,201 | 102 | 16,201 (10,384-26,783) | non | 11,298 non | 2,266 non | 1,693 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 13,194 | 97 | 13,194 (8,302-22,059) | non | 9,448 non | 2,299 non | 1,787 non |
| nex-n2-pro | busey | 102 | 6 | 7,981 | 108 | 7,981 (4,655-13,909) | non | 7,222 non | 2,083 non | 1,993 non |
| ox-alpha | busey | 94 | 27 | 33,833 | 144 | 33,833 (19,782-55,738) | non | 23,846 non | 3,294 non | 2,623 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 80,100 | 413 | 80,100 (47,337-130,880) | non | 55,639 non | 6,552 non | 4,861 non |
| qwen3-8-27b | busey | 100 | 39 | 30,858 | 174 | 30,858 (19,808-50,922) | non | 21,640 non | 4,543 non | 3,443 non |
| qwen3-8-flash | busey | 119 | 55 | 59,432 | 234 | 59,432 (34,887-97,539) | non | 41,584 non | 9,489 non | 6,948 non |
| qwen3-8-max | busey | 94 | 40 | 41,835 | 174 | 41,835 (24,513-68,782) | non | 29,278 non | 4,689 non | 3,528 non |

### S905 / Mali-450 MP3 @ 640x480

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 6.9 | 42 | 42 (25-85) | 10-30 | 42 10-30 | 42 10-30 | 42 10-30 |
| clipdemo | icons | 0 | 0 | 3.2 | 1.6 | 3.2 (2.0-8.0) | 60 | 1.9 60 | 3.2 60 | 1.9 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 6.1 | 4.1 | 6.1 (3.5-18) | 60 | 6.1 60 | 4.1 60 | 4.1 60 |
| fox-with-box-on-cloud | icons | 0 | 0 | 4.2 | 11 | 11 (6.8-25) | 60 | 11 60 | 11 60 | 11 60 |
| google-workspace-48px | icons | 1 | 1 | 60 | 8.1 | 60 (32-118) | 10-30 | 45 10-30 | 55 10-30 | 42 10-30 |
| kit | icons | 2 | 0 | 17 | 6.8 | 17 (9.1-43) | 30 | 16 60 | 7.7 60 | 7.5 60 |
| mr-settodefault | icons | 2 | 0 | 12 | 12 | 12 (7.4-42) | 60 | 12 60 | 12 60 | 11 60 |
| splash-logo | icons | 0 | 0 | 2.3 | 2.6 | 2.6 (1.7-8.3) | 60 | 2.7 60 | 2.6 60 | 2.7 60 |
| claude-fable-5-1 | busey | 178 | 54 | 3,193 | 315 | 3,193 (1,630-6,157) | non | 2,271 non | 541 non | 424 non |
| claude-opus-5 | busey | 92 | 48 | 2,732 | 224 | 2,732 (1,391-5,134) | non | 1,933 non | 543 non | 402 non |
| fugu-ultra | busey | 124 | 13 | 702 | 160 | 702 (371-1,591) | non | 619 non | 223 non | 209 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 1,870 | 335 | 1,870 (977-3,984) | non | 1,318 non | 508 non | 365 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 1,540 | 236 | 1,540 (809-3,156) | non | 1,128 non | 373 non | 283 non |
| gemini-3-7-flash | busey | 57 | 9 | 360 | 109 | 360 (189-864) | non | 287 non | 109 non | 101 non |
| gemini-3-8-flash | busey | 118 | 42 | 821 | 235 | 821 (427-1,989) | non | 635 non | 281 non | 227 non |
| glm-5-3 | busey | 129 | 59 | 1,415 | 291 | 1,415 (741-3,109) | non | 1,041 non | 382 non | 298 non |
| glm-5-3-flash | busey | 79 | 23 | 900 | 138 | 900 (475-1,843) | non | 670 non | 226 non | 182 non |
| glm-5v-turbo | busey | 57 | 27 | 857 | 129 | 857 (451-1,746) | non | 626 non | 216 non | 167 non |
| gpt-5-2-pro | busey | 53 | 16 | 467 | 100 | 467 (245-1,037) | non | 360 non | 151 non | 124 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 291 | 62 | 291 (153-638) | non | 226 non | 96 10-30 | 80 10-30 |
| gpt-5-6-sol | busey | 48 | 4 | 251 | 69 | 251 (133-594) | non | 212 non | 82 10-30 | 75 10-30 |
| gpt-5-6-sol-pro | busey | 41 | 9 | 407 | 76 | 407 (215-861) | non | 305 non | 112 non | 91 10-30 |
| gpt-5-6-terra-pro | busey | 31 | 9 | 317 | 65 | 317 (167-684) | non | 236 non | 89 10-30 | 71 10-30 |
| gpt-6-astra | busey | 162 | 31 | 1,095 | 286 | 1,095 (576-2,545) | non | 862 non | 344 non | 292 non |
| grok-4-5 | busey | 76 | 21 | 501 | 139 | 501 (262-1,196) | non | 398 non | 175 non | 147 non |
| kimi-k2-6 | busey | 55 | 32 | 741 | 138 | 741 (388-1,588) | non | 548 non | 203 non | 157 non |
| kimi-k3 | busey | 50 | 9 | 362 | 78 | 362 (192-799) | non | 289 non | 122 non | 104 non |
| muse-spark-1-3 | busey | 49 | 24 | 535 | 120 | 535 (280-1,196) | non | 390 non | 151 non | 116 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 519 | 113 | 519 (272-1,157) | non | 388 non | 156 non | 124 non |
| nex-n2-pro | busey | 102 | 6 | 561 | 127 | 561 (297-1,265) | non | 514 non | 184 non | 177 non |
| ox-alpha | busey | 94 | 27 | 1,354 | 168 | 1,354 (692-2,704) | non | 986 non | 242 non | 196 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 4,262 | 487 | 4,262 (2,172-8,405) | non | 3,026 non | 766 non | 579 non |
| qwen3-8-27b | busey | 100 | 39 | 1,289 | 204 | 1,289 (679-2,659) | non | 935 non | 306 non | 238 non |
| qwen3-8-flash | busey | 119 | 55 | 2,735 | 273 | 2,735 (1,394-5,277) | non | 1,948 non | 603 non | 454 non |
| qwen3-8-max | busey | 94 | 40 | 1,594 | 204 | 1,594 (813-3,201) | non | 1,153 non | 329 non | 256 non |

### S905 / Mali-450 MP3 @ 1080p

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 34 | 45 | 45 (28-137) | 10-30 | 46 10-30 | 45 10-30 | 46 10-30 |
| clipdemo | icons | 0 | 0 | 20 | 1.9 | 20 (13-36) | 30 | 10 60 | 20 30 | 10 60 |
| duckduckgo-com_2x | icons | 1 | 0 | 31 | 4.5 | 31 (18-64) | 30 | 31 30 | 19 30 | 19 30 |
| fox-with-box-on-cloud | icons | 0 | 0 | 23 | 12 | 23 (15-59) | 30 | 20 30 | 23 30 | 20 30 |
| google-workspace-48px | icons | 1 | 1 | 253 | 8.4 | 253 (135-451) | non | 188 non | 224 non | 167 non |
| kit | icons | 2 | 0 | 82 | 7.0 | 82 (45-167) | 10-30 | 77 10-30 | 34 10-30 | 33 30 |
| mr-settodefault | icons | 2 | 0 | 62 | 13 | 62 (35-131) | 10-30 | 58 10-30 | 23 30 | 19 30 |
| splash-logo | icons | 0 | 0 | 12 | 3.2 | 12 (7.1-27) | 60 | 12 60 | 12 60 | 12 60 |
| claude-fable-5-1 | busey | 178 | 54 | 18,251 | 314 | 18,251 (9,318-31,949) | non | 12,811 non | 2,196 non | 1,690 non |
| claude-opus-5 | busey | 92 | 48 | 15,387 | 226 | 15,387 (7,838-26,675) | non | 10,780 non | 2,501 non | 1,820 non |
| fugu-ultra | busey | 124 | 13 | 3,381 | 160 | 3,381 (1,798-6,399) | non | 2,951 non | 793 non | 746 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 11,272 | 335 | 11,272 (5,931-20,105) | non | 7,838 non | 2,015 non | 1,428 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 8,613 | 239 | 8,613 (4,544-15,253) | non | 6,198 non | 1,519 non | 1,128 non |
| gemini-3-7-flash | busey | 57 | 9 | 2,027 | 110 | 2,027 (1,071-3,814) | non | 1,573 non | 409 non | 358 non |
| gemini-3-8-flash | busey | 118 | 42 | 4,707 | 235 | 4,707 (2,468-8,955) | non | 3,528 non | 1,063 non | 846 non |
| glm-5-3 | busey | 129 | 59 | 9,219 | 293 | 9,219 (4,860-16,590) | non | 6,594 non | 1,587 non | 1,215 non |
| glm-5-3-flash | busey | 79 | 23 | 4,953 | 138 | 4,953 (2,621-8,804) | non | 3,614 non | 935 non | 737 non |
| glm-5v-turbo | busey | 57 | 27 | 5,292 | 130 | 5,292 (2,798-9,277) | non | 3,796 non | 934 non | 706 non |
| gpt-5-2-pro | busey | 53 | 16 | 3,164 | 101 | 3,164 (1,676-5,669) | non | 2,336 non | 654 non | 517 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 1,603 | 62 | 1,603 (848-2,935) | non | 1,221 non | 417 non | 341 non |
| gpt-5-6-sol | busey | 48 | 4 | 1,327 | 70 | 1,327 (703-2,546) | non | 1,097 non | 325 non | 297 non |
| gpt-5-6-sol-pro | busey | 41 | 9 | 2,345 | 75 | 2,345 (1,244-4,174) | non | 1,710 non | 465 non | 370 non |
| gpt-5-6-terra-pro | busey | 31 | 9 | 1,935 | 64 | 1,935 (1,023-3,467) | non | 1,403 non | 395 non | 308 non |
| gpt-6-astra | busey | 162 | 31 | 6,866 | 288 | 6,866 (3,630-12,668) | non | 5,187 non | 1,474 non | 1,225 non |
| grok-4-5 | busey | 76 | 21 | 3,026 | 139 | 3,026 (1,591-5,700) | non | 2,318 non | 724 non | 595 non |
| kimi-k2-6 | busey | 55 | 32 | 4,838 | 138 | 4,838 (2,552-8,616) | non | 3,494 non | 862 non | 653 non |
| kimi-k3 | busey | 50 | 9 | 2,013 | 79 | 2,013 (1,073-3,625) | non | 1,544 non | 453 non | 376 non |
| muse-spark-1-3 | busey | 49 | 24 | 3,740 | 120 | 3,740 (1,970-6,711) | non | 2,646 non | 633 non | 477 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 3,311 | 114 | 3,311 (1,746-6,018) | non | 2,407 non | 660 non | 517 non |
| nex-n2-pro | busey | 102 | 6 | 2,649 | 128 | 2,649 (1,410-5,032) | non | 2,397 non | 686 non | 657 non |
| ox-alpha | busey | 94 | 27 | 9,222 | 169 | 9,222 (4,707-16,213) | non | 6,540 non | 986 non | 785 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 25,087 | 486 | 25,087 (12,798-43,751) | non | 17,541 non | 2,478 non | 1,852 non |
| qwen3-8-27b | busey | 100 | 39 | 8,112 | 205 | 8,112 (4,291-14,290) | non | 5,743 non | 1,319 non | 1,007 non |
| qwen3-8-flash | busey | 119 | 55 | 17,508 | 275 | 17,508 (8,924-30,464) | non | 12,283 non | 2,913 non | 2,140 non |
| qwen3-8-max | busey | 94 | 40 | 11,150 | 205 | 11,150 (5,686-19,578) | non | 7,852 non | 1,401 non | 1,060 non |

### S905 / Mali-450 MP3 @ 4k

| file | set | layers | blurs | GPU ms | CPU ms | frame ms (range) | verdict | patched | scissored | both |
|---|---|---|---|---|---|---|---|---|---|---|
| Ghostscript_Tiger | icons | 0 | 0 | 137 | 45 | 137 (85-312) | non | 137 non | 137 non | 137 non |
| clipdemo | icons | 0 | 0 | 98 | 1.9 | 98 (62-164) | 10-30 | 59 10-30 | 98 10-30 | 59 10-30 |
| duckduckgo-com_2x | icons | 1 | 0 | 131 | 4.5 | 131 (74-249) | non | 131 non | 80 10-30 | 80 10-30 |
| fox-with-box-on-cloud | icons | 0 | 0 | 101 | 12 | 101 (64-189) | non | 90 10-30 | 101 non | 90 10-30 |
| google-workspace-48px | icons | 1 | 1 | 899 | 8.4 | 899 (478-1,582) | non | 678 non | 781 non | 592 non |
| kit | icons | 2 | 0 | 352 | 7.0 | 352 (191-678) | non | 332 non | 146 non | 140 non |
| mr-settodefault | icons | 2 | 0 | 257 | 13 | 257 (146-484) | non | 243 non | 93 10-30 | 80 10-30 |
| splash-logo | icons | 0 | 0 | 54 | 3.2 | 54 (31-100) | 10-30 | 54 10-30 | 54 10-30 | 54 10-30 |
| claude-fable-5-1 | busey | 178 | 54 | 83,732 | 314 | 83,732 (42,695-144,020) | non | 58,505 non | 9,166 non | 7,021 non |
| claude-opus-5 | busey | 92 | 48 | 69,183 | 226 | 69,183 (35,204-118,264) | non | 48,352 non | 10,624 non | 7,703 non |
| fugu-ultra | busey | 124 | 13 | 13,955 | 160 | 13,955 (7,413-25,371) | non | 12,115 non | 3,006 non | 2,826 non |
| gemini-3-1-pro-preview | busey | 98 | 96 | 56,110 | 335 | 56,110 (29,576-96,286) | non | 38,790 non | 8,491 non | 5,983 non |
| gemini-3-1-pro-preview-custom-tools | busey | 75 | 62 | 39,382 | 239 | 39,382 (20,772-67,786) | non | 28,222 non | 6,392 non | 4,717 non |
| gemini-3-7-flash | busey | 57 | 9 | 9,678 | 110 | 9,678 (5,108-17,257) | non | 7,382 non | 1,703 non | 1,485 non |
| gemini-3-8-flash | busey | 118 | 42 | 23,610 | 235 | 23,610 (12,393-42,348) | non | 17,346 non | 4,414 non | 3,498 non |
| glm-5-3 | busey | 129 | 59 | 50,159 | 293 | 50,159 (26,474-86,450) | non | 35,399 non | 7,025 non | 5,339 non |
| glm-5-3-flash | busey | 79 | 23 | 22,397 | 138 | 22,397 (11,842-38,729) | non | 16,238 non | 3,897 non | 3,060 non |
| glm-5v-turbo | busey | 57 | 27 | 26,553 | 130 | 26,553 (14,045-45,158) | non | 18,886 non | 4,155 non | 3,113 non |
| gpt-5-2-pro | busey | 53 | 16 | 18,607 | 101 | 18,607 (9,874-31,662) | non | 13,396 non | 2,976 non | 2,302 non |
| gpt-5-6-luna-pro | busey | 33 | 7 | 7,339 | 62 | 7,339 (3,876-12,971) | non | 5,545 non | 1,802 non | 1,467 non |
| gpt-5-6-sol | busey | 48 | 4 | 6,014 | 70 | 6,014 (3,175-11,045) | non | 4,929 non | 1,371 non | 1,250 non |
| gpt-5-6-sol-pro | busey | 41 | 9 | 11,210 | 75 | 11,210 (5,945-19,198) | non | 8,045 non | 1,916 non | 1,506 non |
| gpt-5-6-terra-pro | busey | 31 | 9 | 9,749 | 64 | 9,749 (5,153-16,819) | non | 6,978 non | 1,755 non | 1,357 non |
| gpt-6-astra | busey | 162 | 31 | 37,146 | 288 | 37,146 (19,631-65,004) | non | 27,393 non | 6,654 non | 5,459 non |
| grok-4-5 | busey | 76 | 21 | 15,917 | 139 | 15,917 (8,372-28,352) | non | 11,922 non | 3,203 non | 2,609 non |
| kimi-k2-6 | busey | 55 | 32 | 26,091 | 138 | 26,091 (13,778-44,671) | non | 18,634 non | 3,896 non | 2,923 non |
| kimi-k3 | busey | 50 | 9 | 9,770 | 79 | 9,770 (5,212-16,667) | non | 7,297 non | 1,795 non | 1,450 non |
| muse-spark-1-3 | busey | 49 | 24 | 21,928 | 120 | 21,928 (11,576-37,528) | non | 15,267 non | 2,904 non | 2,167 non |
| muse-spark-1-3-contributor | busey | 59 | 20 | 17,790 | 114 | 17,790 (9,386-30,905) | non | 12,713 non | 2,948 non | 2,289 non |
| nex-n2-pro | busey | 102 | 6 | 10,692 | 128 | 10,692 (5,677-19,617) | non | 9,666 non | 2,666 non | 2,552 non |
| ox-alpha | busey | 94 | 27 | 50,480 | 169 | 50,480 (25,707-86,599) | non | 35,368 non | 4,323 non | 3,419 non |
| qwen3-8-2-4t-a95b | busey | 200 | 113 | 120,730 | 486 | 120,730 (61,538-204,809) | non | 83,662 non | 8,904 non | 6,575 non |
| qwen3-8-27b | busey | 100 | 39 | 41,670 | 205 | 41,670 (22,050-71,084) | non | 29,223 non | 5,849 non | 4,428 non |
| qwen3-8-flash | busey | 119 | 55 | 88,920 | 275 | 88,920 (45,269-151,784) | non | 62,042 non | 13,354 non | 9,726 non |
| qwen3-8-max | busey | 94 | 40 | 62,529 | 205 | 62,529 (31,832-106,983) | non | 43,600 non | 6,339 non | 4,741 non |

## (1) Do the #323 review fixes change any of it?

The fixes (nested-mask root origin, kept scissor in the padded store, filter-chain images reserved at `begin_layer`) change no fragment, tap or tile count for an admitted layer, so the tables above hold for the fixed tree wherever the transient budget admits every layer. They change the picture only where the earlier reservation makes a layer pass through under a small budget. Measured on the fixed full-stack binary (/private/tmp/wt-all3 at 7bbcb5e, md5 7596fc6e500e10e016916730008149ee, `LAYER_STATS=1 LAYER_LOG=1`, same framings, 491 runs) and, for the masked files, harness/pz/mask-budget-ladder.md (le-fix dc0f9a9, gated harness):

* **640x480: nothing changes.** At the default (256), 48, 32 and 16 MiB budgets the fixed binary refuses 0 layers on all 35 files (256 MiB: max peak 13.5 MiB, refused 0, 48 MiB: max peak 13.5 MiB, refused 0, 32 MiB: max peak 13.5 MiB, refused 0, 16 MiB: max peak 13.5 MiB, refused 0). The 640x480 rows above are the fixed tree's rows.
* **1080p: only budget-refused layers.** Refused layers per file on the full fixed stack (clip + turbulence, the binary above) with the ladder's count for comparison (the ladder covered only the 15 mask-referencing files and ran without #324/#338, so it has no row for the unmasked files that refuse here). The per-device delta is n_refused x the file's average per-layer machinery cost (tile store/load, clear, composite, filter passes, pass boundaries, per-pass driver time), i.e. what the GPU no longer does when the layer is drawn straight into its parent; it is also what the picture loses, since the fixed tree admits a layer with its whole effect set or not at all (opacity and blur are dropped together).

**48 MiB, 1080p** (files with no refused layer omitted; all other files render bit-identically to 256 MiB per the ladder or refuse nothing here):

| file | refused (fixed, full stack) | refused (ladder) | peak MiB default -> budget | Pi Zero frame ms | iPhone XS frame ms | S905X2 / Mali-G31 MP2 frame ms | S905 / Mali-450 MP3 frame ms |
|---|---|---|---|---|---|---|---|
| gemini-3-1-pro-preview-custom-tools | 3/75 | 0 | 56.2 -> 46.0 | 9,951 -> 9,555 (-4.0 %) | 736 -> 706 (-4.0 %) | 6,372 -> 6,119 (-4.0 %) | 8,613 -> 8,271 (-4.0 %) |
| gpt-5-2-pro | 7/53 | 7 | 55.2 -> 45.1 | 3,767 -> 3,272 (-13.1 %) | 273 -> 237 (-13.1 %) | 2,340 -> 2,033 (-13.1 %) | 3,164 -> 2,749 (-13.1 %) |
| qwen3-8-max | 7/94 | 6 | 49.2 -> 44.7 | 9,648 -> 8,933 (-7.4 %) | 857 -> 793 (-7.4 %) | 7,525 -> 6,967 (-7.4 %) | 11,150 -> 10,323 (-7.4 %) |

**32 MiB, 1080p** (files with no refused layer omitted; all other files render bit-identically to 256 MiB per the ladder or refuse nothing here):

| file | refused (fixed, full stack) | refused (ladder) | peak MiB default -> budget | Pi Zero frame ms | iPhone XS frame ms | S905X2 / Mali-G31 MP2 frame ms | S905 / Mali-450 MP3 frame ms |
|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 1/178 | 1 | 36.5 -> 27.5 | 15,609 -> 15,522 (-0.6 %) | 1,388 -> 1,381 (-0.6 %) | 12,307 -> 12,238 (-0.6 %) | 18,251 -> 18,148 (-0.6 %) |
| claude-opus-5 | 2/92 | 0 | 37.2 -> 31.2 | 12,332 -> 12,066 (-2.2 %) | 1,139 -> 1,114 (-2.2 %) | 10,300 -> 10,077 (-2.2 %) | 15,387 -> 15,054 (-2.2 %) |
| fugu-ultra | 2/124 | 2 | 43.2 -> 29.2 | 4,706 -> 4,631 (-1.6 %) | 320 -> 315 (-1.6 %) | 2,513 -> 2,474 (-1.6 %) | 3,381 -> 3,327 (-1.6 %) |
| gemini-3-1-pro-preview | 2/98 | 0 | 34.2 -> 29.7 | 13,337 -> 13,066 (-2.0 %) | 985 -> 965 (-2.0 %) | 8,363 -> 8,193 (-2.0 %) | 11,272 -> 11,043 (-2.0 %) |
| gemini-3-1-pro-preview-custom-tools | 15/75 | 0 | 56.2 -> 29.7 | 9,951 -> 7,972 (-19.9 %) | 736 -> 589 (-19.9 %) | 6,372 -> 5,107 (-19.9 %) | 8,613 -> 6,903 (-19.9 %) |
| glm-5-3-flash | 11/79 | 0 | 34.8 -> 29.7 | 5,829 -> 5,023 (-13.8 %) | 424 -> 365 (-13.9 %) | 3,668 -> 3,161 (-13.8 %) | 4,953 -> 4,267 (-13.8 %) |
| glm-5v-turbo | 7/57 | 0 | 39.3 -> 29.7 | 5,931 -> 5,206 (-12.2 %) | 440 -> 386 (-12.2 %) | 3,906 -> 3,429 (-12.2 %) | 5,292 -> 4,645 (-12.2 %) |
| gpt-5-2-pro | 7/53 | 7 | 55.2 -> 29.3 | 3,767 -> 3,272 (-13.1 %) | 273 -> 237 (-13.1 %) | 2,340 -> 2,033 (-13.1 %) | 3,164 -> 2,749 (-13.1 %) |
| gpt-5-6-sol-pro | 3/41 | 3 | 41.7 -> 30.4 | 2,723 -> 2,525 (-7.3 %) | 198 -> 184 (-7.3 %) | 1,735 -> 1,609 (-7.2 %) | 2,345 -> 2,174 (-7.3 %) |
| grok-4-5 | 3/76 | 3 | 39.3 -> 29.7 | 4,203 -> 4,037 (-3.9 %) | 292 -> 280 (-3.9 %) | 2,257 -> 2,168 (-3.9 %) | 3,026 -> 2,907 (-3.9 %) |
| kimi-k2-6 | 3/55 | 0 | 34.2 -> 29.7 | 5,715 -> 5,405 (-5.4 %) | 419 -> 396 (-5.4 %) | 3,582 -> 3,388 (-5.4 %) | 4,838 -> 4,576 (-5.4 %) |
| nex-n2-pro | 3/102 | 3 | 44.3 -> 29.1 | 3,746 -> 3,637 (-2.9 %) | 252 -> 245 (-2.9 %) | 1,972 -> 1,915 (-2.9 %) | 2,649 -> 2,572 (-2.9 %) |
| qwen3-8-2-4t-a95b | 1/200 | 0 | 57.3 -> 31.3 | 20,045 -> 19,945 (-0.5 %) | 1,858 -> 1,849 (-0.5 %) | 16,803 -> 16,719 (-0.5 %) | 25,087 -> 24,962 (-0.5 %) |
| qwen3-8-27b | 1/100 | 1 | 34.3 -> 29.3 | 9,339 -> 9,247 (-1.0 %) | 686 -> 680 (-1.0 %) | 6,018 -> 5,958 (-1.0 %) | 8,112 -> 8,031 (-1.0 %) |
| qwen3-8-flash | 2/119 | 2 | 46.3 -> 31.3 | 14,381 -> 14,141 (-1.7 %) | 1,311 -> 1,289 (-1.7 %) | 11,758 -> 11,561 (-1.7 %) | 17,508 -> 17,215 (-1.7 %) |
| qwen3-8-max | 41/94 | 41 | 49.2 -> 30.0 | 9,648 -> 5,461 (-43.4 %) | 857 -> 484 (-43.5 %) | 7,525 -> 4,258 (-43.4 %) | 11,150 -> 6,302 (-43.5 %) |

At 48 MiB 3 files are affected (gemini-3-1-pro-preview-custom-tools, gpt-5-2-pro, qwen3-8-max), at 32 MiB 16. No verdict changes anywhere: every affected frame stays non-interactive on every device. Where the full-stack count differs from the ladder (gemini-3-1-pro-preview-custom-tools 3 vs 0; qwen3-8-max 7 vs 6; claude-opus-5 2 vs 0; gemini-3-1-pro-preview 2 vs 0; gemini-3-1-pro-preview-custom-tools 15 vs 0; glm-5-3-flash 11 vs 0; glm-5v-turbo 7 vs 0; kimi-k2-6 3 vs 0; qwen3-8-2-4t-a95b 1 vs 0) the file either carries no mask (outside the ladder) or has a feTurbulence group that is a layer on this build and skipped on the gated one (qwen3-8-max).
* **4K (TV boxes)**: the default 256 MiB admits every layer on every file (peaks 75-211 MiB, so the default is the right order for 4K); 128 MiB refuses the same layers 32 MiB refuses at 1080p (same per-layer ratio; 16 files, qwen3-8-max 41/94, gemini-3-1-pro-preview-custom-tools 15/75, glm-5-3-flash 11/79, glm-5v-turbo 7/57, gpt-5-2-pro 7/53, ...), and 64 MiB refuses layers on 27 of 27 files, up to 96 % of them (gemini-3-1-pro-preview 94/98, claude-fable-5-1 124/178). With a 2176x2176 RGBA8 store at 18.9 MB, a 4K TV app needs 128-256 MiB of transients for this corpus - fine on a 2-4 GB box, and the reason the 32-48 MiB guidance is a 1080p figure.

## (2) Which files are pathological, and why

Every BuseyBench file is non-interactive on the Pi Zero and both TV boxes at every resolution and on the iPhone XS at 1080p; at 640x480 the iPhone XS gets 3 files to 30 fps and 13 to 10-30 fps. The mechanism, from the measured counts and the model's central breakdown at 1080p on the Pi profile (the shares move by a few points between devices; the boxes add 1-3 % of pass-boundary cost):

| file | layers | blurs | masks | turb | clip quad Mpx | blur Mtaps | tile Mpx | dominant GPU terms (1080p) | extras | Pi Zero ms | iPhone XS ms | S905X2 / Mali-G31 MP2 ms | S905 / Mali-450 MP3 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 178 | 54 | 1 | 1 | 62 | 5,481 | 1,580 | layer store/load (tile traffic) 40 %, blur taps 26 % | 1 viewport-sized mask(s); 1 feTurbulence | 15,609 | 1,388 | 12,307 | 18,251 |
| claude-opus-5 | 92 | 48 | 0 | 1 | 50 | 4,909 | 1,088 | layer store/load (tile traffic) 35 %, blur taps 30 % | 1 feTurbulence | 12,332 | 1,139 | 10,300 | 15,387 |
| fugu-ultra | 124 | 13 | 2 | 0 | 25 | 952 | 746 | layer store/load (tile traffic) 63 %, blur taps 20 % | 2 viewport-sized mask(s) | 4,706 | 320 | 2,513 | 3,381 |
| gemini-3-1-pro-preview | 98 | 96 | 0 | 0 | 25 | 6,336 | 1,594 | layer store/load (tile traffic) 48 %, blur taps 48 % |  | 13,337 | 985 | 8,363 | 11,272 |
| gemini-3-1-pro-preview-custom-tools | 75 | 62 | 0 | 0 | 17 | 4,885 | 1,132 | blur taps 49 %, layer store/load (tile traffic) 46 % |  | 9,951 | 736 | 6,372 | 8,613 |
| gemini-3-7-flash | 57 | 9 | 0 | 0 | 0 | 784 | 402 | layer store/load (tile traffic) 60 %, blur taps 29 % |  | 2,701 | 188 | 1,505 | 2,027 |
| gemini-3-8-flash | 118 | 42 | 0 | 0 | 0 | 1,728 | 1,084 | layer store/load (tile traffic) 65 %, blur taps 26 % |  | 6,688 | 464 | 3,520 | 4,707 |
| glm-5-3 | 129 | 59 | 1 | 0 | 58 | 4,749 | 1,438 | layer store/load (tile traffic) 51 %, blur taps 42 % | 1 viewport-sized mask(s) | 11,298 | 817 | 6,855 | 9,219 |
| glm-5-3-flash | 79 | 23 | 0 | 0 | 25 | 2,605 | 687 | layer store/load (tile traffic) 47 %, blur taps 45 % |  | 5,829 | 424 | 3,668 | 4,953 |
| glm-5v-turbo | 57 | 27 | 0 | 0 | 8 | 3,063 | 628 | blur taps 52 %, layer store/load (tile traffic) 42 % |  | 5,931 | 440 | 3,906 | 5,292 |
| gpt-5-2-pro | 53 | 16 | 2 | 0 | 8 | 1,579 | 459 | layer store/load (tile traffic) 49 %, blur taps 42 % | 2 viewport-sized mask(s) | 3,767 | 273 | 2,340 | 3,164 |
| gpt-5-6-luna-pro | 33 | 7 | 1 | 0 | 8 | 709 | 282 | layer store/load (tile traffic) 55 %, blur taps 35 % | 1 viewport-sized mask(s) | 2,049 | 145 | 1,192 | 1,603 |
| gpt-5-6-sol | 48 | 4 | 1 | 0 | 17 | 352 | 325 | layer store/load (tile traffic) 67 %, blur taps 18 % | 1 viewport-sized mask(s) | 1,947 | 131 | 995 | 1,327 |
| gpt-5-6-sol-pro | 41 | 9 | 0 | 0 | 14 | 1,227 | 311 | layer store/load (tile traffic) 46 %, blur taps 45 % |  | 2,723 | 198 | 1,735 | 2,345 |
| gpt-5-6-terra-pro | 31 | 9 | 0 | 0 | 8 | 1,002 | 279 | layer store/load (tile traffic) 48 %, blur taps 43 % |  | 2,307 | 167 | 1,434 | 1,935 |
| gpt-6-astra | 162 | 31 | 1 | 0 | 68 | 2,917 | 1,268 | layer store/load (tile traffic) 57 %, blur taps 33 % | 1 viewport-sized mask(s) | 8,958 | 629 | 5,120 | 6,866 |
| grok-4-5 | 76 | 21 | 0 | 0 | 0 | 1,142 | 661 | layer store/load (tile traffic) 63 %, blur taps 27 % |  | 4,203 | 292 | 2,257 | 3,026 |
| kimi-k2-6 | 55 | 32 | 0 | 0 | 8 | 2,634 | 682 | layer store/load (tile traffic) 48 %, blur taps 46 % |  | 5,715 | 419 | 3,582 | 4,838 |
| kimi-k3 | 50 | 9 | 0 | 0 | 9 | 946 | 272 | layer store/load (tile traffic) 47 %, blur taps 41 % |  | 2,334 | 169 | 1,484 | 2,013 |
| muse-spark-1-3 | 49 | 24 | 0 | 0 | 8 | 1,991 | 561 | layer store/load (tile traffic) 50 %, blur taps 44 % |  | 4,515 | 329 | 2,775 | 3,740 |
| muse-spark-1-3-contributor | 59 | 20 | 0 | 0 | 17 | 1,587 | 565 | layer store/load (tile traffic) 54 %, blur taps 38 % |  | 4,187 | 299 | 2,464 | 3,311 |
| nex-n2-pro | 102 | 6 | 2 | 0 | 25 | 691 | 604 | layer store/load (tile traffic) 65 %, blur taps 18 % | 2 viewport-sized mask(s) | 3,746 | 252 | 1,972 | 2,649 |
| ox-alpha | 94 | 27 | 1 | 1 | 17 | 2,720 | 864 | layer store/load (tile traffic) 43 %, blur taps 25 % | 1 viewport-sized mask(s); 1 feTurbulence | 8,085 | 710 | 6,229 | 9,222 |
| qwen3-8-2-4t-a95b | 200 | 113 | 1 | 2 | 54 | 7,873 | 1,754 | layer store/load (tile traffic) 35 %, blur taps 29 % | 1 viewport-sized mask(s); 2 feTurbulence | 20,045 | 1,858 | 16,803 | 25,087 |
| qwen3-8-27b | 100 | 39 | 1 | 0 | 75 | 4,541 | 1,036 | blur taps 49 %, layer store/load (tile traffic) 44 % | 1 viewport-sized mask(s) | 9,339 | 686 | 6,018 | 8,112 |
| qwen3-8-flash | 119 | 55 | 2 | 2 | 75 | 5,484 | 1,340 | layer store/load (tile traffic) 37 %, blur taps 29 % | 2 viewport-sized mask(s); 2 feTurbulence | 14,381 | 1,311 | 11,758 | 17,508 |
| qwen3-8-max | 94 | 40 | 2 | 1 | 33 | 3,351 | 1,007 | layer store/load (tile traffic) 42 %, blur taps 26 % | 2 viewport-sized mask(s); 1 feTurbulence | 9,648 | 857 | 7,525 | 11,150 |

* **Layer count x viewport-sized stores** (35-67 % of GPU time): with `VIEWPORT_CLIP=1` each of the 31-200 layers stores and reloads a 1088x1088 RGBA8 target (plus the parent's), is cleared, and is composited back - 272-1,754 Mpx of tile traffic per 1080p frame. On the Pi's 1.5 GB/s bus that alone is 1.1 s-7.0 s; on the iPhone's 25 GB/s 65 ms-421 ms.
* **Blur taps** (18-52 %): 4-113 Gaussian blurs per frame, each two passes over the whole store with up to 49 taps per pixel (sigma clamped to 8): 0.35-7.87 Gtaps per 1080p frame - 352 ms-11.8 s at the Pi's 1 Gtap/s, 29 ms-1.3 s at the iPhone's 12 Gtap/s (the turbulence files' taps are charged half at the noise rate).
* **Render-pass boundaries**: 100-1,000 per frame; 1-3 % of the boxes' GPU time at 200-250 us each, 40-200 ms on the iPhone at 60 us, and the term the Pi model omits.
* **Viewport-sized masks** (13 files apply 1-2): a luminance mask adds two viewport-sized coverage images and their draws per masked layer; measurable but second-order next to the layer machinery.
* **Full-target clip stencil quads** (24 files, up to 75 Mpx at 1080p on qwen3-8-27b / qwen3-8-flash): at most 1.1 % of GPU time on any device; patch 01 removes ~90 % of them.
* **feTurbulence** (6 files, 1-2 chains): 25-30 % of those files' GPU time under the model's rule (half the taps at the noise rate).
* **CPU**: recording x factor + driver cost is 8 ms-68 ms on the iPhone, 53 ms-413 ms on the S905X2, 62 ms-486 ms on the S905, 57 ms-353 ms on the Pi at 1080p - the GPU is at least 13.9x the CPU on every BuseyBench frame on every device. Ghostscript_Tiger (icon set, 869 draw calls) is the only CPU-bound file: 82 ms on the Pi (10-30 fps), 38 / 45 ms on the boxes (10-30 fps), 4.0 ms on the iPhone.
* Icon-set outliers: google-workspace-48px (one viewport-sized blurred, masked layer for a 48-px group; 296 ms on the Pi at 1080p, 188 ms on the S905X2) and kit (two viewport-sized layers) are the harness's viewport scissor, not the artwork. Scissoring fixes kit (S905X2 1080p 65 -> 28 ms) but not google-workspace-48px (188 -> 166 ms): its bbox factor is 0.86 because the group's filter region is nearly the whole box.

## (3) What would make them approachable, per device

Three levers, quantified on the same model:

1. **The six parked patches** (01 bounded clip quads, 02 lone-blur no parity pass, 03 clip fans kept, 04 GL blur scratch cache, 05 sized command Vec, 06 direct fill_device_rect triangles) - per-file count reductions measured on this Mac (patched_all6.md: over BuseyBench at 1080p clip-quad Mpx 714 -> 63, pass switches 9,395 -> 7,685, tile Mpx 22,650 -> 18,268, filter Mpx 3,541 -> 2,405, transients 985 -> 786 MB) applied to each device. Effect: BuseyBench medians drop 18-27 % on every device (Pi 1080p 5.8 s -> 4.4 s; iPhone 1080p 424 ms -> 318 ms; S905X2 1080p 3.6 s -> 2.6 s; S905 4K 23.6 s -> 17.3 s); verdict changes only on the iPhone at 640x480 (0/3/13/11 -> 0/6/13/8: gemini-3-7-flash 10-30->30 (38->32 ms), gpt-5-6-sol-pro 10-30->30 (39->31 ms), gpt-6-astra non->10-30 (117->96 ms), kimi-k3 10-30->30 (37->30 ms), ox-alpha non->10-30 (118->90 ms), qwen3-8-27b non->10-30 (124->92 ms)) and on the icons (clipdemo 1080p on the Pi 34 -> 16 ms; S905X2 1080p icons 1/3/3/1 -> 2/2/3/1).

2. **A lower resolution**: the 640x480 framing is 5.06x fewer pixels and the model is 80-100 % pixel-proportional on BuseyBench, so it is a 4-6x lever - the largest single one for the Pi and the boxes, and still not enough: BuseyBench at 640x480 stays non-interactive on all three (Pi median 931 ms, S905X2 620 ms, S905 821 ms; best files 189-327 ms). On the iPhone XS it is the difference between 0/0/0/27 at 1080p and 0/3/13/11 at 640x480. For a TV box the native panel is 1080p or 4K, so this lever means rendering the scene into a smaller layer and scaling it, which the Mali does at its pixel rate (1.3 Gpix/s): a 1080p upscale of a 640x480 render costs ~1.6 ms extra.

3. **Application-side scissoring** (`intersect_scissor` to the group's layer bounding box before `begin_layer`, what the harness's `LAYER_BBOX_SCISSOR=1` does): the fixed harness's LAYER_LOG gives every layer's clipped bbox; with 3-sigma blur padding and the pool's 64-px granularity, BuseyBench layers cover 3.0-12.1 % (median 6.1 %) of the viewport-sized store at 1080p. The estimate scales the layer-sized work (composites, layer clears, filter passes, full-target clip quads, the layer-sized half of the tile traffic) by that factor and leaves content fill, pass boundaries and the parent's own store/load alone. Effect: BuseyBench medians drop 2.3-6.1x (Pi 1080p 5.8 s -> 1.6 s; S905X2 1080p 3.6 s -> 719 ms, 640x480 620 ms -> 175 ms; iPhone 1080p 424 ms -> 119 ms, 640x480 80 ms -> 36 ms). Verdicts: iPhone 640x480 3/9/14/1, 1080p 0/0/10/17; S905X2 640x480 0/0/6/21; S905 640x480 0/0/3/24; Pi 640x480 0/0/0/27. With the patches as well: iPhone 640x480 5/9/13/0, 1080p 0/0/13/14; S905X2 640x480 0/0/9/18; S905 640x480 0/0/4/23; Pi 640x480 0/0/1/26.

   Two measured caveats on lever 3, from running the fixed binary with `LAYER_BBOX_SCISSOR=1`:
   * The transient pool's peak *rises* up to 3.1x at the default budget (1080p MiB: gpt-6-astra 28.7 -> 90.1, claude-opus-5 37.2 -> 88.5, claude-fable-5-1 36.5 -> 86.9, qwen3-8-flash 46.3 -> 99.2; at 4K 5 files hit the 256 MiB ceiling and refuse 4-92 layers) because the pool reuses only an exact size class and never frees within a frame (src/transient.rs), so up to 178 differently-sized layers become 178 live images. At 48 MiB it then refuses 91/119 (qwen3-8-flash), 89/178 (claude-fable-5-1), 76/162 (gpt-6-astra) layers instead of 0-7. The lever needs the pool to hand a smaller request a larger free image (best-fit, or bucketed classes) or to release within the frame; until then bbox scissoring trades GPU time for refused layers under any realistic budget.
   * The bbox the harness scissors to is usvg's `abs_layer_bounding_box` (filter region and strokes included), the same box a browser rasterises the filter in; the estimate does not re-measure fragments, so a layer whose bbox is nearly the viewport (google-workspace-48px, factor 0.86) gains little.

Where that leaves each device:

* **iPhone XS**: with scissoring, BuseyBench at 640x480 is 3/9/14/1 (60/30/10-30/non); with the patches too 5/9/13/0. At 1080p (its native 1125x2436 is 1.3x more pixels) scissoring gets 10 files to 10-30 fps, 13 with the patches; nothing reaches 30 fps at 1080p (best 41 ms) because the remaining per-frame cost is 11-79 Mpx of fragments, 0.01-0.58 Gtaps of blur over the bbox-sized stores and 100-1,000 pass boundaries at 60 us. The next lever is the blur itself: a downsampled blur (blur at 1/2 or 1/4 scale for sigma >= 4, as browsers do) cuts the tap count 4-16x on the sigma-clamped files, and merging the parity pass into the composite removes one pass boundary per layer.
* **S905X2 / Mali-G31 MP2**: BuseyBench is non-interactive at 1080p and 4K under every lever (572 ms median with patches + scissoring at 1080p, 2.4 s at 4K); at 640x480 with both levers 0/0/9/18 - 9 files in the 10-30 fps class, best 55 ms. The icon set: 1080p 1/3/3/1 (Ghostscript_Tiger 38, google-workspace-48px 188, kit 65, mr-settodefault 49 ms; the Tiger is its 869 draws x 25 us, google-workspace-48px is the viewport-sized layer), 4K 0/0/2/6.
* **S905 / Mali-450 MP3**: as the S905X2 with 35 % longer frames (0/0/4/23 at 640x480 with both levers) and the FP16 precision caveat; GLES2 is not a functional limit (femtovg's GL backend and its shaders are GLSL ES 1.00).
* **Pi Zero**: 0/0/1/26 at 640x480 with both levers (gpt-5-6-terra-pro 98 ms the only 10-30 fps file); the bus is the wall.

## Caveats

* All device numbers are rates and factors, not measurements on the devices; the optimistic-pessimistic range in every table is the honest width (roughly 0.6-2x around the central value). The Pi Zero column is model.md's, included for comparison.
* The A12 GPU clock and FLOPS are third-party estimates (Apple publishes neither); the rate model was cross-checked against the measured Mac GPU time scaled by the Geekbench 6 Metal ratio (above).
* The Mali driver per-draw / per-pass costs and the per-pass GPU costs are assumptions with 2-4x ranges; they never dominate BuseyBench (GPU fill and traffic are 2-10x larger) but they set the Tiger's class on the boxes.
* 4K counts are extrapolated from 1080p with measured per-file exponents; the fixed binary was run at 4K only for layer admission and transient bytes.
* Recording time includes the harness's per-frame Path rebuild (an app that keeps its Paths pays less); on the boxes this is 5-30 % of the CPU time, never of the frame.
* Mali-450 (Utgard) executes fragment shaders at FP16 regardless of `highp`; femtovg's paint-matrix and scissor math at 1080p+ and the two-point radial gradient solve are outside FP16's useful range, so the S905 row is a performance class, not a rendering the corpus would pass.

## Artifacts

* harness/pz/model_devices.py: the model (`PZ=harness/pz RUNS=<fixed-binary logs> OUT=<dir> python3 model_devices.py`); scratchpad devices/: `model_devices.json` (every row, summary, budget entry, mechanism share, bbox factor and run stat), `report.py` (writes this file), `run_matrix_fixed.sh`.
* Fixed-binary runs (scratchpad devices/runs/): 491 runs of /private/tmp/wt-all3/target/debug/examples/_logos_full (md5 7596fc6e500e10e016916730008149ee) over the 35 files x {640x480: default/48/32/16 MiB; 1080p: default/48/32 MiB, each with and without LAYER_BBOX_SCISSOR; 4K: default/128/64 MiB and default+bbox}, `SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1 LAYER_STATS=1 LAYER_LOG=1`, renders to /dev/null.
