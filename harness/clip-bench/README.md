# What a shape clip costs

Frame time at 1920 x 1080 on an Apple M4 Max, femtovg master (9d574e0) -> shape clips. The two builds run back to
back with the order alternating; the times are the medians and the percentage is the median of the paired
differences. `paired.py` drives the SVG pages through the wgpu harness (`_logos_full`, `FRAMES` frames after the
first); `gl_fill_bench.rs` draws the same scenes with the OpenGL backend into an image target behind a hidden window,
and `glpaired.py` compares two builds of it.

| scene | wgpu (Metal) | OpenGL (Apple's) |
|---|---:|---:|
| 40 full-screen fills, no clip | 1.47 -> 1.45 ms (0.0 %) | 0.78 -> 0.78 ms (-0.7 %) |
| 200 cards, no clip | 2.97 -> 3.00 ms (+1.3 %) | 0.46 -> 0.46 ms (+0.6 %) |
| 200 cards, each under a rounded-rect clip | 14.2 -> 3.2 ms | 6.5 -> 0.64 ms |
| 200 cards, each under a circle clip | 14.0 -> 3.1 ms | |
| 40 full-screen fills under a rect clip | 1.60 -> 1.48 ms (-6.0 %) | 0.83 -> 0.79 ms (-6.1 %) |
| 40 full-screen fills under a rounded-rect clip | 1.51 -> 1.52 ms (+0.3 %) | 0.81 -> 0.94 ms (+15 %) |
| 40 full-screen fills under an ellipse clip | 1.51 -> 1.59 ms (+4.6 %) | |

Thirty pairs a row for the fills, fourteen for the clipped cards; a repeat of an unclipped row moves by up to 2 %
either way.

A stencil clip costs draws and a replay per clip and nothing per fragment; a shape clip costs nothing per clip and a
few operations per fragment under it. Only a draw under a shape runs the shader variant that evaluates one: with a
uniform switch in the one shader instead, the 40 unclipped fills cost 2.7 % more on wgpu and 17 % more on OpenGL. A
rect filled under an upright rect clip is cut to the clip and carries none, so those fills cost less than under the
stencil. A draw the clip holds whole needs none either, but after a draw that carried the shape it carries a
coverage of one and stays on that variant: switching for it cost the 200 clipped cards 28 % on OpenGL.

`gl_clip_check.rs` is the OpenGL backend's run-time check: eleven clips (plain, turned, skewed, tight corners, one
pixel thick) against each pixel's exact share inside the shape, worst difference 0.048.
