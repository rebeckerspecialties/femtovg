# Hardening probes against master 1334764 (2026-09-22)

Measurements behind the issues filed for the post-#324 hardening list. Every
number comes from a throwaway test against master 1334764 (#324 merged with
the "Bound clip replay and offscreen work" commits); the wgpu probes ran on
the Metal adapter, the recording probes through `RecordingRenderer`.
Chromium references: chrome-headless-shell 131 through `make_ref.py`.

## Winding counters under a clip (`corpus/winding-overflow.svg`, sheet `winding-overflow.png`)

Coincident same-direction square subpaths filled NonZero, centre pixel:

| contours | unclipped | under a clip |
|---|---|---|
| 126 / 127 | filled / filled | filled / filled |
| 128 | filled | **empty** (7 winding bits wrap) |
| 129 | filled | filled |
| 255 | filled | filled |
| 256 | **empty** (8 bits wrap) | **empty** |
| 257 | filled | filled |

EvenOdd is unaffected by the wrap (parity survives). Alternating-direction
contours (net winding 0 or 1) are right at every count. Chromium fills every
square. Against Chromium at 1x / 2x / 4x: 2.41 / 6.98 / 17.04 % of pixels,
1.93 / 6.13 / 16.10 % structural - the two missing squares.

## Clip edge antialiasing (`clipdemo.svg`, sheet `clip-edge-antialiasing.png`)

| zoom | px > 20/255 | structural |
|---|---|---|
| 1x | 0.54 % | 0.000 % |
| 2x | 0.68 % | 0.000 % |
| 4x | 0.43 % | 0.000 % |

All of it is the hard stencil edge against Chromium's coverage-blended one.

## Clip replay work (recording renderer, 256x256, circle clips nested `depth` deep)

Alternating `restore()` and a small fill afterwards; "consecutive" restores
all clips first and draws once:

| depth | ClipFill commands recorded (clips taken) | vertices queued at flush |
|---|---|---|
| 4 alternating | 10 (4) | 1,984 (31 KiB) |
| 8 alternating | 36 (8) | 7,004 (109 KiB) |
| 16 alternating | 136 (16) | 26,164 (408 KiB) |
| 32 alternating | 528 (32) | 100,964 (1.5 MiB) |
| 32 consecutive | 32 (32) | 6,104 (95 KiB) |

A 20,000-point star clipped 8 deep caches 479,952 vertices (7.3 MiB) and,
with alternating restores and draws, queues 2,160,092 vertices (33 MiB) in
one frame: every replay copies each surviving entry's geometry into the
vertex buffer again.

## Turbulence lattices per distinct seed (recording renderer, one frame)

| distinct seeds | lattices alive until the flush | bytes |
|---|---|---|
| 4 | 4 | 2.0 MiB |
| 5 | 5 | 2.5 MiB |
| 9 | 13 (4 cached + 9 deferred deletions) | 6.5 MiB |
| 256 | 260 | 130 MiB |

The four-entry cache bounds cache hits, not the textures a recorded command
still references: an evicted lattice is deleted at the flush.

## Gradient cache key with a NaN stop (sheet `gradient-nan-alias.png`)

`GradientStop`'s `Ord` compares `(offset, color)` tuples with `<`, so a NaN
offset compares `Equal` to every offset with the same color: stops
`[0, 0.5, 1]` and `[0, NaN, 1]` share one `BTreeMap` key and the NaN gradient
is drawn with whichever ramp was cached first (same `ImageId`); drawn alone
it gets its own ramp. Centre pixel of the NaN bar: `[30, 30, 220]` after the
0.5 gradient, `[30, 114, 124]` alone.
