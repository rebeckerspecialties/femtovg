# Patched (01-05) vs unpatched render equivalence

Unpatched reference: /private/tmp/wt-all3/target/debug/examples/_logos_full (corpus-all3 f05e2da, no patches, same harness minus instrumentation). Patched: /private/tmp/wt-pz release binary with all five patches. Same GPU (Metal), same env (SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1).

| render | px differing (>0) | px differing (>8) | max channel delta | frame px |
|---|---|---|---|---|
| Ghostscript_Tiger_1080p.ppm | 0 | 0 | 0 | 2073600 |
| Ghostscript_Tiger_640x480.ppm | 1 | 1 | 217 | 307200 |
| claude-fable-5-1_1080p.ppm | 0 | 0 | 0 | 2073600 |
| claude-fable-5-1_640x480.ppm | 0 | 0 | 0 | 307200 |
| claude-opus-5_1080p.ppm | 790 | 0 | 1 | 2073600 |
| claude-opus-5_640x480.ppm | 249 | 0 | 1 | 307200 |
| clipdemo_1080p.ppm | 0 | 0 | 0 | 2073600 |
| clipdemo_640x480.ppm | 0 | 0 | 0 | 307200 |
| duckduckgo-com_2x_1080p.ppm | 0 | 0 | 0 | 2073600 |
| duckduckgo-com_2x_640x480.ppm | 0 | 0 | 0 | 307200 |
| fox-with-box-on-cloud_1080p.ppm | 0 | 0 | 0 | 2073600 |
| fox-with-box-on-cloud_640x480.ppm | 0 | 0 | 0 | 307200 |
| fugu-ultra_1080p.ppm | 0 | 0 | 0 | 2073600 |
| fugu-ultra_640x480.ppm | 0 | 0 | 0 | 307200 |
| gemini-3-1-pro-preview-custom-tools_1080p.ppm | 969 | 0 | 1 | 2073600 |
| gemini-3-1-pro-preview-custom-tools_640x480.ppm | 198 | 0 | 1 | 307200 |
| gemini-3-1-pro-preview_1080p.ppm | 41 | 0 | 1 | 2073600 |
| gemini-3-1-pro-preview_640x480.ppm | 7 | 0 | 1 | 307200 |
| gemini-3-7-flash_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gemini-3-7-flash_640x480.ppm | 0 | 0 | 0 | 307200 |
| gemini-3-8-flash_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gemini-3-8-flash_640x480.ppm | 0 | 0 | 0 | 307200 |
| glm-5-3-flash_1080p.ppm | 0 | 0 | 0 | 2073600 |
| glm-5-3-flash_640x480.ppm | 0 | 0 | 0 | 307200 |
| glm-5-3_1080p.ppm | 0 | 0 | 0 | 2073600 |
| glm-5-3_640x480.ppm | 0 | 0 | 0 | 307200 |
| glm-5v-turbo_1080p.ppm | 0 | 0 | 0 | 2073600 |
| glm-5v-turbo_640x480.ppm | 0 | 0 | 0 | 307200 |
| google-workspace-48px_1080p.ppm | 0 | 0 | 0 | 2073600 |
| google-workspace-48px_640x480.ppm | 0 | 0 | 0 | 307200 |
| gpt-5-2-pro_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gpt-5-2-pro_640x480.ppm | 0 | 0 | 0 | 307200 |
| gpt-5-6-luna-pro_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gpt-5-6-luna-pro_640x480.ppm | 0 | 0 | 0 | 307200 |
| gpt-5-6-sol-pro_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gpt-5-6-sol-pro_640x480.ppm | 0 | 0 | 0 | 307200 |
| gpt-5-6-sol_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gpt-5-6-sol_640x480.ppm | 0 | 0 | 0 | 307200 |
| gpt-5-6-terra-pro_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gpt-5-6-terra-pro_640x480.ppm | 0 | 0 | 0 | 307200 |
| gpt-6-astra_1080p.ppm | 0 | 0 | 0 | 2073600 |
| gpt-6-astra_640x480.ppm | 0 | 0 | 0 | 307200 |
| grok-4-5_1080p.ppm | 0 | 0 | 0 | 2073600 |
| grok-4-5_640x480.ppm | 0 | 0 | 0 | 307200 |
| kimi-k2-6_1080p.ppm | 0 | 0 | 0 | 2073600 |
| kimi-k2-6_640x480.ppm | 0 | 0 | 0 | 307200 |
| kimi-k3_1080p.ppm | 0 | 0 | 0 | 2073600 |
| kimi-k3_640x480.ppm | 0 | 0 | 0 | 307200 |
| kit_1080p.ppm | 0 | 0 | 0 | 2073600 |
| kit_640x480.ppm | 0 | 0 | 0 | 307200 |
| mr-settodefault_1080p.ppm | 0 | 0 | 0 | 2073600 |
| mr-settodefault_640x480.ppm | 0 | 0 | 0 | 307200 |
| muse-spark-1-3-contributor_1080p.ppm | 403 | 0 | 1 | 2073600 |
| muse-spark-1-3-contributor_640x480.ppm | 116 | 0 | 1 | 307200 |
| muse-spark-1-3_1080p.ppm | 0 | 0 | 0 | 2073600 |
| muse-spark-1-3_640x480.ppm | 0 | 0 | 0 | 307200 |
| nex-n2-pro_1080p.ppm | 0 | 0 | 0 | 2073600 |
| nex-n2-pro_640x480.ppm | 0 | 0 | 0 | 307200 |
| ox-alpha_1080p.ppm | 0 | 0 | 0 | 2073600 |
| ox-alpha_640x480.ppm | 0 | 0 | 0 | 307200 |
| qwen3-8-2-4t-a95b_1080p.ppm | 0 | 0 | 0 | 2073600 |
| qwen3-8-2-4t-a95b_640x480.ppm | 0 | 0 | 0 | 307200 |
| qwen3-8-27b_1080p.ppm | 0 | 0 | 0 | 2073600 |
| qwen3-8-27b_640x480.ppm | 0 | 0 | 0 | 307200 |
| qwen3-8-flash_1080p.ppm | 0 | 0 | 0 | 2073600 |
| qwen3-8-flash_640x480.ppm | 0 | 0 | 0 | 307200 |
| qwen3-8-max_1080p.ppm | 0 | 0 | 0 | 2073600 |
| qwen3-8-max_640x480.ppm | 0 | 0 | 0 | 307200 |
| splash-logo_1080p.ppm | 0 | 0 | 0 | 2073600 |
| splash-logo_640x480.ppm | 0 | 0 | 0 | 307200 |

61 of 70 renders bit-identical.


## Patch 06 (fill_device_rect emits the rect's triangles directly) vs patches 01-05

Same binary lineage, one frame each, both framings: 70 of 70 renders bit-identical.

## Attribution of the eight <=1 LSB renders above

With patch 02's lone-blur branch disabled (`bin/patched_no02`, everything else applied) all six re-rendered files were bit-identical to the unpatched reference (claude-opus-5, gemini-3-1-pro-preview-custom-tools, gemini-3-1-pro-preview, muse-spark-1-3-contributor, claude-fable-5-1, gemini-3-8-flash at 640x480), so patches 01, 03, 05 are pixel-exact and the <=1 LSB deltas belong to patch 02 alone (it drops the identity color-matrix pass and its extra 8-bit unpremultiply/premultiply round trip). Against the Chromium 131 references at the harness's reference framing (460x260, BOX 200 at 130,30) the four affected files score identically with and without patch 02: claude-opus-5 px>20 0.29% / structural 0.000%, gemini-3-1-pro-preview-custom-tools 1.28% / 0.000%, gemini-3-1-pro-preview 2.15% / 0.003%, muse-spark-1-3-contributor 0.76% / 0.041% (max deltas 127/139/207/170 both ways); the patch is reference-neutral.

## Pre-existing multi-frame artifact (not from the patches)

Ghostscript_Tiger at 640x480 rendered with FRAMES>=2 differs from a single-frame render at exactly one pixel, (200,145): [204,114,38] in frame 1, white from frame 2 on. Reproducible (three runs), identical with the unpatched library, absent at FRAMES=1. Consistent with a stencil winding bit left behind by a concave fill whose cover quad missed that pixel; the stencil is never cleared between frames (clear_rect clears color only). Repro: FRAME_W=640 FRAME_H=480 BOX=480 BOX_X=80 BOX_Y=0 SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1 FRAMES=2 _logos_full 1.0 out.ppm examples/assets/Ghostscript_Tiger.svg vs FRAMES=1.
