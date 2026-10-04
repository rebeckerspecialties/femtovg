# What a shape clip costs

Frame time at 1920 x 1080 on an Apple M4 Max, femtovg master (9d574e0) -> shape clips. The two builds run back to
back with the order alternating; the times are the medians and the percentage is the median of the paired
differences. `paired.py` drives the SVG pages through the wgpu harness (`_logos_full`, `FRAMES` frames after the
first); `gl_fill_bench.rs` draws the same scenes with the OpenGL backend into an image target behind a hidden window,
and `glpaired.py` compares two builds of it.

| scene | wgpu (Metal) | OpenGL (Apple's) |
|---|---:|---:|
| 40 full-screen fills, no clip | 0.92 -> 0.92 ms (-0.3 %) | 0.82 -> 0.81 ms (-1.4 %) |
| 200 cards, no clip | 2.11 -> 2.08 ms (-0.3 %) | 0.42 -> 0.42 ms (+1.1 %) |
| 200 cards, each under a rounded-rect clip | 13.5 -> 2.6 ms | 8.2 -> 0.6 ms |
| 200 cards, each under a circle clip | 14.9 -> 2.5 ms | |
| 40 full-screen fills under a rect clip | 0.98 -> 1.00 ms (+2.3 %) | 0.79 -> 0.91 ms (+15 %) |
| 40 full-screen fills under a rounded-rect clip | 0.99 -> 1.03 ms (+3.2 %) | 0.98 -> 1.17 ms (+19 %) |
| 40 full-screen fills under an ellipse clip | 0.97 -> 1.07 ms (+9.1 %) | |

A stencil clip costs draws and a replay per clip and nothing per fragment; a shape clip costs nothing per clip and a
few operations per fragment under it. Only a draw under a shape runs the shader variant that evaluates one: with a
uniform switch in the one shader instead, the 40 unclipped fills cost 2.7 % more on wgpu and 17 % more on OpenGL.

`gl_clip_check.rs` is the OpenGL backend's run-time check: eleven clips (plain, turned, skewed, tight corners, one
pixel thick) against each pixel's exact share inside the shape, worst difference 0.048.
