# Clip-edge probes

What a renderer draws in the pixels that a clip's edge crosses, and what it does where that edge is also the
content's, another clip's or the viewport's. Frames are 460 x 260 at the `harness/corpus_run` framings (`z1` is the
fit, `z2` twice it); the references are Chromium 131 rasterizing in software (`--disable-gpu`, `refs.py`) and on the
GPU (ANGLE on Metal, `refs_gpu.py`) and Firefox 158. femtovg with stencil clips is master 9d574e0; with shape clips,
femtovg/femtovg#380.

## Ink against the exact area

How much of the green fill each renderer drew at the fit, less the exact area of what the clip leaves of it, in pixels
(`harness/corpus_run/probe_ink.py`). A renderer that gives each edge pixel its share inside is at 0; one that
multiplies two coverages on a shared edge is short by about a sixth of a pixel per pixel of that edge.

| probe | exact px | femtovg, stencil clips | femtovg, shape clips | Chromium software | Chromium GPU | Firefox |
|---|---:|---:|---:|---:|---:|---:|
| `rect-fill-fractional` | 1528 | +0.4 | +0.4 | +0.4 | +0.4 | +0.4 |
| `rect-clip-fractional` | 1528 | +2.4 | +0.4 | -0.0 | +0.4 | -0.0 |
| `rect-clip-coincident` | 1528 | -20.0 | +0.4 | -31.7 | +0.4 | -31.7 |
| `rounded-clip-coincident` | 4727 | -34.8 | -48.8 | -52.5 | -48.2 | -53.3 |
| `rotated-clip-coincident` | 4850 | -34.1 | -46.6 | -36.1 | -46.7 | -50.1 |
| `rect-clip-path-edge` | 4850 | -8.2 | -32.1 | -32.7 | -31.7 | -32.9 |
| `rect-clip-rect-inside` | 800 | -15.7 | +0.6 | -11.9 | +0.6 | -12.0 |
| `rounded-clip-rect-inside` | 1136 | +0.3 | +0.3 | -5.8 | +0.3 | -5.9 |
| `nested-twin-clips` | 1528 | +2.4 | +0.4 | -0.0 | +0.4 | -33.3 |
| `nested-twin-rounded-clips` | 4727 | +2.5 | +0.1 | -52.5 | +0.7 | -53.3 |
| `viewport-fill` | 30289 | -49.0 | -49.0 | -44.3 | +0.4 | -89.0 |
| `viewport-overflow` | 30289 | +0.4 | +0.4 | +11.4 | +0.4 | -89.0 |
| `viewport-clip-twin` | 30289 | -89.0 | +0.4 | +10.8 | +0.4 | -89.0 |
| `viewport-clip-twin-fill` | 30289 | -89.0 | +0.4 | -44.9 | +0.4 | -89.0 |

## Edge pixels

The coverage of the pixel each side crosses, half way along it - left, right, top, bottom, or the sides a probe is
about - next to that pixel's share inside (`harness/corpus_run/probe_edges.py`).

| probe | framing | exact | femtovg, stencil clips | femtovg, shape clips | Chromium software | Chromium GPU | Firefox |
|---|---|---|---|---|---|---|---|
| `rect-fill-fractional` | z1 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 |
| `rect-clip-fractional` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .70 .80 .50 .75 | .70 .80 .40 .85 | .70 .80 .50 .75 |
| `rect-clip-coincident` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .70 .80 .40 .85 | .49 .64 .20 .64 | .70 .80 .40 .85 | .49 .64 .20 .64 |
| `rounded-clip-coincident` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .49 .64 .16 .73 | .49 .64 .25 .57 | .49 .64 .16 .73 | .49 .64 .25 .57 |
| `rect-clip-rect-inside` | z1 | .70 .40 | .70 0 | .70 .40 | .49 .20 | .70 .40 | .49 .20 |
| `rounded-clip-rect-inside` | z1 | .70 | .70 | .70 | .49 | .70 | .49 |
| `nested-twin-clips` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .70 .80 .50 .75 | .70 .80 .40 .85 | .49 .64 .25 .56 |
| `nested-twin-rounded-clips` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .49 .64 .25 .57 | .70 .80 .40 .85 | .49 .64 .25 .57 |
| `viewport-fill` | z1 | .45 | .20 | .20 | .22 | .45 | 0 |
| `viewport-clip-twin` | z1 | .45 | 0 | .45 | .50 | .45 | 0 |
| `viewport-clip-twin-fill` | z1 | .45 | 0 | .45 | .22 | .45 | 0 |
| `rect-clip-half-pixel` | z1 | .75 .75 | 1 .99 | .75 .75 | .75 .75 | .75 .75 | .57 .56 |
| `rect-clip-half-pixel` | z2 | .50 .50 | 1 0 | .51 .49 | .51 .49 | .50 .50 | .25 0 |
| `path-clip-half-pixel` | z1 | .75 .75 | 1 .99 | .75 .75 | .57 .56 | .56 .56 | .57 .56 |
| `path-clip-half-pixel` | z2 | .50 .50 | 1 0 | .50 .50 | .25 .24 | .50 .50 | .25 0 |

## What each does

- A stencil clip takes a pixel whole or not at all: a row the clip covers .40 or .45 of is dropped.
- The software rasterizers antialias a clip's edge and multiply its coverage with the content's wherever the two
  meet: .49 where a .70 edge meets itself. Firefox multiplies nested clips with one outline too, and Chromium the
  rounded ones. Vertically both resolve a path's edge to a quarter pixel (.40 reads .50, .85 reads .75), and a clip
  drawn as a path with curves reads as the square of its coverage in Chromium. Firefox draws nothing in the row the
  viewport's edge crosses.
- Chromium's GPU rasterizer covers an edge once where a draw stays inside its clip (`rect-clip-rect-inside`,
  `rounded-clip-rect-inside`), where an upright rect clip cuts an upright rect (`rect-clip-coincident`), and where
  clips nest or lie on the viewport (`nested-twin-*`, `viewport-clip-twin*`). It multiplies where a rounded or a
  turned clip meets its twin and where a path that is no rect ends on a rect clip's edge.
- The shape clip does what the GPU rasterizer does in each of these: 13 of the 14 probes are within a pixel of its
  ink (3 with stencil clips). The one left, `viewport-fill`, has no clip: the harness cuts to the viewport with a
  scissor, whose coverage multiplies the fill's own (.20 for .45) on master as here.

## Against the exact area

The circle and ellipse clip-path reftests (`corpus/wpt-clip-path-reftests`) at four framings against each pixel's
share inside the ellipse, from 16 x 16 samples (`harness/corpus_run/ideal_clip.py`):

| | femtovg, stencil clips | femtovg, shape clips | Chromium software | Chromium GPU | Firefox |
|---|---:|---:|---:|---:|---:|
| largest error, of 255 | 165 | 13 | 70 | 36 | 73 |
| pixels beyond 20/255, worst frame | 0.48 % | 0 | 0.27 % | 0.26 % | 0.31 % |
