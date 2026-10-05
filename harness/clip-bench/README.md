# What a shape clip costs

Frame time at 1920 x 1080 on an Apple M4 Max, femtovg master (9d574e0) -> shape clips (femtovg/femtovg#380 at
131597f). The two builds run back to back with the order alternating; the times are the medians and the percentage
is the median of the paired differences. `paired.py` drives the SVG pages through the wgpu harness (`_logos_full`,
`FRAMES` frames after the first); `gl_fill_bench.rs` draws the same scenes with the OpenGL backend into an image
target behind a hidden window, and `glpaired.py` compares two builds of it.

| scene | wgpu (Metal) | OpenGL (Apple's) |
|---|---:|---:|
| 40 full-screen fills, no clip | 1.40 -> 1.41 ms (+0.2 %) | 0.74 -> 0.74 ms (0.0 %) |
| 40 full-screen paths, no clip | 1.41 -> 1.43 ms (+1.3 %) | 0.76 -> 0.75 ms (-0.7 %) |
| 200 cards, no clip | 2.81 -> 2.86 ms (+1.5 %) | 0.43 -> 0.44 ms (+1.9 %) |
| 200 cards, each under a rounded-rect clip | 13.8 -> 3.1 ms | 6.2 -> 0.67 ms |
| 200 cards, each under a circle clip | 13.8 -> 3.1 ms | |
| 40 full-screen fills under a rect clip | 1.53 -> 1.39 ms (-9.0 %) | 0.83 -> 0.78 ms (-7.7 %) |
| under a rounded-rect clip | 1.52 -> 1.43 ms (-5.1 %) | 0.86 -> 1.02 ms (+16.9 %) |
| under an ellipse clip | 1.52 -> 1.52 ms (+0.5 %) | 0.76 -> 1.13 ms (+47.5 %) |
| under a rect clip of 400 x 300 | 1.50 -> 0.89 ms (-41.2 %) | 0.49 -> 0.14 ms (-67.8 %) |
| under a rounded-rect clip of 400 x 300 | 1.53 -> 0.89 ms (-41.1 %) | 0.47 -> 0.17 ms (-61.2 %) |
| 40 full-screen paths under a rounded-rect clip | | 0.87 -> 0.99 ms (+14.5 %) |
| under an ellipse clip | | 0.81 -> 1.14 ms (+41.8 %) |
| under a rounded-rect clip of 400 x 300 | 1.55 -> 0.96 ms (-37.6 %) | 0.51 -> 0.16 ms (-64.9 %) |

Thirty pairs a row for the fills on wgpu and twelve on OpenGL, fourteen for the cards; a repeat of an unclipped row
moves by up to 2 % either way.

A stencil clip costs draws and a replay per clip and nothing per fragment; a shape clip costs nothing per clip and a
few operations per fragment under it. Only a draw under a shape runs the shader variant that evaluates one: with a
uniform switch in the one shader instead, the 40 unclipped fills cost 2.7 % more on wgpu and 17 % more on OpenGL. A
draw under a shape is scissored to the pixels the shape reaches, so a clip smaller than the content under it costs
less than its stencil did - without the scissor the paths under the small clip cost 7 % more. A rect filled under an
upright rect clip is cut to the clip and carries none, and a draw the clip holds whole needs none either, but after
a draw that carried the shape it carries a coverage of one and stays on that variant: switching for it cost the 200
clipped cards 28 % on OpenGL. What is left to pay is fill-bound content that crosses a clip as large as the target:
nothing on wgpu, and on OpenGL the fragments' arithmetic - a sixth more under a rounded rect, whose corners few
fragments are near, and nearly half more under an ellipse, where every fragment takes the corner's path.

Recording a fill costs the canvas 5 to 10 ns more than master's 230 to 310 (`draw_cost.rs`, the Void renderer), and
the 600 unclipped fills of the cards page take about 2 % longer to encode under a scissor that holds them, nothing
without one. Over the corpus, every file at the fit and at 1080p (2,392 frames, `corpus_run/pass_time.py`), the
frames take 7,647 -> 7,635 ms in sum and the median frame 1.0 % less.

`gl_clip_check.rs` is the OpenGL backend's run-time check: eleven clips (plain, turned, skewed, tight corners, one
pixel thick) against each pixel's exact share inside the shape, worst difference 0.048, and a concave fill under a
small shape that must leave neither winding nor scissor behind, in an image and in the window. `gl_mask_check.rs`
and `gl_crop_check.rs` are the same for coverage masks and for `ImageFilter::Crop`.
