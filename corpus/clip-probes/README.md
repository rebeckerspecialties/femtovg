# Clip-edge probes

What a renderer draws in the pixels that a clip's edge crosses, and what it does where that edge is also the
content's, another clip's or the viewport's. Frames are 460 x 260 at the `harness/corpus_run` framings (`z1` is the
fit, `z2` twice it); the references are Chromium 131 rasterizing in software (`--disable-gpu`, `refs.py`) and on the
GPU (ANGLE on Metal, `refs_gpu.py`), Firefox 158 and WebKit (Safari 27, `refs_webkit.py`). femtovg with stencil
clips is master 9d574e0; with shape clips, femtovg/femtovg#380 at 620b19c, where the scissor the harness cuts to the
viewport with is a box like the clip.

## Ink against the exact area

How much of the green fill each renderer drew at the fit, less the exact area of what the clip leaves of it, in pixels
(`harness/corpus_run/probe_ink.py`). A renderer that gives each edge pixel its share inside is at 0; one that
multiplies two coverages on a shared edge is short by about a sixth of a pixel per pixel of that edge.

| probe | exact px | femtovg, stencil clips | femtovg, shape clips | Chromium software | Chromium GPU | Firefox | WebKit |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rect-fill-fractional` | 1528 | +0.4 | +0.4 | +0.4 | +0.4 | +0.4 | -0.2 |
| `rect-clip-fractional` | 1528 | +2.4 | +0.4 | -0.0 | +0.4 | -0.0 | +0.1 |
| `rect-clip-coincident` | 1528 | -20.0 | +0.4 | -31.7 | +0.4 | -31.7 | -30.0 |
| `rounded-clip-coincident` | 4727 | -34.8 | -2.6 | -52.5 | -48.2 | -53.3 | -48.1 |
| `rotated-clip-coincident` | 4850 | -34.1 | +0.3 | -36.1 | -46.7 | -50.1 | -46.3 |
| `rect-clip-path-edge` | 4850 | -8.2 | -32.1 | -32.7 | -31.7 | -32.9 | -32.1 |
| `rect-clip-rect-inside` | 800 | -15.7 | +0.6 | -11.9 | +0.6 | -12.0 | -14.0 |
| `rect-clip-path-inside` | 3196 | -23.9 | +0.1 | -18.8 | +0.1 | -19.0 | -24.9 |
| `rounded-clip-rect-inside` | 1136 | +0.3 | +0.3 | -5.8 | +0.3 | -5.9 | -6.3 |
| `rounded-clip-rect-cover` | 4727 | -27.0 | +0.1 | -41.4 | +0.7 | -41.9 | -39.5 |
| `rounded-clip-path-cover` | 4727 | -27.0 | +0.1 | -43.3 | +0.7 | -41.9 | -39.3 |
| `rounded-clip-rect-band` | 2325 | -25.4 | -22.0 | -18.3 | -21.6 | -18.4 | -23.1 |
| `nested-twin-clips` | 1528 | +2.4 | +0.4 | -0.0 | +0.4 | -33.3 | -29.8 |
| `nested-twin-rounded-clips` | 4727 | +2.5 | +0.1 | -52.5 | +0.7 | -53.3 | -48.1 |
| `viewport-fill` | 30289 | -49.0 | +0.4 | -44.3 | +0.4 | -89.0 | -49.8 |
| `viewport-path-edge` | 16470 | -31.7 | +0.7 | -16.4 | +0.7 | -49.9 | -35.0 |
| `viewport-overflow` | 30289 | +0.4 | +0.4 | +11.4 | +0.4 | -89.0 | -0.4 |
| `viewport-clip-twin` | 30289 | -89.0 | +0.4 | +10.8 | +0.4 | -89.0 | -49.8 |
| `viewport-clip-twin-fill` | 30289 | -89.0 | +0.4 | -44.9 | +0.4 | -89.0 | -71.8 |

## Edge pixels

The coverage of the pixel each side crosses, half way along it - left, right, top, bottom, or the sides a probe is
about - next to that pixel's share inside (`harness/corpus_run/probe_edges.py`).

| probe | framing | exact | femtovg, stencil clips | femtovg, shape clips | Chromium software | Chromium GPU | Firefox | WebKit |
|---|---|---|---|---|---|---|---|---|
| `rect-fill-fractional` | z1 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 |
| `rect-clip-fractional` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .70 .80 .50 .75 | .70 .80 .40 .85 | .70 .80 .50 .75 | .70 .80 .40 .85 |
| `rect-clip-coincident` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .70 .80 .40 .85 | .49 .64 .20 .64 | .70 .80 .40 .85 | .49 .64 .20 .64 | .49 .64 .16 .72 |
| `rounded-clip-coincident` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .70 .80 .40 .85 | .49 .64 .25 .57 | .49 .64 .16 .73 | .49 .64 .25 .57 | .49 .64 .16 .73 |
| `rect-clip-rect-inside` | z1 | .70 .40 | .70 0 | .70 .40 | .49 .20 | .70 .40 | .49 .20 | .49 .16 |
| `rect-clip-path-inside` | z1 | .70 .40 | .70 0 | .70 .40 | .49 .25 | .70 .40 | .48 .25 | .49 .16 |
| `rounded-clip-rect-inside` | z1 | .70 | .70 | .70 | .49 | .70 | .49 | .49 |
| `rounded-clip-rect-cover` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .70 .80 .40 .85 | .49 .64 .20 .64 | .70 .80 .40 .85 | .49 .64 .20 .64 | .49 .64 .16 .72 |
| `rounded-clip-path-cover` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .70 .80 .40 .85 | .49 .64 .25 .56 | .70 .80 .40 .85 | .49 .64 .20 .64 | .49 .64 .16 .72 |
| `rounded-clip-rect-band` | z1 | .70 .80 .40 | .70 .80 0 | .49 .64 .16 | .49 .64 .20 | .49 .64 .16 | .49 .64 .20 | .49 .64 .16 |
| `nested-twin-clips` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .70 .80 .50 .75 | .70 .80 .40 .85 | .49 .64 .25 .56 | .49 .64 .16 .72 |
| `nested-twin-rounded-clips` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .49 .64 .25 .57 | .70 .80 .40 .85 | .49 .64 .25 .57 | .49 .64 .16 .73 |
| `viewport-fill` | z1 | .45 | .20 | .45 | .22 | .45 | 0 | .20 |
| `viewport-path-edge` | z1 | .45 | .20 | .45 | .25 | .45 | 0 | .20 |
| `viewport-clip-twin` | z1 | .45 | 0 | .45 | .50 | .45 | 0 | .20 |
| `viewport-clip-twin-fill` | z1 | .45 | 0 | .45 | .22 | .45 | 0 | .09 |
| `rect-clip-half-pixel` | z1 | .75 .75 | 1 .99 | .75 .75 | .75 .75 | .75 .75 | .57 .56 | .75 .75 |
| `rect-clip-half-pixel` | z2 | .50 .50 | 1 0 | .51 .49 | .51 .49 | .50 .50 | .25 0 | .51 .49 |
| `path-clip-half-pixel` | z1 | .75 .75 | 1 .99 | .75 .75 | .57 .56 | .56 .56 | .57 .56 | .75 .75 |
| `path-clip-half-pixel` | z2 | .50 .50 | 1 0 | .50 .50 | .25 .24 | .50 .50 | .25 0 | .51 .49 |

## What each does

- A stencil clip takes a pixel whole or not at all: a row the clip covers .40 or .45 of is dropped.
- The software rasterizers and WebKit antialias a clip's edge and multiply its coverage with the content's wherever
  the two meet: .49 where a .70 edge meets itself. WebKit does so with the exact shares; the software rasterizers
  resolve a path's edge vertically to a quarter pixel (.40 reads .50, .85 reads .75), and a clip drawn as a path with
  curves reads as the square of its coverage in Chromium. Firefox and WebKit multiply nested clips with one outline
  too, and Chromium the rounded ones. Firefox draws nothing in the row the viewport's edge crosses.
- Chromium's GPU rasterizer covers an edge once where a draw stays inside its clip (`rect-clip-rect-inside`,
  `rect-clip-path-inside`, `rounded-clip-rect-inside`), where an upright rect clip cuts an upright rect
  (`rect-clip-coincident`), where an upright rect covers a rounded clip (`rounded-clip-*-cover`), where clips nest
  (`nested-twin-*`) and on the viewport (`viewport-*`). It multiplies where a rounded or a turned clip meets its twin
  at the fit - at 2x and 4x it counts the rounded twin once - and where a path that is no rect ends on a rect clip's
  edge and reaches past it elsewhere. Its tests are exact in floats and made per raster tile, so the same file can
  come out either way at another zoom.
- The shape clip does what the GPU rasterizer does in each of these, by a tolerance of a 64th of a pixel, and holds a
  draw by the points of its outline as well, so that a rounded or a turned clip's twin is covered once at every
  scale: on 17 of the 19 probes its ink is within a pixel of that rasterizer's - the other two are those twins - and
  on 16 within a pixel of the exact area (stencil clips 3, WebKit 3, software Chromium 3, Firefox 2). Of the three
  left, the rounded twin is drawn as without its clip to the bit, a fill that is itself 3 px short of its area; the
  other two multiply in every renderer: the path on a rect clip's edge, and a rect band across a rounded clip.

## Against the exact area

The circle and ellipse clip-path reftests (`corpus/wpt-clip-path-reftests`) at four framings against each pixel's
share inside the ellipse, from 16 x 16 samples (`harness/corpus_run/ideal_clip.py`):

| | femtovg, stencil clips | femtovg, shape clips | Chromium software | Chromium GPU | Firefox |
|---|---:|---:|---:|---:|---:|
| largest error, of 255 | 165 | 13 | 70 | 36 | 73 |
| pixels beyond 20/255, worst frame | 0.48 % | 0 | 0.27 % | 0.26 % | 0.31 % |
