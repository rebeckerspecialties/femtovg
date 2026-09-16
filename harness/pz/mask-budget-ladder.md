# Transient-budget ladder with masks on the fixed #323 tree (1080p)

Date 2026-09-16. Tree: `le-fix` in /private/tmp/wt-le at dc0f9a9 (#323 layer masks with the review fixes: 0bd7e9f nested-mask root origin, 048ddf3 kept scissor in the padded store, dc0f9a9 filter-chain images reserved at `begin_layer`; upstream/master 83ea071 merged). Harness: the gated `_logos_full.rs` (scratchpad `harness_gated.rs`) copied to `examples/_logos_full.rs` and built with `cargo build --example _logos_full --features wgpu`, no RUSTFLAGS, so `harness cfgs: clip=false turbulence=false`: clip paths draw unclipped (#324 absent) and feTurbulence chains are left to SKIP_UNSUPPORTED_FILTERS (#338 absent). wgpu/Metal, debug build.

Framing: `FRAME_W=1920 FRAME_H=1080 BOX=1080 BOX_X=420 BOX_Y=0 SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1 LAYER_STATS=1 _logos_full 1.0 out.ppm file.svg`, budget through the harness's existing `TRANSIENT_BUDGET_MB=<MiB>` (examples/_logos_full.rs:814-819 calls `Canvas::set_transient_image_budget(mb << 20)` right after `Canvas::new`; no harness change was needed for that). References: Chromium 131 headless-shell at 1920x1080 from `make_ref.py <svg> 1.0` under the same framing env, `--force-device-scale-factor=1`.

Files: every BuseyBench SVG containing `<mask` (15: claude-fable-5-1, fugu-ultra, glm-5-3, gpt-5-2-pro, gpt-5-6-luna-pro, gpt-5-6-sol-pro, gpt-5-6-sol, gpt-6-astra, grok-4-5, nex-n2-pro, ox-alpha, qwen3-8-2-4t-a95b, qwen3-8-27b, qwen3-8-flash, qwen3-8-max), corpus/mask-luminance-radial-transform.svg, corpus/mask-nested-origin-reduction.svg, and google-workspace-48px.svg (the `$S/da/gws.svg` named in the brief does not exist; the icon is /private/tmp/wt-da/google-workspace-48px.svg). gpt-5-6-sol-pro (`mask id="faceFade"`) and grok-4-5 (`mask id="hairMask"`) define a mask nothing references (no `mask="url(...)"`), so the harness captures 0 masks for them; they stay in the table as listed.

## What each column is

* **masks**: mask images the harness captured (`LAYER_LOG=1` `MASK` lines). They are harness-owned frame-sized RGBA8 images (1920x1080x4 = 7.9 MiB each) outside the transient pool and the budget.
* **admitted**: layers `begin_layer` accepted / layers begun (`LAYER_STATS=1`: `layers begun`, `layers passed through`). On the fixed tree a layer reserves its store, the mask's coverage images (one for an alpha mask, two for luminance) and the filter chain's result and scratches at `begin_layer` (src/lib.rs:1417-1449), so `false` is the whole story: a layer is admitted with every declared effect or passes through as a whole. For rows with pass-throughs the parenthesis says how many of the refused layers carried a mask and how many were nested (depth 2), from a `PASS` line added to the harness copy for this run.
* **peak MiB**: `canvas.transient_image_bytes()` sampled just before `flush_to_output` (`transient bytes held at flush`). The pool never frees within a frame - `TransientPool.bytes` only decreases in `release_all` at the flush (src/transient.rs:107-124) - so the figure at the flush is the frame's peak live transient bytes.
* **vs Chromium**: `compare.py render.ppm chr.png` over the 1920x1080 frame: % of pixels with max-channel delta > 20, the same after 2 px erosion (structural), max delta; then `boxstats.py` (BOXRECT 420,0,1080) % of the 1080x1080 SVG box, the unit the pre-#323 ladder used.
* **vs 256 MiB**: `compare.py --exact` of the row's render against the same file rendered at the default 256 MiB on the same build: the budget's own effect, isolated from everything the build renders differently from Chromium (unclipped clip paths, no feTurbulence). `0 px` means bit-identical.

## 48 MiB, fixed #323 tree (le-fix dc0f9a9)

| file | masks | admitted | peak MiB | vs Chromium frame px>20 / structural / max | vs Chromium box px>20 / structural | vs 256 MiB (px differ, px>20 %, max) |
|---|---|---|---|---|---|---|
| claude-fable-5-1 | 1 | 177/177 | 33.8 | 2.55 % / 0.995 % / 154 | 4.526 % / 1.769 % | identical |
| fugu-ultra | 2 | 124/124 | 43.2 | 0.97 % / 0.592 % / 152 | 1.729 % / 1.052 % | identical |
| glm-5-3 | 1 | 129/129 | 38.3 | 0.76 % / 0.494 % / 137 | 1.358 % / 0.879 % | identical |
| gpt-5-2-pro | 2 | 46/53 (0 masked, 7 nested) | 45.1 | 7.96 % / 5.669 % / 148 | 14.151 % / 10.078 % | 86222 px (4.16 %), 2.21 %, max 57 |
| gpt-5-6-luna-pro | 1 | 33/33 | 28.7 | 0.29 % / 0.140 % / 93 | 0.511 % / 0.249 % | identical |
| gpt-5-6-sol-pro | 0 | 41/41 | 41.7 | 2.75 % / 1.620 % / 178 | 4.883 % / 2.880 % | identical |
| gpt-5-6-sol | 1 | 48/48 | 28.7 | 0.84 % / 0.507 % / 90 | 1.492 % / 0.901 % | identical |
| gpt-6-astra | 1 | 162/162 | 28.7 | 1.17 % / 0.674 % / 186 | 2.086 % / 1.197 % | identical |
| grok-4-5 | 0 | 76/76 | 39.3 | 0.11 % / 0.000 % / 206 | 0.200 % / 0.000 % | identical |
| nex-n2-pro | 2 | 102/102 | 44.3 | 4.89 % / 4.150 % / 105 | 8.702 % / 7.378 % | identical |
| ox-alpha | 1 | 93/93 | 28.7 | 0.21 % / 0.019 % / 135 | 0.370 % / 0.034 % | identical |
| qwen3-8-2-4t-a95b | 1 | 198/198 | 44.0 | 1.64 % / 1.133 % / 90 | 2.914 % / 2.014 % | identical |
| qwen3-8-27b | 1 | 100/100 | 34.3 | 0.85 % / 0.465 % / 89 | 1.514 % / 0.827 % | identical |
| qwen3-8-flash | 2 | 117/117 | 43.2 | 1.91 % / 1.188 % / 160 | 3.390 % / 2.112 % | identical |
| qwen3-8-max | 2 | 87/93 (0 masked, 6 nested) | 43.8 | 1.26 % / 1.023 % / 141 | 2.231 % / 1.818 % | 2942 px (0.14 %), 0.00 %, max 21 |
| mask-luminance-radial-transform | 3 | 3/3 | 27.1 | 0.00 % / 0.000 % / 4 | 0.000 % / 0.000 % | identical |
| mask-nested-origin-reduction | 1 | 2/2 | 28.0 | 0.05 % / 0.000 % / 133 | 0.086 % / 0.000 % | identical |
| google-workspace-48px | 1 | 1/1 | 20.2 | 3.45 % / 3.095 % / 129 | 6.140 % / 5.502 % | identical |

## 32 MiB, fixed #323 tree (le-fix dc0f9a9)

| file | masks | admitted | peak MiB | vs Chromium frame px>20 / structural / max | vs Chromium box px>20 / structural | vs 256 MiB (px differ, px>20 %, max) |
|---|---|---|---|---|---|---|
| claude-fable-5-1 | 1 | 176/177 (1 masked, 0 nested) | 29.3 | 2.75 % / 1.132 % / 154 | 4.883 % / 2.012 % | 25494 px (1.23 %), 0.29 %, max 42 |
| fugu-ultra | 2 | 122/124 (2 masked, 0 nested) | 29.2 | 1.83 % / 1.077 % / 245 | 3.252 % / 1.915 % | 135909 px (6.55 %), 0.98 %, max 245 |
| glm-5-3 | 1 | 129/129 | 28.7 | 0.80 % / 0.501 % / 137 | 1.426 % / 0.890 % | 4445 px (0.21 %), 0.03 %, max 37 |
| gpt-5-2-pro | 2 | 46/53 (2 masked, 5 nested) | 29.3 | 5.97 % / 3.882 % / 148 | 10.619 % / 6.901 % | 84800 px (4.09 %), 0.06 %, max 85 |
| gpt-5-6-luna-pro | 1 | 33/33 | 28.7 | 0.29 % / 0.140 % / 93 | 0.511 % / 0.249 % | identical |
| gpt-5-6-sol-pro | 0 | 38/41 (0 masked, 3 nested) | 30.4 | 5.19 % / 3.660 % / 178 | 9.218 % / 6.507 % | 86784 px (4.19 %), 2.41 %, max 72 |
| gpt-5-6-sol | 1 | 48/48 | 28.7 | 0.84 % / 0.507 % / 90 | 1.492 % / 0.901 % | identical |
| gpt-6-astra | 1 | 162/162 | 28.7 | 1.17 % / 0.674 % / 186 | 2.086 % / 1.197 % | identical |
| grok-4-5 | 0 | 73/76 (0 masked, 3 nested) | 29.7 | 0.12 % / 0.000 % / 206 | 0.208 % / 0.000 % | 113994 px (5.50 %), 0.00 %, max 20 |
| nex-n2-pro | 2 | 99/102 (2 masked, 1 nested) | 29.1 | 5.49 % / 4.631 % / 105 | 9.761 % / 8.233 % | 42031 px (2.03 %), 0.63 %, max 40 |
| ox-alpha | 1 | 93/93 | 28.7 | 0.21 % / 0.019 % / 135 | 0.370 % / 0.034 % | identical |
| qwen3-8-2-4t-a95b | 1 | 198/198 | 29.1 | 1.86 % / 1.280 % / 96 | 3.312 % / 2.275 % | 80888 px (3.90 %), 0.12 %, max 63 |
| qwen3-8-27b | 1 | 99/100 (1 masked, 0 nested) | 29.3 | 0.99 % / 0.464 % / 202 | 1.759 % / 0.825 % | 57263 px (2.76 %), 0.62 %, max 179 |
| qwen3-8-flash | 2 | 115/117 (2 masked, 0 nested) | 29.2 | 3.53 % / 2.464 % / 160 | 6.282 % / 4.380 % | 170930 px (8.24 %), 1.09 %, max 49 |
| qwen3-8-max | 2 | 52/93 (2 masked, 0 nested) | 29.1 | 4.75 % / 3.821 % / 227 | 8.443 % / 6.793 % | 168977 px (8.15 %), 4.63 %, max 162 |
| mask-luminance-radial-transform | 3 | 3/3 | 27.1 | 0.00 % / 0.000 % / 4 | 0.000 % / 0.000 % | identical |
| mask-nested-origin-reduction | 1 | 2/2 | 28.0 | 0.05 % / 0.000 % / 133 | 0.086 % / 0.000 % | identical |
| google-workspace-48px | 1 | 1/1 | 20.2 | 3.45 % / 3.095 % / 129 | 6.140 % / 5.502 % | identical |

## Default 256 MiB, fixed #323 tree (the baseline the vs-256 column uses)

| file | masks | layers | peak MiB | vs Chromium frame px>20 / structural / max | vs Chromium box px>20 / structural |
|---|---|---|---|---|---|
| claude-fable-5-1 | 1 | 177 | 33.8 | 2.55 % / 0.995 % / 154 | 4.526 % / 1.769 % |
| fugu-ultra | 2 | 124 | 43.2 | 0.97 % / 0.592 % / 152 | 1.729 % / 1.052 % |
| glm-5-3 | 1 | 129 | 38.3 | 0.76 % / 0.494 % / 137 | 1.358 % / 0.879 % |
| gpt-5-2-pro | 2 | 53 | 55.2 | 5.92 % / 3.842 % / 148 | 10.524 % / 6.831 % |
| gpt-5-6-luna-pro | 1 | 33 | 28.7 | 0.29 % / 0.140 % / 93 | 0.511 % / 0.249 % |
| gpt-5-6-sol-pro | 0 | 41 | 41.7 | 2.75 % / 1.620 % / 178 | 4.883 % / 2.880 % |
| gpt-5-6-sol | 1 | 48 | 28.7 | 0.84 % / 0.507 % / 90 | 1.492 % / 0.901 % |
| gpt-6-astra | 1 | 162 | 28.7 | 1.17 % / 0.674 % / 186 | 2.086 % / 1.197 % |
| grok-4-5 | 0 | 76 | 39.3 | 0.11 % / 0.000 % / 206 | 0.200 % / 0.000 % |
| nex-n2-pro | 2 | 102 | 44.3 | 4.89 % / 4.150 % / 105 | 8.702 % / 7.378 % |
| ox-alpha | 1 | 93 | 28.7 | 0.21 % / 0.019 % / 135 | 0.370 % / 0.034 % |
| qwen3-8-2-4t-a95b | 1 | 198 | 44.0 | 1.64 % / 1.133 % / 90 | 2.914 % / 2.014 % |
| qwen3-8-27b | 1 | 100 | 34.3 | 0.85 % / 0.465 % / 89 | 1.514 % / 0.827 % |
| qwen3-8-flash | 2 | 117 | 43.2 | 1.91 % / 1.188 % / 160 | 3.390 % / 2.112 % |
| qwen3-8-max | 2 | 93 | 48.3 | 1.24 % / 1.023 % / 141 | 2.213 % / 1.818 % |
| mask-luminance-radial-transform | 3 | 3 | 27.1 | 0.00 % / 0.000 % / 4 | 0.000 % / 0.000 % |
| mask-nested-origin-reduction | 1 | 2 | 28.0 | 0.05 % / 0.000 % / 133 | 0.086 % / 0.000 % |
| google-workspace-48px | 1 | 1 | 20.2 | 3.45 % / 3.095 % / 129 | 6.140 % / 5.502 % |

## Same ladder on the corpus-all3 harness (pre-fix #323 code, whole stack) and the 2026-09-09 pre-#323 numbers

Run today with the already-built /private/tmp/wt-all3/target/debug/examples/_logos_full (branch corpus-all3 at f05e2da: #322 + the pre-review #323 + #324 clip + #338 turbulence + #339; its working tree carries an uncommitted stencil-clear change in the renderers and a test rename, nothing in the layer or pool code) under the same framing and references. That tree reserves mask coverage at `begin_layer` but acquires the filter target at `end_layer` and, past the budget, composites the unfiltered capture instead (wt-all3 src/lib.rs:1539-1545), so its pass-through count undercounts degraded layers; its vs-256 column shows the real effect. Its Chromium numbers are better than the fixed tree's for reasons unrelated to masks or the budget (clip paths clipped, feTurbulence run) - except the two reduction files, where the pre-fix mask code is what is wrong. The `pre-#323` columns are `busey-1080-pi-budget.json` (2026-09-09, #322 pooled build after its review round, boxstats % of box); it has no row for the two reduction files or the icon.

### 48 MiB

| file | pre-fix #323: admitted | peak MiB | box px>20 / structural | vs its 256 MiB | pre-#323 (09-09): admitted | peak MiB | box px>20 / structural |
|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 178/178 | 36.5 | 3.364 % / 0.973 % | identical | 178/178 | 36.5 | 3.364 % / 0.973 % |
| fugu-ultra | 124/124 | 43.2 | 0.368 % / 0.002 % | identical | 124/124 | 38.7 | 0.368 % / 0.002 % |
| glm-5-3 | 129/129 | 38.3 | 0.044 % / 0.000 % | identical | 129/129 | 38.3 | 0.044 % / 0.000 % |
| gpt-5-2-pro | 51/53 | 45.1 | 14.092 % / 10.018 % | 84366 px (4.07 %), 2.19 %, max 57 | 53/53 | 45.1 | 10.484 % / 6.794 % |
| gpt-5-6-luna-pro | 33/33 | 28.7 | 0.084 % / 0.000 % | identical | 33/33 | 28.7 | 0.084 % / 0.000 % |
| gpt-5-6-sol-pro | 41/41 | 41.7 | 4.448 % / 2.577 % | identical | 41/41 | 41.7 | 4.448 % / 2.577 % |
| gpt-5-6-sol | 48/48 | 28.7 | 0.112 % / 0.000 % | identical | 48/48 | 28.7 | 0.112 % / 0.000 % |
| gpt-6-astra | 162/162 | 28.7 | 0.178 % / 0.000 % | identical | 162/162 | 28.7 | 0.178 % / 0.000 % |
| grok-4-5 | 76/76 | 39.3 | 0.200 % / 0.000 % | identical | 76/76 | 39.3 | 0.200 % / 0.000 % |
| nex-n2-pro | 102/102 | 44.3 | 0.508 % / 0.048 % | identical | 102/102 | 39.3 | 0.508 % / 0.048 % |
| ox-alpha | 94/94 | 30.6 | 0.232 % / 0.001 % | identical | 94/94 | 30.6 | 0.232 % / 0.001 % |
| qwen3-8-2-4t-a95b | 200/200 | 47.3 | 0.278 % / 0.010 % | 45325 px (2.19 %), 0.01 %, max 23 | 200/200 | 47.3 | 0.278 % / 0.010 % |
| qwen3-8-27b | 100/100 | 34.3 | 0.044 % / 0.000 % | identical | 100/100 | 29.3 | 0.044 % / 0.000 % |
| qwen3-8-flash | 119/119 | 46.3 | 1.124 % / 0.360 % | identical | 119/119 | 41.8 | 1.124 % / 0.360 % |
| qwen3-8-max | 87/94 | 44.7 | 0.094 % / 0.000 % | 2942 px (0.14 %), 0.00 %, max 21 | 94/94 | 44.7 | 0.076 % / 0.000 % |
| mask-luminance-radial-transform | 3/3 | 27.1 | 19.312 % / 18.737 % | identical | - | - | - |
| mask-nested-origin-reduction | 2/2 | 28.0 | 16.400 % / 16.136 % | identical | - | - | - |
| google-workspace-48px | 1/1 | 20.2 | 6.140 % / 5.502 % | identical | - | - | - |

### 32 MiB

| file | pre-fix #323: admitted | peak MiB | box px>20 / structural | vs its 256 MiB | pre-#323 (09-09): admitted | peak MiB | box px>20 / structural |
|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 177/178 | 27.5 | 3.721 % / 1.216 % | 25499 px (1.23 %), 0.29 %, max 42 | 178/178 | 27.5 | 3.335 % / 0.974 % |
| fugu-ultra | 122/124 | 29.2 | 1.863 % / 0.858 % | 135924 px (6.55 %), 0.98 %, max 245 | 124/124 | 29.2 | 1.862 % / 0.856 % |
| glm-5-3 | 129/129 | 28.7 | 0.118 % / 0.012 % | 4528 px (0.22 %), 0.04 %, max 37 | 129/129 | 28.7 | 0.118 % / 0.012 % |
| gpt-5-2-pro | 46/53 | 29.3 | 10.584 % / 6.872 % | 84801 px (4.09 %), 0.06 %, max 85 | 48/53 | 29.3 | 10.508 % / 6.826 % |
| gpt-5-6-luna-pro | 33/33 | 28.7 | 0.084 % / 0.000 % | identical | 33/33 | 28.7 | 0.084 % / 0.000 % |
| gpt-5-6-sol-pro | 41/41 | 30.4 | 4.448 % / 2.577 % | 36986 px (1.78 %), 0.00 %, max 4 | 41/41 | 30.4 | 4.448 % / 2.577 % |
| gpt-5-6-sol | 48/48 | 28.7 | 0.112 % / 0.000 % | identical | 48/48 | 28.7 | 0.112 % / 0.000 % |
| gpt-6-astra | 162/162 | 28.7 | 0.178 % / 0.000 % | identical | 162/162 | 28.7 | 0.178 % / 0.000 % |
| grok-4-5 | 73/76 | 29.7 | 0.208 % / 0.000 % | 113994 px (5.50 %), 0.00 %, max 20 | 73/76 | 29.7 | 0.208 % / 0.000 % |
| nex-n2-pro | 100/102 | 29.1 | 1.564 % / 0.914 % | 37282 px (1.80 %), 0.61 %, max 40 | 98/102 | 29.1 | 1.136 % / 0.320 % |
| ox-alpha | 94/94 | 30.6 | 0.232 % / 0.001 % | identical | 94/94 | 30.6 | 0.232 % / 0.001 % |
| qwen3-8-2-4t-a95b | 199/200 | 31.3 | 5.455 % / 0.536 % | 249745 px (12.04 %), 2.67 %, max 59 | 200/200 | 31.3 | 0.523 % / 0.142 % |
| qwen3-8-27b | 100/100 | 29.3 | 0.044 % / 0.000 % | 9219 px (0.44 %), 0.00 %, max 7 | 100/100 | 29.3 | 0.044 % / 0.000 % |
| qwen3-8-flash | 117/119 | 31.3 | 4.469 % / 2.818 % | 206043 px (9.94 %), 1.51 %, max 66 | 119/119 | 31.3 | 4.478 % / 2.831 % |
| qwen3-8-max | 87/94 | 30.0 | 0.905 % / 0.051 % | 119693 px (5.77 %), 0.35 %, max 73 | 89/94 | 30.0 | 0.578 % / 0.051 % |
| mask-luminance-radial-transform | 3/3 | 27.1 | 19.312 % / 18.737 % | identical | - | - | - |
| mask-nested-origin-reduction | 2/2 | 28.0 | 16.400 % / 16.136 % | identical | - | - | - |
| google-workspace-48px | 1/1 | 20.2 | 6.140 % / 5.502 % | identical | - | - | - |

## Findings

1. **48 MiB admits every masked layer in every file.** No refused layer at 48 MiB carries a mask (`PASS ... mask=false` for all 13), and 16 of 18 files render bit-identically to the 256 MiB default. The two that do not, gpt-5-2-pro (46/53) and qwen3-8-max (87/93), refuse only layers nested at depth 2 inside an admitted layer - in gpt-5-2-pro five of the seven are 19x19 and 38x38 px blurred groups, each still costing a viewport-sized store because the harness scissors every layer to the 1080 px viewport (`VIEWPORT_CLIP=1`), and one 1088x1088 RGBA8 store is 4.5 MiB (`transient::LAYER_GRANULARITY` 64). The fixed tree holds the enclosing layer's mask coverage (two images for a luminance mask) and filter-chain images from `begin_layer` (dc0f9a9), so a nested layer sees less headroom than on the pre-fix tree, which acquired the filter target only at `end_layer`: pre-fix refuses 2/53 there, and the 2026-09-09 #322 build 0/53. The resulting picture is nearly the same on both #323 trees (fixed 86,222 px / pre-fix 84,366 px differ from their 256 MiB render); on qwen3-8-max the two trees produce the same 2,942 changed pixels.

2. **32 MiB is below what a viewport-sized masked layer plus its neighbours need.** Masked layers themselves pass through in 7 of the 15 files that reference a mask: claude-fable-5-1 (1), fugu-ultra (2), gpt-5-2-pro (2, plus 5 nested), nex-n2-pro (2, plus 1 nested), qwen3-8-27b (1), qwen3-8-flash (2), qwen3-8-max (2, plus 39 blurred or opacity-only siblings). Every file's peak sits at 28.7-30.4 MiB against the 33.5 MB cap: the pool never frees within a frame, so it fills with the size classes the frame has already used (plain 1088x1088 stores, blur-padded 1152-1216 px stores, FLIP_Y and non-FLIP_Y variants) and refuses any layer whose class is not free at that moment. qwen3-8-max refuses 41/93 on the fixed tree against 7/94 on the pre-fix tree, but the pre-fix render still changes over 119,693 px (5.77 %) with those 7 refusals: it admitted the other blurred layers and composited them unfiltered when the filter target failed at `end_layer` (wt-all3 src/lib.rs:1539-1545), which its counter does not report. The fixed tree's 41 is the honest count of layers that could not get their whole effect set; its render changes over 168,977 px (8.15 %) because a refused layer drops its opacity as well as its blur.

3. **Shadows are the uncounted degradation.** Three fixed-tree rows at 32 MiB change with no refused layer or only nested ones: qwen3-8-2-4t-a95b (0 refused, 80,888 px, max 63), glm-5-3 (0 refused, 4,445 px), grok-4-5 (3 nested refused, 113,994 px, max 20). The harness casts every feDropShadow group through the canvas shadow state, whose coverage and blur images come from the same pool and are skipped past the budget without a counter (src/lib.rs:2411-2414). With `NO_SHADOW=1` all three render bit-identically at 32 and 256 MiB (0 px differ), and grok-4-5 then refuses nothing, so on those files the budget's whole cost is dropped shadows plus the room the shadows' images took from the nested layers. `LAYER_STATS` cannot see this; a skipped-shadow counter on `Canvas` would.

4. **The two reductions match Chromium at every budget on the fixed tree** - mask-luminance-radial-transform 0.00 % / 0.000 % (max delta 4), mask-nested-origin-reduction 0.05 % / 0.000 % (max 133 on a one-pixel edge ribbon; 0 px after erosion) - and are wrong at every budget on the pre-fix tree (10.86 % / 10.539 % and 9.23 % / 9.076 %). That is the review fixes (0bd7e9f, 048ddf3), not the budget; neither file comes near the cap (27.1 and 28.0 MiB peak, 3 and 2 layers).

5. **google-workspace-48px** is 1 layer, 1 alpha mask, admitted at every budget with a 20.2 MiB peak, and 3.45 % / 3.095 % (box 6.14 % / 5.50 %) against Chromium on both trees at every budget - identical renders. The differing pixels are the diagonal band where the icon's two overlapping chevrons meet (columns 521-1398, rows 72-1007; 58,219 of 71,615 survive a 4 px erosion, so a filled region, femtovg 3/255 darker on average): femtovg draws a hard boundary along that diagonal where Chromium blends the overlap softly. Budget- and #323-independent; a separate item.

6. **Peak bytes across trees.** At 256 MiB the fixed and pre-fix trees hold the same peak on 13 of 18 files; the five that differ (claude-fable-5-1 33.8 vs 36.5, ox-alpha 28.7 vs 30.6, qwen3-8-2-4t-a95b 44.0 vs 57.3, qwen3-8-flash 43.2 vs 46.3, qwen3-8-max 48.3 vs 49.2) are the files where the gated harness begins 1-2 fewer layers (177 vs 178, 93 vs 94, 198 vs 200, 117 vs 119, 93 vs 94): their feTurbulence groups render as layers on the all3 build and are skipped on this one. Against the 2026-09-09 #322 numbers the masked files hold more at 256 MiB (gpt-5-2-pro 55.2 vs 50.7, fugu-ultra 43.2 vs 38.7, nex-n2-pro 44.3 vs 39.3): the mask coverage images #323 adds, two viewport-sized stores per luminance-masked layer.

7. **Recommendation for the 32-48 MiB guidance** (`set_transient_image_budget` docs, src/lib.rs:1177-1181): 48 MiB holds for masked content with the caveat that nested layers inside a masked, blurred or shadowed layer can be refused; 32 MiB refuses masked layers outright on half the mask-referencing corpus when layers are viewport-sized. What the docs already say - scissor each group to its bounds before `begin_layer` - is the lever; this ladder deliberately keeps the pre-#323 framing (viewport scissor) so the numbers compare.

## Artifacts

Scratchpad `ladder/`: `refs/` (18 Chromium references and their pages), `logs/` and `logs_all3/` (LAYER_STATS output per file and budget; `*_layerlog.txt` LAYER_LOG at 48 MiB; `*_passlog.txt` per-refused-layer PASS lines), `metrics_fixed.json` / `metrics_all3.json` (every compare.py and boxstats line), `metrics.py`, `mkdoc.py`, `run.sh`, `run_all3.sh`, `mkrefs.sh`, `gws_overlay.png`. Renders were deleted after measuring (disk). The harness copy was removed from /private/tmp/wt-le/examples after the run; le-fix is unchanged.
