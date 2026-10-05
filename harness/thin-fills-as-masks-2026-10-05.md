# Thin fills as coverage masks: an experiment

femtovg/femtovg#327: a fill thinner than a pixel is over-inked. Each edge's fringe is drawn for itself, so two edges
a sixth of a pixel apart leave about 1.4 px of ink per pixel of length where the shape covers 0.15, and small text
drawn as paths clogs.

The clip masks of the `clip-coverage` branch (the second tier of femtovg/femtovg#346) hold what such a fill needs:
the area of the flattened path in each pixel, rasterized on the CPU, kept across frames and read by the draw's own
fragment shader in the one pass. Skia's Graphite draws small paths the same way ("Small paths are rasterized on the
CPU for higher quality", `Device::chooseRenderer`, into its `RasterPathAtlas`, at most 256 of them a flush).

The harness switch `FILL_MASKS=T` (`--cfg harness_clip_paths`, `_logos_full.rs`) draws a fill whose mean width on the
target - twice its area over its perimeter - is under T pixels, and whose bounds span at most `FILL_MASKS_MAX` pixels
(65,536), as a rect over its bounds under the path as a clip. Nothing in the library changes: this is what a fill
through a mask would draw, with a clip pushed and popped around it. `FILL_MASKS=1e9 FILL_MASKS_MAX=4096` gates on size
alone, as Skia does: every fill of at most 64 x 64 pixels.

![a card logo, the tiger, an icon and a banner at the fit: fills with fringes, thin fills as masks, the exact area, each build's difference from it, and Chromium's GPU rasterizer and WebKit against it](https://raw.githubusercontent.com/rebeckerspecialties/femtovg/demo-assets/thin-fills-as-masks.png)

Orange is 9-20/255 from the exact area (Chromium 131 at 8 device pixels a pixel, each block averaged), red beyond 20,
a deviating pixel drawn three wide.

## Accuracy

Builds: `cm` is `clip-coverage` (98f1300), `cmf` the same with curves flattened four times finer (the
`finer-flattening` branch's tolerance); `fm1` and `fmf1` are those with `FILL_MASKS=1`, `fms64` and `fmfs64` with the
size gate. Corpus of 1,196 files at four framings, against the area reference, `cm` -> each:

| | changed frames with the reference | toward it | away | by more than 0.1 points | changed pixels, mean distance of 255 |
|---|---:|---:|---:|---:|---:|
| thin fills as masks (`fm1`) | 118 | 67 | 0 | 19 toward, 0 away | 38.0 -> 6.5 |
| fills of at most 64 x 64 as masks (`fms64`) | 346 | 231 | 6 | 34 toward, 0 away | 8.2 -> 3.3 |
| finer flattening alone (`cmf`) | 685 | 594 | 12 | 207 toward, 2 away | 6.5 -> 3.7 |
| finer flattening and thin fills (`fmf1`) | 685 | 605 | 12 | 222 toward, 1 away | 6.9 -> 3.6 |
| finer flattening and small fills (`fmfs64`) | 688 | 608 | 14 | 237 toward, 0 away | 6.8 -> 3.4 |

Finer flattening alone moves two frames away by more than 0.1 points, and both are thin fills: a portrait's stubble is
a dozen open curves under SVG's default black fill, slivers a sixth of a pixel wide, which the coarser flattening
turned into single chords that fill nothing (#360) and the finer one leaves as slivers for the fringes to over-ink -
three of them hold 6 px of ink between them and take 14 px on master, 95 flattened finer, and 3.5 through masks. With
thin fills as masks that frame moves toward the area instead.

Pixels beyond 20/255 of the exact area, over the changed frames that every renderer has:

| frames | before | after | Chromium GPU | Chromium software | Firefox | WebKit |
|---|---:|---:|---:|---:|---:|---:|
| `cm` -> `fm1`, 62 | 32,299 | 25,507 | 39,423 | 33,364 | 27,734 | 25,656 |
| `cm` -> `fmf1`, 364 | 144,084 | 83,062 | 177,992 | 159,213 | 132,505 | 86,617 |
| master -> `fmf1` | 418,779 | 84,907 | 219,220 | 227,901 | 170,559 | 112,114 |

## Cost

On an M4 Max, the same binary with and without the switch, medians of paired runs (`corpus_run/pass_time.py`). The
harness works out a fill's mean width from the path itself, eight chords a curve, which a library would read off the
points it has flattened anyway.

| | frames | in sum | median frame | a tenth of the frames beyond |
|---|---:|---:|---:|---:|
| thin fills, the whole corpus at the fit and at 1080p | 2,392 | +0.2 % | +0.4 % | +4.8 % |
| the files with a thin fill, four framings | 408 | +0.4 % | +0.9 % | +5.7 % |
| the same with the scene moved a fraction of a pixel every frame | 408 | +0.7 % | +1.2 % | +9.5 % |
| thin fills and finer flattening, the whole corpus | 2,392 | +0.8 % | +0.9 % | +5.3 % |
| fills of at most 64 x 64, the whole corpus | 2,392 | +0.8 % | +0.9 % | +5.5 % |
| the files with one, the scene moving every frame | 656 | +2.9 % | +4.2 % | +16.8 % |

At the fit 956 of the corpus's 7,860 fills are thin, in 117 files (346 in 54 at 1080p); the size gate takes 5,442. The
masks of a file with thin fills hold 27 KiB at the median and 0.5 MiB at most (1.9 MiB at 1080p), of a budget of 32.

What a still scene pays is one draw with its own texture for each thin fill. What a moving one pays is the mask
rasterized and uploaded again every frame, a texture each: the tiger at the fit, 113 thin fills of its 227, takes
75 % longer when all of them move every frame (122 % with the size gate). An atlas for small masks and a limit on how
many are made a frame - Skia's 256 - are what that case needs before this is a default.
