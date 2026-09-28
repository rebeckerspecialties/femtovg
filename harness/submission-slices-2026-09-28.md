# Submission slicing on the WGPU backend (femtovg #367 / #368)

wgpu opens a Metal command buffer for every render pass of a `CommandEncoder`
and commits them together at submit (wgpu-core `open_pass` -> `begin_encoding`,
wgpu-hal Metal `begin_encoding` = new `MTLCommandBuffer`, queue sized for
4,096), and the driver reserves about 2.3 MiB (`IOAccelerator` shared regions:
sixteen of 32 KiB, two of 256 KiB, one of 768 KiB, one of 1 MiB) for each
until it completes, whatever the target size. A standalone wgpu program with
800 empty passes on one encoder holds 1,841 MiB; the same 800 passes as
encoders inside one `MTLCommandBuffer` in pure Metal hold 25 MiB
(gfx-rs/wgpu#10494). `WGPURenderer::set_submission_slicing` submits the frame
in slices of 64 passes; `wait_past: Some(2)` additionally waits once more than
two slices are unfinished, at the cost of polling the device inside the flush.

## Peak driver memory, one frame at 460x260, M4 Max (`footprint(1)`)

| frame | one submission | slices of 64 | slices of 64, waiting past two |
|---|---|---|---|
| 200 opacity layers | 862 MiB | 344 MiB | 344 MiB |
| 800 opacity layers | 3,685 MiB | 963 MiB | 413 MiB |
| 1,600 opacity layers | buffer creation fails (`Buffer with '' label is invalid`) | 3,589 MiB | 415 MiB |
| claude-fable-5-1 (176 layers, 6 blurs) | 1,535 MiB | 881 MiB | 407 MiB |
| four sigma 64..128 blur groups (`corpus/probes/bigblur.svg`, a 372-pass chain) | 744 MiB | 422 MiB | 338 MiB |

The same 800-layer frame at 1920x1080 holds the same 3,685 MiB: per pass, not per pixel.

## Pixels and time

- 576 corpus frames at 1x/2x/4x: bit-identical against upstream master and against the same build with slicing off (`harness/ab.py`).
- Soak, 201 files x 3 zooms x 3 passes, M4 Max: wall p50 0.9 / p95 35.2 / p99 66.0 / max 134 ms with slicing off, 1.0 / 29.1 / 47.6 / 74 ms with slices alone, 1.0 / 30.6 / 46.8 / 72 ms waiting past two; RSS high-water 733 -> 423 -> 164 MiB.
- `tests/submission_slices_wgpu.rs`: 63/64/65-pass frames slice as `[63]`, `[64]`, `[64, 1]`; a mixed scene renders identically in slices of 1, 3, 7, 8 and 13 passes; the prepass order with and without slicing; a child process measures the 176-layer portrait's footprint: 937 MiB waiting past two slices, 1,109 MiB with slices alone, 1,567 MiB in one submission.

## iPhone 12 (A14, iOS 26.5), 460x260, efficiency cores

Full corpus, one pass at 1x/2x/4x, warm shader cache; master figures from the same harness at upstream master (the five files it cannot hold excluded from the common set).

| | master | sliced |
|---|---|---|
| claude-fable-5-1, gemini-3-1-pro-preview, glm-5-3, qwen3-8-2-4t-a95b, qwen3-8-flash | jetsam at the 2.2 GiB per-process limit | 187-404 ms at 1x |
| the other 194 files (582 frames), wall p50 / p95 / p99 / max, ms | 4.1 / 173 / 357 / 1,534 | 3.2 / 117 / 194 / 244 |

Instruments cannot record the phone while these frames run: the device-side `DTServiceHub` writes the trace at ~1.9 MB/s, exceeds its 4.3 GB per day disk-write budget (`DTServiceHub.diskwrites_resource-*.ips`) and the recording reports "Device disconnected"; a Mac-side hub left by a killed `xctrace` breaks every later recording until killed.
