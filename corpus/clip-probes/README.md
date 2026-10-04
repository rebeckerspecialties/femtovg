# Clip-edge probes

What a renderer draws in the pixel that a clip's edge crosses. Each cell is the coverage of the edge pixel on the
left, right, top and bottom side of the clip, read from the frame (460 x 260, the `harness/corpus_run` framings; `z1` is
the fit, `z2` twice it); `exact` is the share of that pixel inside the clip. Chromium 131 headless shell and Firefox 158,
both rasterizing in software.

| probe | framing | exact | femtovg, stencil clips (9d574e0) | femtovg, shape clips | Chromium | Firefox |
|---|---|---|---|---|---|---|
| `rect-fill-fractional` (no clip) | z1 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 | .70 .80 .40 .85 |
| `rect-clip-fractional` | z1 | .70 .80 .40 .85 | 1 1 0 1 | .70 .80 .40 .85 | .70 .80 .50 .75 | .70 .80 .50 .75 |
| `rect-clip-coincident` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .49 .64 .16 .73 | .49 .64 .20 .64 | .49 .64 .20 .64 |
| `rounded-clip-coincident` | z1 | .70 .80 .40 .85 | .70 .80 0 .85 | .49 .64 .16 .73 | .49 .64 .25 .57 | .49 .64 .25 .57 |
| `rect-clip-half-pixel` | z1 | .75 .75 | 1 .99 | .75 .74 | .75 .75 | .57 .56 |
| `rect-clip-half-pixel` | z2 | .50 .50 | 1 0 | .50 .49 | .51 .49 | .25 0 |
| `path-clip-half-pixel` | z1 | .75 .75 | 1 .99 | .75 .74 | .57 .56 | .57 .56 |
| `path-clip-half-pixel` | z2 | .50 .50 | 1 0 | .50 .49 | .25 .24 | .25 0 |

- A stencil clip takes a pixel whole or not at all.
- Both browsers antialias a clip's edge, and where the content ends on the same edge they multiply the two
  coverages (.49 where a .70 edge meets itself). The shape clip does the same.
- Vertically the browsers resolve a path's edge to a quarter pixel, as a clip or as the fill of a rounded rect: .40
  reads .50 and .85 reads .75. A plain rect fill is exact.
- A clip drawn as a path with curves reads as the square of its coverage in Chromium (.25 for .50, .57 for .75).
  Firefox reads that way for every clip on the letterboxed frame, and draws nothing in a column covered .495.

## Against the exact area

The circle and ellipse clip-path reftests (`corpus/wpt-clip-path-reftests`) at four framings against each pixel's
share inside the ellipse, from 16 x 16 samples (`harness/corpus_run/ideal_clip.py`):

| | femtovg, stencil clips | femtovg, shape clips | Chromium | Firefox |
|---|---:|---:|---:|---:|
| largest error, of 255 | 165 | 13 | 70 | 73 |
| pixels beyond 20/255, worst frame | 0.48 % | 0 | 0.27 % | 0.31 % |
