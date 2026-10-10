# What a shape clip costs

Frame time at 1920 x 1080 on an Apple M4 Max, femtovg master (9d574e0) -> shape clips (femtovg/femtovg#380 at
620b19c). The two builds run back to back with the order alternating; the times are the medians and the percentage
is the median of the paired differences. `paired.py` drives the SVG pages through the wgpu harness (`_logos_full`,
`FRAMES` frames after the first); `gl_fill_bench.rs` draws the same scenes with the OpenGL backend into an image
target behind a hidden window, and `glpaired.py` compares two builds of it.

| scene | wgpu (Metal) | OpenGL (Apple's) |
|---|---:|---:|
| 40 full-screen fills, no clip | 1.08 -> 1.10 ms (+1.3 %) | 0.77 -> 0.77 ms (+0.5 %) |
| 40 full-screen paths, no clip | 1.11 -> 1.11 ms (+0.1 %) | 0.78 -> 0.77 ms (-0.9 %) |
| 200 cards, no clip | 2.22 -> 2.24 ms (+1.1 %) | 0.40 -> 0.41 ms (+0.8 %) |
| 200 cards, each under a rounded-rect clip | 11.7 -> 2.8 ms | 6.9 -> 0.64 ms |
| 200 cards, each under a circle clip | 11.8 -> 2.7 ms | |
| 40 full-screen fills under a rect clip | 1.20 -> 1.09 ms (-8.9 %) | 0.78 -> 0.76 ms (-3.5 %) |
| under a rounded-rect clip | 1.20 -> 1.14 ms (-4.7 %) | 0.81 -> 0.96 ms (+18.6 %) |
| under an ellipse clip | 1.19 -> 1.19 ms (0.0 %) | 0.79 -> 1.13 ms (+44.8 %) |
| under a rect clip of 400 x 300 | 1.14 -> 0.65 ms (-43.2 %) | 0.48 -> 0.15 ms (-67.7 %) |
| under a rounded-rect clip of 400 x 300 | 1.14 -> 0.64 ms (-43.7 %) | 0.37 -> 0.18 ms (-53.0 %) |
| 40 full-screen paths under a rounded-rect clip | | 0.80 -> 0.94 ms (+18.1 %) |
| under an ellipse clip | | 0.73 -> 1.07 ms (+48.3 %) |
| under a rounded-rect clip of 400 x 300 | 1.14 -> 0.68 ms (-40.3 %) | 0.48 -> 0.17 ms (-65.6 %) |

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
nothing on wgpu, and on OpenGL the fragments' arithmetic - nearly a fifth more under a rounded rect, whose corners
few fragments are near, and nearly half more under an ellipse, where every fragment takes the corner's path.

Recording a fill costs the canvas 5 to 10 ns more than master's 230 to 310 (`draw_cost.rs`, the Void renderer), and
the 600 unclipped fills of the cards page take about 2 % longer to encode under a scissor that holds them, 1 % in
instructions, and half a percent without one. The 40 unclipped fills reach past the viewport, which the harness
makes a scissor: each is cut to it and flattened a second time, 0.3 us. Over the corpus, every file at the fit and
at 1080p (2,392 frames, `corpus_run/pass_time.py`), the frames take 5,980 -> 5,957 ms in sum and the median frame
as long as it did (+0.1 %).

`gl_clip_check.rs` is the OpenGL backend's run-time check: eleven clips (plain, turned, skewed, tight corners, one
pixel thick) against each pixel's exact share inside the shape, worst difference 0.048, and a concave fill under a
small shape that must leave neither winding nor scissor behind, in an image and in the window. `gl_mask_check.rs`
and `gl_crop_check.rs` are the same for coverage masks and for `ImageFilter::Crop`. `mask_cost.rs` is `draw_cost.rs`
for a clip that is no box: what taking it and filling a rect under it costs the canvas once its mask exists, with
masks and with the stencil.

## The tools

`../build.sh --gl TAG:SRC` builds `gl_fill_bench`, `gl_clip_check` and `gl_svg_dump` against the femtovg checkout
SRC into `$HARNESS_BIN/<tool>_TAG` (`GL_EXAMPLES` names others, e.g. `gl_crop_check gl_mask_check`). Then, for two
builds A and B:

- `glpaired.py A B PAIRS FRAMES scene...`: frame time of `gl_fill_bench`, alternating, with the paired difference.
- `gl_instr.py A B -- scene...`: instructions retired a frame (a long run minus a short one; macOS `/usr/bin/time -l`).
- `gl_clip_check_A` and `gl_clip_check_B`: each prints the clip checks; diff the two outputs.
- `gl_svg_dump_A OUT.ppm SCALE FILE.svg`: the OpenGL backend's pixels for an SVG's solid fills and strokes, to
  compare two builds byte for byte.

`paired.py` does the wgpu harness's pages the same way; `draw_cost.rs` and `mask_cost.rs` are Void-renderer
benches of the canvas side.
