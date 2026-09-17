# Quadrature blur split on the full stack

`blur-quadrature` eff79e5 (Split Gaussian blurs above the shader bound into quadrature passes) on add6332 on
origin/layer-effects 999edd5, measured through the full-stack harness (`_logos_full.rs` with `--cfg harness_clip
--cfg harness_turbulence`: #322 layers, #323 masks, #324 clip paths, #338 feTurbulence, master's #336/#339)
against Chromium 131. Before = the binary the sheets round used; after = the same eval tree with the blur branch
merged. Metric and framing are the playbook's (`harness/README.md`): 460x260, pivot zoom about (230,130), SVG in
a 200 px box at (130,30), `SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1`, `compare.py` percent of pixels above
20/255 / structural percent after a 2 px erosion.

## Setup

* Eval tree `/private/tmp/wt-all3`, branch `corpus-all3`: 7bbcb5e + bf5169e `eval: clip fill rule` (the one
  uncommitted `expand_fill` fill-rule line) + 12d31f9 `Merge branch 'blur-quadrature' into corpus-all3`. One
  conflict, doc-comment only (`filter_image`'s doc: #338's turbulence note against the branch's per-pass bound
  note), both paragraphs kept; every code hunk (`chain_blur_sigma`, `blur_passes`, the `filter_passes` split,
  the `begin_layer` pad, the shadow ping-pong) auto-merged.
* Before binary md5 `7596fc6e500e10e016916730008149ee` (saved as `_logos_full_prequad`); after binary md5
  `6ee1458fb7bc6e7a35af92c71d1fc3b0`, built with `RUSTFLAGS="--cfg harness_clip --cfg harness_turbulence"
  cargo build --example _logos_full --features wgpu` (only femtovg recompiled, 3.5 s; the dependency
  fingerprints already carried those flags). `LAYER_STATS=1` on both: `harness cfgs: clip=true turbulence=true`,
  0 filters skipped, 0 layers passed through (default 256 MiB budget) on every frame below. Both are debug
  builds (the disk rules forbid a release build), so the wall times are debug times and only the ratio matters.
* References: chrome-headless-shell 131 `--disable-gpu --force-device-scale-factor=1 --window-size=460,260`,
  pages from `make_ref.py`. The 27 1x references are the earlier session's; the 2x and 4x ones were rendered by
  `validate.py --make-refs` (48 new, three reused from the zoom-triple proof). The icon references at 1.6, 1.9,
  2.1 and 2.35 were rendered again and are bit-identical to the earlier set (max delta 0 at each zoom).

## (a) Google Workspace icon ladder (`google-workspace-48px.svg`, feGaussianBlur stdDeviation 2.38)

sigma in device px = 2.38 x zoom x 200/48; passes = ceil((sigma/8)^2) (one pass of the unsplit sigma before).

| zoom | sigma (device px) | passes after | before px>20 / structural | after px>20 / structural | max delta before -> after |
|---|---|---|---|---|---|
| 1.6 | 15.9 | 4 of 7.93 | 0.06 % / 0.000 % | 0.04 % / 0.000 % | 76 -> 76 |
| 1.9 | 18.8 | 6 of 7.69 | 0.60 % / 0.000 % | 0.08 % / 0.000 % | 59 -> 59 |
| 2.1 | 20.8 | 7 of 7.87 | 2.90 % / 1.538 % | 0.08 % / 0.000 % | 56 -> 56 |
| 2.35 | 23.3 | 9 of 7.77 | 4.43 % / 3.016 % | 0.06 % / 0.000 % | 56 -> 49 |

The 2.35x diff against Chromium before the split is a ribbon along the blurred edge (5,295 px above 20/255,
bbox x 181-411); after it is 0.06 % (max delta 49, single pixels). 1.6x, where sigma 15.9 already needs four
passes, moves from 0.06 % to 0.04 %; the 0.6-1.3x steps (sigma <= 8, one pass with the value untouched) are
planned exactly as before and were not re-run.

## (b) BuseyBench, zoom triple 1x / 2x / 4x, 27 files

| file | 1x before | 1x after | 2x before | 2x after | 4x before | 4x after |
|---|---|---|---|---|---|---|
| claude-fable-5-1 | 0.85 / 0.000 | = | 3.49 / 0.324 | = | 6.38 / 1.812 | 7.15 / 2.490 |
| claude-opus-5 | 0.29 / 0.000 | = | 0.46 / 0.000 | = | 0.64 / 0.000 | 0.63 / 0.000 |
| fugu-ultra | 0.67 / 0.000 | = | 1.81 / 0.035 | = | 1.26 / 0.003 | = |
| gemini-3-1-pro-preview-custom-tools | 1.28 / 0.000 | = | 2.02 / 0.089 | 2.00 / 0.093 | 5.34 / 1.281 | 3.51 / 0.670 |
| gemini-3-1-pro-preview | 2.15 / 0.003 | = | 4.04 / 0.041 | = | 2.91 / 0.225 | 2.77 / 0.183 |
| gemini-3-7-flash | 1.37 / 0.003 | = | 3.82 / 0.694 | = | 5.81 / 2.638 | 5.84 / 2.671 |
| gemini-3-8-flash | 1.21 / 0.119 | = | 2.40 / 0.048 | = | 2.37 / 0.000 | = |
| glm-5-3-flash | 0.45 / 0.000 | = | 0.66 / 0.000 | = | 0.85 / 0.000 | 0.84 / 0.000 |
| glm-5-3 | 0.08 / 0.000 | = | 0.17 / 0.000 | = | 0.11 / 0.000 | 0.10 / 0.000 |
| glm-5v-turbo | 1.16 / 0.000 | = | 2.55 / 0.008 | = | 1.57 / 0.191 | 1.04 / 0.000 |
| gpt-5-2-pro | 3.36 / 0.186 | = | 11.62 / 3.611 | = | 27.49 / 15.659 | = |
| gpt-5-6-luna-pro | 0.27 / 0.000 | = | 0.43 / 0.000 | = | 0.18 / 0.000 | = |
| gpt-5-6-sol-pro | 2.64 / 0.153 | = | 7.71 / 2.450 | = | 11.27 / 5.082 | 14.37 / 8.176 |
| gpt-5-6-sol | 0.11 / 0.000 | = | 0.29 / 0.000 | = | 0.48 / 0.000 | = |
| gpt-5-6-terra-pro | 2.58 / 0.193 | = | 6.23 / 2.375 | = | 8.01 / 4.586 | 8.52 / 5.191 |
| gpt-6-astra | 0.15 / 0.000 | = | 0.21 / 0.000 | = | 0.37 / 0.000 | = |
| grok-4-5 | 0.78 / 0.000 | = | 0.74 / 0.000 | = | 0.35 / 0.000 | 0.36 / 0.000 |
| kimi-k2-6 | 0.22 / 0.000 | = | 0.37 / 0.000 | = | 0.69 / 0.058 | = |
| kimi-k3 | 0.63 / 0.000 | = | 1.45 / 0.000 | = | 1.12 / 0.005 | 1.02 / 0.000 |
| muse-spark-1-3-contributor | 0.76 / 0.041 | = | 1.47 / 0.000 | = | 0.84 / 0.000 | = |
| muse-spark-1-3 | 0.30 / 0.000 | = | 0.64 / 0.000 | = | 0.77 / 0.000 | = |
| nex-n2-pro | 0.51 / 0.000 | = | 1.10 / 0.000 | = | 1.42 / 0.116 | 1.28 / 0.088 |
| ox-alpha | 0.09 / 0.000 | = | 0.20 / 0.000 | = | 0.36 / 0.000 | = |
| qwen3-8-2-4t-a95b | 0.62 / 0.000 | = | 1.01 / 0.000 | = | 0.92 / 0.000 | 0.89 / 0.000 |
| qwen3-8-27b | 0.16 / 0.000 | = | 0.23 / 0.000 | = | 0.20 / 0.000 | = |
| qwen3-8-flash | 0.19 / 0.000 | = | 0.42 / 0.000 | 0.41 / 0.000 | 1.43 / 0.227 | 0.56 / 0.000 |
| qwen3-8-max | 0.14 / 0.000 | = | 0.38 / 0.000 | = | 0.11 / 0.000 | = |
| **mean (27)** | **0.85 / 0.026** | **0.85 / 0.026** | **2.07 / 0.358** | **2.07 / 0.358** | **3.08 / 1.181** | **3.11 / 1.303** |
| mean, 22 files without the shadow/glow idiom (see c) | 0.56 / 0.007 | 0.56 / 0.007 | 1.05 / 0.010 | 1.05 / 0.010 | 1.10 / 0.096 | 0.94 / 0.046 |

`=` means the after frame scored identically (px>20, structural and max delta all equal). Per zoom:

* zoom 1.0: mean px>20 0.85 % -> 0.85 %, mean structural 0.026 % -> 0.026 %; 27 of 27 files identical; files above 0.05 % structural 4 -> 4: gemini-3-8-flash 0.119, gpt-5-2-pro 0.186, gpt-5-6-sol-pro 0.153, gpt-5-6-terra-pro 0.193
* zoom 2.0: mean px>20 2.07 % -> 2.07 %, mean structural 0.358 % -> 0.358 %; 25 of 27 files identical; files above 0.05 % structural 6 -> 6: claude-fable-5-1 0.324, gemini-3-1-pro-preview-custom-tools 0.093, gemini-3-7-flash 0.694, gpt-5-2-pro 3.611, gpt-5-6-sol-pro 2.450, gpt-5-6-terra-pro 2.375
* zoom 4.0: mean px>20 3.08 % -> 3.11 %, mean structural 1.181 % -> 1.303 %; 12 of 27 files identical; files above 0.05 % structural 11 -> 9: claude-fable-5-1 2.490, gemini-3-1-pro-preview-custom-tools 0.670, gemini-3-1-pro-preview 0.183, gemini-3-7-flash 2.671, gpt-5-2-pro 15.659, gpt-5-6-sol-pro 8.176, gpt-5-6-terra-pro 5.191, kimi-k2-6 0.058, nex-n2-pro 0.088

Files that move by more than 0.01 points (px>20 or structural) at any zoom - there are none at 1x, two at 2x
(within 0.02 points), and these at 4x:

| file | zoom | px>20 before -> after | structural before -> after | largest blur (device sigma at that zoom) |
|---|---|---|---|---|
| claude-fable-5-1 | 4.0 | 6.38 -> 7.15 (+0.77) | 1.812 -> 2.490 (+0.678) | 20 -> 15.6 (blur20) + shadow idiom 14 |
| claude-opus-5 | 4.0 | 0.64 -> 0.63 (-0.01) | 0.000 -> 0.000 (+0.000) | 28 -> 21.9 |
| gemini-3-1-pro-preview-custom-tools | 2.0 | 2.02 -> 2.00 (-0.02) | 0.089 -> 0.093 (+0.004) | 40 -> 31.2 (blur-xl), feDropShadow 20 -> 15.6 |
| gemini-3-1-pro-preview-custom-tools | 4.0 | 5.34 -> 3.51 (-1.83) | 1.281 -> 0.670 (-0.611) | 40 -> 31.2 (blur-xl), feDropShadow 20 -> 15.6 |
| gemini-3-1-pro-preview | 4.0 | 2.91 -> 2.77 (-0.14) | 0.225 -> 0.183 (-0.042) | 25 -> 19.5 (unused) / 15 -> 11.7, feDropShadow 15 |
| gemini-3-7-flash | 4.0 | 5.81 -> 5.84 (+0.03) | 2.638 -> 2.671 (+0.033) | 12 -> 9.4 (softGlow idiom) |
| glm-5-3-flash | 4.0 | 0.85 -> 0.84 (-0.01) | 0.000 -> 0.000 (+0.000) | feDropShadow 18 -> 14.1 |
| glm-5v-turbo | 4.0 | 1.57 -> 1.04 (-0.53) | 0.191 -> 0.000 (-0.191) | 20 -> 15.6, feDropShadow 15 -> 11.7 |
| gpt-5-6-sol-pro | 4.0 | 11.27 -> 14.37 (+3.10) | 5.082 -> 8.176 (+3.094) | 15 -> 11.7 (shadow idiom) |
| gpt-5-6-terra-pro | 4.0 | 8.01 -> 8.52 (+0.51) | 4.586 -> 5.191 (+0.605) | 15 -> 11.7 (shadow idiom) |
| grok-4-5 | 4.0 | 0.35 -> 0.36 (+0.01) | 0.000 -> 0.000 (+0.000) | feDropShadow 12 -> 9.4 |
| kimi-k3 | 4.0 | 1.12 -> 1.02 (-0.10) | 0.005 -> 0.000 (-0.005) | feDropShadow 18 -> 14.1 |
| nex-n2-pro | 4.0 | 1.42 -> 1.28 (-0.14) | 0.116 -> 0.088 (-0.028) | feDropShadow 16 -> 12.5, 14 -> 10.9 |
| qwen3-8-2-4t-a95b | 4.0 | 0.92 -> 0.89 (-0.03) | 0.000 -> 0.000 (+0.000) | 30 -> 23.4, feDropShadow 18 -> 14.1 |
| qwen3-8-flash | 2.0 | 0.42 -> 0.41 (-0.01) | 0.000 -> 0.000 (+0.000) | 34 -> 26.6, feDropShadow 26 -> 20.3 |
| qwen3-8-flash | 4.0 | 1.43 -> 0.56 (-0.87) | 0.227 -> 0.000 (-0.227) | 34 -> 26.6, feDropShadow 26 -> 20.3 |

At 4x the structural improvements sum to -1.104 points (gemini-3-1-pro-preview-custom-tools -0.611, qwen3-8-flash
-0.227, glm-5v-turbo -0.191, gemini-3-1-pro-preview -0.042, nex-n2-pro -0.028, kimi-k3 -0.005) and the regressions to
+4.410 (gpt-5-6-sol-pro +3.094, claude-fable-5-1 +0.678, gpt-5-6-terra-pro +0.605, gemini-3-7-flash +0.033), net
+3.306 / 27 = +0.122 on the mean. All four regressions are files whose residual is the
harness's mapping of a manual drop-shadow or glow filter, not the split; see (c). Over the 22 files without that
idiom the 4x mean goes 1.10 % / 0.096 % -> 0.94 % / 0.046 % structural, and the 2x and 1x means are unchanged to three decimals.

## (c) Attribution of the residual after the split

Two classes account for every file above 0.05 % structural except three small ones:

* **#332 (separable blend modes)**: the `feTurbulence -> ... -> feBlend mode="multiply"` skin chains
  (gpt-5-2-pro `#skinNoise`, gpt-5-6-sol-pro `#skinTexture`, nex-n2-pro `#skinTexture`) and gemini-3-7-flash's
  `mix-blend-mode: screen` group (`#lighting-fx`, opacity 0.45). The harness draws those groups' sources
  unfiltered / composited normally (README rule 3). Ablation on the **reference side only**: the `filter=` or
  `mix-blend-mode` stripped from the SVG, Chromium re-rendered, femtovg's sweep frame kept (re-rendering it on the
  stripped SVG changes 0 px in every case, so the femtovg side is unchanged by construction).
* **The manual drop-shadow / glow idiom** (a harness mapping, not a femtovg or a blur item): `feGaussianBlur
  in="SourceAlpha" -> feOffset -> feColorMatrix | feFlood+feComposite -> feMerge[shadow, SourceGraphic]`
  (gpt-5-6-sol-pro `#shadow` sd 15 on the face group and hair, gpt-5-6-terra-pro `#shadow` sd 15 on face and
  neck, claude-fable-5-1 `#dropShadow` sd 14 / `#hairShadow` sd 5, gpt-5-2-pro `#softShadow` sd 8 on ten groups
  including the whole face) and the glow variant `feGaussianBlur -> feComposite/feMerge under SourceGraphic`
  (gemini-3-7-flash `#softGlow` sd 12, gpt-5-2-pro `#rim` sd 3). `group_effects()` in `_logos_full.rs` turns
  every `feGaussianBlur` primitive of a group's filter into a blur of the group's layer, so these groups render
  blurred where the browser blurs only an offset shadow copy under a sharp source. A truer blur is then a truer
  error, which is why a larger sigma at 4x regresses them. Ablation on **both sides**: those `filter=` references
  stripped from the SVG, Chromium and femtovg both rendered on it.

px>20 % / structural % against Chromium 131; `both` = idiom stripped both sides and #332 stripped on the
reference side:

| file | zoom | after, full | #332 stripped (ref) | idiom stripped (both sides) | both | #332 share, idiom present | idiom share | #332 share, idiom out | remainder |
|---|---|---|---|---|---|---|---|---|---|
| gpt-5-2-pro | 1.0 | 3.36 / 0.186 | 3.29 / 0.153 | 0.23 / 0.000 | 0.23 / 0.000 | 0.033 | 0.186 | 0.000 | 0.000 |
| gpt-5-2-pro | 2.0 | 11.62 / 3.611 | 11.30 / 3.402 | 0.35 / 0.000 | 0.35 / 0.000 | 0.209 | 3.611 | 0.000 | 0.000 |
| gpt-5-2-pro | 4.0 | 27.49 / 15.659 | 26.54 / 15.083 | 0.14 / 0.000 | 0.14 / 0.000 | 0.576 | 15.659 | 0.000 | 0.000 |
| gpt-5-6-sol-pro | 1.0 | 2.64 / 0.153 | 2.96 / 0.293 | 0.56 / 0.000 | 0.54 / 0.000 | -0.140 (interaction) | 0.153 | 0.000 | 0.000 |
| gpt-5-6-sol-pro | 2.0 | 7.71 / 2.450 | 8.60 / 3.511 | 1.02 / 0.000 | 0.99 / 0.000 | -1.061 (interaction) | 2.450 | 0.000 | 0.000 |
| gpt-5-6-sol-pro | 4.0 | 14.37 / 8.176 | 15.41 / 10.685 | 0.53 / 0.000 | 0.47 / 0.000 | -2.509 (interaction) | 8.176 | 0.000 | 0.000 |
| gpt-5-6-terra-pro | 1.0 | 2.58 / 0.193 | n/a | 0.57 / 0.000 | n/a | 0 (none in file) | 0.193 | 0 (none in file) | 0.000 |
| gpt-5-6-terra-pro | 2.0 | 6.23 / 2.375 | n/a | 0.70 / 0.000 | n/a | 0 (none in file) | 2.375 | 0 (none in file) | 0.000 |
| gpt-5-6-terra-pro | 4.0 | 8.52 / 5.191 | n/a | 0.58 / 0.000 | n/a | 0 (none in file) | 5.191 | 0 (none in file) | 0.000 |
| claude-fable-5-1 | 2.0 | 3.49 / 0.324 | n/a | 0.09 / 0.000 | n/a | 0 (none in file) | 0.324 | 0 (none in file) | 0.000 |
| claude-fable-5-1 | 4.0 | 7.15 / 2.490 | n/a | 0.08 / 0.000 | n/a | 0 (none in file) | 2.490 | 0 (none in file) | 0.000 |
| gemini-3-7-flash | 2.0 | 3.82 / 0.694 | 3.65 / 0.597 | 1.81 / 0.041 | 1.50 / 0.000 | 0.097 | 0.653 | 0.041 | 0.000 |
| gemini-3-7-flash | 4.0 | 5.84 / 2.671 | 5.24 / 2.179 | 2.87 / 0.649 | 1.68 / 0.000 | 0.492 | 2.022 | 0.649 | 0.000 |
| nex-n2-pro | 4.0 | 1.28 / 0.088 | 1.28 / 0.086 | n/a | n/a | 0.002 | 0 (none in file) | n/a | 0.086 |

Reading the table:

* gpt-5-6-sol-pro, gpt-5-6-terra-pro and claude-fable-5-1: the shadow idiom is the whole residual at every zoom
  (structural 0.000 with it stripped; px>20 0.5-1.0 % on the two gpt files, 0.08-0.09 % on fable). Their #332
  share once the idiom is out is 0.000 structural (px>20 within 0.06 points: sol-pro 0.56/1.02/0.53 -> 0.54/0.99/0.47).
  Stripping sol-pro's multiply alone reads *worse* (0.153 -> 0.293 at 1x, 2.450 -> 3.511 at 2x, 8.176 -> 10.685
  at 4x) because the idiom error dominates the same pixels; that is an interaction, not a #332 cost.
* gpt-5-2-pro (3.6 % / 15.7 % structural at 2x / 4x): #332's multiply is 0.033 / 0.209 / 0.576 points at 1x / 2x /
  4x with the idiom present and 0.000 with it out; the `#softShadow` idiom on ten groups is the rest, 0.153 /
  3.402 / 15.083. Remainder 0.000 (px>20 0.23 / 0.35 / 0.14 %).
* gemini-3-7-flash: the `#softGlow` idiom is 0.653 of 0.694 at 2x and 2.022 of 2.671 at 4x; the `screen` blend
  (#332) is the remaining 0.041 / 0.649 once the glow is out (0.097 / 0.492 measured with it present). Remainder
  0.000.
* nex-n2-pro 4x: #332 is 0.002 of 0.088; the 0.086 that remains is neither class (no idiom in the file; it has
  feDropShadow sd 16 and 14 groups, sigma 12.5 / 10.9 at 4x, run through the shadow split - the split took the
  file from 0.116 to 0.088).

Files above 0.05 % structural after the split that have neither class (no feBlend, no mix-blend-mode, no
idiom): gemini-3-1-pro-preview-custom-tools (2x 0.093, 4x 0.670, from 1.281), gemini-3-1-pro-preview (4x 0.183,
from 0.225), kimi-k2-6 (4x 0.058, unchanged; its sd-20 blurs sit on ellipses at opacity 0.08-0.10), and
gemini-3-8-flash (1x 0.119, unchanged; its largest blur is sd 6). Their #332 share is 0 by construction. A
`LAYER_BBOX_SCISSOR=1` probe (usvg's layer bbox includes the SVG filter region, which the harness's
viewport-sized layers do not clip to; the README notes it also cuts the group shadow's reach):

| file | zoom | after, viewport-sized layers | after, LAYER_BBOX_SCISSOR=1 |
|---|---|---|---|
| gemini-3-1-pro-preview-custom-tools | 2.0 | 2.00 / 0.093 | 1.78 / 0.075 |
| gemini-3-1-pro-preview-custom-tools | 4.0 | 3.51 / 0.670 | 2.05 / 0.195 |
| gemini-3-1-pro-preview | 4.0 | 2.77 / 0.183 | 2.59 / 0.183 |
| kimi-k2-6 | 4.0 | 0.69 / 0.058 | 0.67 / 0.058 |
| gemini-3-8-flash | 1.0 | 1.21 / 0.119 | 1.17 / 0.033 |
| nex-n2-pro | 4.0 | 1.28 / 0.088 | 1.32 / 0.088 |

So 0.475 of custom-tools' 0.670 at 4x and 0.086 of gemini-3-8-flash's 0.119 at 1x behave like filter-region
clipping (`#blur-lg` and `#blur-md` there are `x=-20% width=140%` regions around small ellipses under sigma
15.6 / 6.2 blurs, which Chromium truncates at the region edge); gemini-3-1-pro-preview, kimi-k2-6 and nex-n2-pro
do not move under the probe and stay unattributed at 0.183 / 0.058 / 0.086.

#332 overall: with the idiom groups out of the way its class costs 0.000 structural on gpt-5-2-pro and
gpt-5-6-sol-pro at every zoom, 0.002 on nex-n2-pro at 4x, and 0.041 / 0.649 on gemini-3-7-flash at 2x / 4x (the
`screen` group). Everything else above 0.05 % is the harness idiom (five files) or the three unattributed
residuals above.

## (d) Cost: transient bytes held at flush and wall per frame

`LAYER_STATS=1`, bytes held at the flush of the last frame; wall per frame = (FRAMES=11 - FRAMES=1) / 10, each
the minimum of two runs, GPU otherwise idle, debug builds (absolute times are debug times; the ratio is the
result). The eight files with the largest blurs by max stdDeviation (custom-tools 40, qwen3-8-flash 34, qwen3-8-max
30, qwen3-8-2-4t-a95b 30, claude-opus-5 28, gemini-3-1-pro-preview 25, qwen3-8-27b 24, claude-fable-5-1 20 - the
tie at 20 with glm-5v-turbo and kimi-k2-6 broken by the 4x pass count, 11 vs 10 vs 7), at 2x and 4x, plus the
icon at 2.35x. No layer passed through on any run.

| file | zoom | layers | bytes held before -> after | wall/frame before -> after (ms) |
|---|---|---|---|---|
| gemini-3-1-pro-preview-custom-tools | 2.0 | 825 | 8,135,168 -> 8,921,600 (+0.79 MB) | 94.0 -> 95.9 (+2 %) |
| gemini-3-1-pro-preview-custom-tools | 4.0 | 825 | 6,984,192 -> 14,017,024 (+7.03 MB) | 88.3 -> 112.6 (+28 %) |
| qwen3-8-flash | 2.0 | 1309 | 9,145,360 -> 8,080,400 (-1.06 MB) | 118.7 -> 119.5 (+1 %) |
| qwen3-8-flash | 4.0 | 1309 | 8,614,032 -> 13,524,624 (+4.91 MB) | 114.4 -> 142.5 (+25 %) |
| qwen3-8-max | 2.0 | 1034 | 4,495,168 -> 4,495,168 (+0.00 MB) | 83.0 -> 83.0 (+0 %) |
| qwen3-8-max | 4.0 | 1034 | 5,156,416 -> 9,143,360 (+3.99 MB) | 82.3 -> 86.1 (+5 %) |
| qwen3-8-2-4t-a95b | 2.0 | 2200 | 9,983,040 -> 12,932,160 (+2.95 MB) | 208.2 -> 204.7 (-2 %) |
| qwen3-8-2-4t-a95b | 4.0 | 2200 | 10,554,272 -> 20,568,480 (+10.01 MB) | 206.1 -> 223.6 (+8 %) |
| claude-opus-5 | 2.0 | 1012 | 7,414,208 -> 8,593,856 (+1.18 MB) | 96.2 -> 97.7 (+2 %) |
| claude-opus-5 | 4.0 | 1012 | 6,769,024 -> 15,081,344 (+8.31 MB) | 93.0 -> 113.3 (+22 %) |
| gemini-3-1-pro-preview | 2.0 | 1078 | 6,058,496 -> 6,058,496 (+0.00 MB) | 131.2 -> 126.8 (-3 %) |
| gemini-3-1-pro-preview | 4.0 | 1078 | 6,984,192 -> 8,054,784 (+1.07 MB) | 130.7 -> 137.3 (+5 %) |
| qwen3-8-27b | 2.0 | 1100 | 4,833,280 -> 6,012,928 (+1.18 MB) | 89.4 -> 89.6 (+0 %) |
| qwen3-8-27b | 4.0 | 1100 | 3,276,800 -> 11,862,016 (+8.59 MB) | 85.2 -> 95.2 (+12 %) |
| claude-fable-5-1 | 2.0 | 1958 | 6,964,416 -> 6,964,416 (+0.00 MB) | 135.7 -> 133.5 (-2 %) |
| claude-fable-5-1 | 4.0 | 1958 | 5,966,208 -> 6,850,944 (+0.88 MB) | 131.0 -> 148.1 (+13 %) |
| google-workspace-48px | 2.35 | 11 | 2,621,440 -> 5,734,400 (+3.11 MB) | 3.9 -> 8.7 (+122 %) |

At 2x (device sigmas up to 15.6, at most four passes, on four of the eight files) the wall per frame is within
-3 % to +2 % - noise - and the bytes held move by -1.06 to +2.95 MB (a larger pad can merge two 64 px size
classes into one, which is how qwen3-8-flash holds *less*). At 4x the bytes held grow 0.9-10.0 MB (qwen3-8-27b
3.3 -> 11.9 MB, qwen3-8-2-4t-a95b 10.6 -> 20.6 MB) and the wall per frame +5 % to +28 % (custom-tools 88 -> 113
ms, qwen3-8-flash 114 -> 143, claude-opus-5 93 -> 113). The icon at 2.35x, one layer whose blur goes from one pass
to nine on a store that grows from 512x320 to 640x448, goes 3.9 -> 8.7 ms per frame.

**Pad growth.** A layer store pads its scissor rect by `ceil(3 sigma) + 2` per side and rounds to 64 px; before,
sigma was clamped to 8 in the pad (26 px per side).

* Icon at 2.35x, sigma 23.3: pad 26 -> 72 px per side; the scissor is the whole 460x260 frame, so the store goes
  512x320 (655,360 B) -> 640x448 (1,146,880 B), +491,520 B per image; the layer holds the store, one alpha-mask
  coverage image, the chain result and one -> two scratches (2 -> 10 passes with parity, scratch count
  min(2, passes-1)): 4 x 655,360 = 2,621,440 B -> 5 x 1,146,880 = 5,734,400 B, +3,112,960 B. Those are exactly
  the measured `transient bytes held at flush` (2,621,440 -> 5,734,400).
* The biggest blur in the corpus, gemini-3-1-pro-preview-custom-tools `#blur-xl` stdDeviation 40 at 4x = sigma
  31.25, 16 passes of 7.81: pad 26 -> 96 px per side, store 512x320 -> 704x512, 655,360 -> 1,441,792 B per
  image (+786,432 B), and the layer's three images (store, result, one scratch) become four: 1,966,080 ->
  5,767,168 B, +3,801,088 B for that layer. The file's pool at the flush grows 6,984,192 -> 14,017,024 B
  (+7,032,832), the rest being the `#blur-lg` class (sigma 15.6, pad 26 -> 49, 512x320 -> 576x384, three ->
  four images: +1,572,864 B) and the sigma-15.6 drop-shadow images (8 px granularity, pad 26 -> 49 per side).

## Evidence

`blur-quadrature-evidence.png` (repo root): top row the icon at 2.35x, full 460x260 frames, before / after /
Chromium 131; bottom row qwen3-8-flash at 4x (stdDeviation 34 = sigma 26.6, 12 passes), crop (60,20)-(400,130)
at 2x, before 1.43 % / 0.227 % -> after 0.56 % / 0.000 %. Metrics: `busey-blur-quadrature-metrics.json`
(before and after, all 27 files x 3 zooms) and `busey-blur-quadrature-cost.json`.

## Follow-ups (harness, not femtovg)

* Map the shadow idiom (`feGaussianBlur in="SourceAlpha"` -> `feOffset` -> recolour -> `feMerge` under
  `SourceGraphic`) onto README rule 4 (shadow state around the layer, offset and colour from the chain) instead of
  a group blur, and the glow idiom onto a blurred copy composited under the source. Five files, 1.242 of the
  1.303 points of the 4x mean: with those groups unshadowed on both sides the after build's corpus means read
  0.59 % / 0.006 %, 1.00 % / 0.010 %, 0.92 % / 0.061 % at 1x / 2x / 4x (substituted, not a harness result).
* The filter-region clip (`x/y/width/height` on `<filter>`): custom-tools 4x 0.670 -> 0.195 and gemini-3-8-flash
  1x 0.119 -> 0.033 under the bbox probe.
