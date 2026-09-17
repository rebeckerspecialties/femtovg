# Regression pass 2026-09-17: master 0d09c8f and the open stack against Chromium 131

Every corpus file rendered with the two evaluation binaries of the playbook harness (`examples/_logos_full.rs`, rules 1-5 incl. the
invalid-filter-reference pre-pass, `SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1`):

* **master** = upstream femtovg master 0d09c8f alone (#340 quadrature blur, #323 layer masks, #339 hairline alpha, #336 winding, #322 layers, #321 chains merged; no #324 clip paths - clip groups draw unclipped; no #338 feTurbulence - chains classified by input and skipped per rule 1). md5 `bdcf0adf6338efe9be61fff22b5abfdf`. `LAYER_STATS=1` prints `harness cfgs: clip=false turbulence=false`.
* **stack** = master + #338 (fe-turbulence at f1306d4) + #324 (path-clip). md5 `be52586cc97b96ceb4207e453477bef4`, `clip=true turbulence=true`.
* **338** = master + #338 only (md5 `d89a917589f739d889a76ce0ef181b13`), run over BuseyBench and the icons to split each master residual into its #338 share (master -> 338) and its #324 share (338 -> stack).

References: chrome-headless-shell 131 `--headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --default-background-color=FFFFFFFF` on `make_ref.py` pages; Firefox Developer Edition headless at 1x on the same pages for the browser envelope (Chromium vs Firefox). Metric: `compare.py` - percent of pixels with max channel delta > 20/255, and *structural* = the same after a 2-px binary erosion. Framing: 460x260, pivot zoom about (230,130), SVG in a 200-px box at (130,30); zooms 1 / 2 / 4 (the 2x and 4x frames are crops of the same artwork, the device-pixel-ratio case). Flag rule: structural > 0.05 % at any zoom, or structural above the Chromium-vs-Firefox structural envelope. Every flagged file is attributed below; every UNCAPTURED candidate by ablation (element stripped on both sides, or a harness `NO_*` switch), never by guess. Driver: `sweep.py` (this pass), numbers in `regression-2026-09-17-metrics.json`.

## Summary

| corpus | files | zooms | mean px>20 / structural, master | mean, stack | Chromium vs Firefox (1x) | flagged (stack) | flagged (master only) |
|---|---|---|---|---|---|---|---|
| icons (`wt-da/*.svg`) | 10 | 1/2/4 | 1x 3.01 / 2.346; 2x 7.14 / 6.241; 4x 9.41 / 8.709 | 1x 0.93 / 0.501; 2x 1.61 / 1.033; 4x 0.52 / 0.112 | mean 0.15 / 0.011 | kit | clipdemo |
| Ghostscript Tiger | 1 | 1/2/4 | 1x 2.75 / 0.003; 2x 3.91 / 0.000; 4x 2.99 / 0.000 | identical to master (0 px) | 0.02 / 0.000 | none (1x 0.003 = 4 px at (215,122)-(228,156), under threshold) | none |
| BuseyBench | 27 | 1/2/4 | 1x 1.94 / 0.632; 2x 5.36 / 2.582; 4x 7.93 / 5.078 | 1x 0.85 / 0.026; 2x 2.07 / 0.358; 4x 3.11 / 1.303 | mean 0.19 / 0.000 | 10: claude-fable-5-1, gemini-3-1-pro-preview, gemini-3-1-pro-preview-custom-tools, gemini-3-7-flash, gemini-3-8-flash, gpt-5-2-pro, gpt-5-6-sol-pro, gpt-5-6-terra-pro, kimi-k2-6, nex-n2-pro | 15 |
| corpus/{banner,ember,svsdeid,mask-*} | 5 | 1 | 1.40 / 0.859 | 1.40 / 0.859 | mean 0.05 / 0.000 | banner | none |
| WPT css-masking (box-relative) | 22 | 1/2 | 1x 38.64 / 33.373; 2x 38.57 / 35.872 | 1x 22.57 / 19.363; 2x 22.47 / 20.830 | mean 0.19 / 0.000 | 10 | 9 |
| SVGenius (625x625, box 625 at 0,0) | 104 | 1 | 1.69 / 1.128 (97 square-viewBox files: 0.31 / 0.000) | identical to master (0 px on 104/104) | mean 0.11 / 0.000 | 7 (all `make_ref.py` framing) | none |

Master and stack render bit-identically wherever a file uses neither clip paths nor feTurbulence (`master_vs_stack` exact = 0 at every zoom: 7 of 10 icons, the Tiger, 3 of 27 BuseyBench files (gemini-3-7-flash, gemini-3-8-flash, grok-4-5), 3 of 5 misc files, 104 of 104 SVGenius files, 12 of 23 WPT cases). Nothing the stack adds regresses any file at any zoom: stack structural <= master structural on every frame except gpt-5-2-pro (1x +0.001, 4x +0.006 pt, inside the idiom-chain noise).

## Findings not in the open inventory

### UNCAPTURED: content beyond the canvas' top/left edge casts no layer shadow into the frame

Four BuseyBench files keep a structural band along the top rows of the 4x frame on both binaries (gemini-3-1-pro-preview 0.183, gemini-3-1-pro-preview-custom-tools 0.195 of 0.670, nex-n2-pro 0.088, kimi-k2-6 0.058; custom-tools 0.075 of 0.093 at 2x). In each, femtovg's top rows are lighter than Chromium's by 10-13/255, decaying over 8-14 rows (nex-n2-pro rows 0-5 +11 to +13 R; kimi-k2-6 rows 0-14 +10 to +13). Attribution by ablation:

* Stripping one filter reference on **both sides** removes the band entirely: nex-n2-pro `#hairShadow` (feDropShadow dx 0 dy 16 sd 14 on `hair-back`/`hair-front`) 105 -> 0 band px, 0.088 -> 0.000; kimi-k2-6 `#shadow-soft` (dy 8 sd 10 on `hair-back`/`eyebrows`/`hair-front`) 69 -> 0, 0.058 -> 0.000; gemini-3-1-pro-preview `#drop-shadow` 219 -> 0, 0.183 -> 0.003. Every other filter in those files changes the band by at most 5 px. `NO_MASK`, `NO_TURBULENCE`, `NO_OPACITY`, `LAYER_BBOX_SCISSOR` leave it; `NO_SHADOW` makes the whole frame worse (the shadow mapping is right where the source is on-canvas).
* Frame-extension probe (`FRAME_H=360 BOX_Y=80`: same pivot geometry, 50 more rows of content above): the band vanishes from the rows that now have content above them (nex-n2-pro 105 -> 0 px, kimi-k2-6 69 -> 0, custom-tools 237 -> 0, gemini-3-1-pro-preview 219 -> 84) and reappears at the new top edge (462 / 23 / 852 / 205 px).
* Reduction `corpus/shadow-offcanvas-reduction.svg` (300x300 frame, box 600 at (-150,-150), so the canvas top is SVG y = 50): a rect ending 6 px above the canvas top under `feDropShadow dy=6 sd=5` casts **0 of Chromium's 4,772 shadow pixels** into the frame (5.64 % / 4.709 % structural, max delta 108) on master and stack alike; `dy=0` likewise 0 of 1,278. The same rect placed 6 px beyond the **left** edge with `dx=6`: 0 of 4,774. Mirrored beyond the **bottom** edge (`dy=-6`) or the **right** edge (`dx=-6`) the shadow is there at 86 % (4,102 of 4,772 / 4,774; 2.53 % / 1.69 %). A rect crossing the top edge casts the shadow of its visible part only (11,572 of 12,220). The same rect above the top edge under a plain `feGaussianBlur sd=5` is exact (max delta 4; 1,070 vs 962 ink px) - so the layer's blur pass sees the padded off-canvas content and the shadow pass does not, and the loss is asymmetric (origin-side edges lose everything, far-side edges 14 %).
* Not a harness mapping: the harness only sets `shadow_color/offset/blur` before `begin_layer` and scissors to the SVG viewport (`canvas.scissor(0,0,box,box)` under the pivot transform, which femtovg intersects with the canvas); the store bounds, pad and shadow pass are femtovg's. Master (no #324/#338) reproduces it identically, so it is neither pending PR.
* Visible only when artwork extends beyond the canvas (the DPR / pivot-zoom / panning case): at 1x every corpus file sits inside the frame and the band cannot occur, which is why the 1x sweeps never showed it. Evidence: `regression-2026-09-17-shadow-edge.png`.

Proposed home: **new issue** - "Layer shadow (begin_layer + shadow state) ignores layer content beyond the canvas' origin edges" - with the reduction, the four corpus files at 4x and the asymmetry table above. It would have landed in #322's review had the zoom sweep existed then; #325 (kernel shape) does not cover it (the kernel is right where the source is on-canvas).

### Everything else above threshold is inventory or harness

* **#324 pending (clip paths)** explains every master-only flag: clipdemo (10.9 / 31.2 / 49.5 -> 0.000), the 15 BuseyBench files flagged on master but not on the stack (13 of them entirely - their 338-build numbers equal master's to 0.03 pt and their stack numbers are 0.000; claude-opus-5 and qwen3-8-max jointly with #338), the master->stack delta of six stack-flagged files (claude-fable-5-1, gemini-3-1-pro-preview, gemini-3-1-pro-preview-custom-tools, gpt-5-6-sol-pro, kimi-k2-6, nex-n2-pro), kit's master->stack delta, and 9 WPT cases (mask-nested-clip-path-002/-003/-010/-panning-001/-002 and the four `*-content-clip*` files go from 55.2 / 59.6 box-structural (10.4 for -010; 3.2 / 4.2 for the clip files) to 0.000 on the stack).
* **#338 pending (feTurbulence)** explains claude-opus-5 (2.617 / 11.354 / 23.239 of 4.487 / 18.742 / 42.260 at 1x/2x/4x; the rest #324) and qwen3-8-max (0.248 / 1.449 / 1.804 of 0.307 / 1.865 / 3.754). No other file moves by more than 0.03 pt between master and the 338 build.
* **#332 (blend modes)**: banner (4.293 -> 0.112 with the color-burn group stripped on both sides), gemini-3-7-flash's `screen` group (0.041 / 0.649 at 2x/4x), gpt-5-2-pro's multiply (0.033 / 0.209 / 0.576), nex-n2-pro 0.002.
* **#327 (thin fills)**: banner's remaining 0.112 (outlined wordmark/tagline: light-pixel ink 5.41x -> 1.83x -> 1.09x of Chromium's as the box grows 200 -> 400 -> 800, structural 1.68 % -> 0.41 % -> 0.000 % of the banner); the AA-only px>20 on fox-with-box-on-cloud (1.03-1.47 %, 0.000 structural), duckduckgo, mr-settodefault, splash-logo, the Tiger (2.75-3.91 %, <= 0.003 structural) and BuseyBench's 0.6-2 % floors.
* **Harness mapping**: the manual drop-shadow / glow idiom (claude-fable-5-1, gemini-3-7-flash, gpt-5-2-pro, gpt-5-6-sol-pro, gpt-5-6-terra-pro; `group_effects()` blurs the whole group; blur-quadrature-evidence.md (c) has the both-sides ablations); SVG filter-region clipping (gemini-3-8-flash 1x 0.119 -> 0.033 and custom-tools 0.670 -> 0.195 under `LAYER_BBOX_SCISSOR=1`; muse-spark-1-3-contributor 0.041 -> 0.013); usvg ignoring `<style>` animation state (kit); nested clipPath translations that live only in `corpus/wpt/_wpt_masks.rs` (9 WPT cases); fonts (mask-text-001, within the 0.27 % envelope); and `make_ref.py`'s framing of a non-square viewBox with a square width/height (7 SVGenius files: usvg letterboxes xMidYMid inside the 200x200 size, the page fits the viewBox xMinYMin; width/height stripped on both sides -> 0.000 on all seven).
* **#325, #335, #337**: no file's residual attributes to them in this pass (#337's primitives appear only inside the idiom chains above, where the harness's whole-group blur is the larger error; #335 is an API-sequence issue the harness does not exercise).

## Icons (460x260, box 200 at (130,30); px>20 % / structural %)

| file | zoom | master | stack | Chromium vs Firefox (1x) | attribution |
|---|---|---|---|---|---|
| background-noodles-left-dark | 1 | 0.01 / 0.000 | 0.01 / 0.000 | 0.00 / 0.000 | match |
| background-noodles-left-dark | 2 | 0.07 / 0.000 | 0.07 / 0.000 |  | same |
| background-noodles-left-dark | 4 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| clipdemo | 1 | 13.15 / 10.935 | 0.54 / 0.000 | 0.15 / 0.000 | #324 pending (clip): master draws the two clip groups unclipped (LAYER_STATS `clip paths drawn unclipped: 2`); stack 0.000 at every zoom |
| clipdemo | 2 | 34.43 / 31.210 | 0.68 / 0.000 |  | as 1x |
| clipdemo | 4 | 51.88 / 49.492 | 0.43 / 0.000 |  | as 1x |
| duckduckgo-com_2x | 1 | 0.75 / 0.000 | 0.75 / 0.000 | 0.02 / 0.000 | AA only (#327 class, 0.000 structural) |
| duckduckgo-com_2x | 2 | 0.46 / 0.000 | 0.46 / 0.000 |  | same |
| duckduckgo-com_2x | 4 | 0.25 / 0.000 | 0.25 / 0.000 |  | same |
| fox-with-box-on-cloud | 1 | 1.03 / 0.000 | 1.03 / 0.000 | 0.02 / 0.000 | AA only (#327 class, 0.000 structural) |
| fox-with-box-on-cloud | 2 | 1.47 / 0.000 | 1.47 / 0.000 |  | same |
| fox-with-box-on-cloud | 4 | 0.96 / 0.000 | 0.96 / 0.000 |  | same |
| google-workspace-48px | 1 | 0.07 / 0.000 | 0.07 / 0.000 | 0.06 / 0.000 | match |
| google-workspace-48px | 2 | 0.08 / 0.000 | 0.08 / 0.000 |  | same |
| google-workspace-48px | 4 | 0.03 / 0.000 | 0.03 / 0.000 |  | same |
| kit-flame-reduction | 1 | 0.01 / 0.000 | 0.01 / 0.000 | 0.00 / 0.000 | match |
| kit-flame-reduction | 2 | 0.03 / 0.000 | 0.03 / 0.000 |  | same |
| kit-flame-reduction | 4 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| kit | 1 | 13.96 / 12.527 | 5.79 / 5.011 | 0.95 / 0.114 | harness mapping (usvg ignores `<style>`: CSS `@keyframes`/`offset-path`/`transform` animation state on 19 groups). Ablation, animation state stripped on both sides: stack vs Chromium 0.01 %/0.000 % at 1x (80 px), 0 px at 2x and 4x; femtovg unchanged (0 px at every zoom), Chromium changed by exactly the sweep diff (7,123 / 13,957 / 2,088 px); master->stack delta is #324 pending (1 clip group, `unclipped: 1`) |
| kit | 2 | 33.04 / 31.197 | 11.46 / 10.325 |  | as 1x |
| kit | 4 | 39.15 / 37.602 | 1.71 / 1.120 |  | as 1x |
| mr-settodefault | 1 | 0.76 / 0.000 | 0.76 / 0.000 | 0.03 / 0.000 | AA only (#327 class, 0.000 structural) |
| mr-settodefault | 2 | 1.32 / 0.000 | 1.32 / 0.000 |  | same |
| mr-settodefault | 4 | 1.06 / 0.000 | 1.05 / 0.000 |  | same |
| splash-logo | 1 | 0.30 / 0.000 | 0.30 / 0.000 | 0.24 / 0.000 | match |
| splash-logo | 2 | 0.51 / 0.000 | 0.51 / 0.000 |  | same |
| splash-logo | 4 | 0.74 / 0.000 | 0.74 / 0.000 |  | same |
| thin-fill-crescent | 1 | 0.04 / 0.000 | 0.04 / 0.000 | 0.00 / 0.000 | match |
| thin-fill-crescent | 2 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| thin-fill-crescent | 4 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| **mean (10)** | | 1x 3.01 / 2.346; 2x 7.14 / 6.241; 4x 9.41 / 8.709 | 1x 0.93 / 0.501; 2x 1.61 / 1.033; 4x 0.52 / 0.112 | | |

## Ghostscript Tiger

| zoom | master = stack | Chromium vs Firefox | note |
|---|---|---|---|
| 1 | 2.75 / 0.003 | 0.02 / 0.000 | 4 structural px at (215,122)-(228,156), thin-stroke/fill AA (#327 class); px>20 is AA ribbons on the stroke work |
| 2 | 3.91 / 0.000 |  | AA only |
| 4 | 2.99 / 0.000 |  | AA only |

## BuseyBench (27 files; px>20 % / structural %)

| file | 1x master | 1x 338 | 1x stack | 2x master | 2x 338 | 2x stack | 4x master | 4x 338 | 4x stack | Chr vs FF (1x) | attribution (stack residual; master->stack delta) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **claude-fable-5-1** | 1.27 / 0.028 | 1.27 / 0.028 | 0.85 / 0.000 | 4.96 / 0.850 | 4.90 / 0.849 | 3.49 / 0.324 | 8.68 / 3.484 | 8.64 / 3.457 | 7.15 / 2.490 | 0.02 / 0.000 | harness mapping: manual drop-shadow idiom (`#dropShadow` sd 14, `#hairShadow` sd 5 -> whole-group blur); blur-quadrature-evidence.md (c): idiom stripped both sides -> 0.000 at 2x/4x; master->stack delta #324 pending (7 unclipped); #338 share 0 (338 build = master to 0.03 pt) |
| **claude-opus-5** | 7.20 / 4.487 | 4.16 / 1.870 | 0.29 / 0.000 | 24.91 / 18.742 | 12.64 / 7.388 | 0.46 / 0.000 | 49.99 / 42.260 | 25.53 / 19.021 | 0.63 / 0.000 | 0.03 / 0.000 | stack 0.000; #338 pending 2.617 / 11.354 / 23.239 (master->338) + #324 pending 1.870 / 7.388 / 19.021 (338->stack) |
| **fugu-ultra** | 1.08 / 0.027 | 1.08 / 0.027 | 0.67 / 0.000 | 3.53 / 0.845 | 3.53 / 0.845 | 1.81 / 0.035 | 4.63 / 2.258 | 4.63 / 2.258 | 1.26 / 0.003 | 0.46 / 0.000 | stack <= 0.035 (under threshold); #324 pending (338 build = master) |
| **gemini-3-1-pro-preview-custom-tools** | 4.14 / 1.950 | 4.14 / 1.950 | 1.28 / 0.000 | 6.18 / 3.051 | 6.18 / 3.051 | 2.00 / 0.093 | 3.90 / 0.887 | 3.90 / 0.887 | 3.51 / 0.670 | 0.73 / 0.000 | harness mapping: SVG filter-region clipping (`#blur-lg`/`#blur-md` x=-20 % regions; `LAYER_BBOX_SCISSOR=1` -> 0.075 / 0.195) plus UNCAPTURED shadow-edge for the remaining band (bbox (145,1)-(316,6) at 2x, (28,2)-(432,16) at 4x; frame-extension probe: 237 -> 0 px); #324 pending (338 build = master) |
| **gemini-3-1-pro-preview** | 2.71 / 0.132 | 2.71 / 0.132 | 2.15 / 0.003 | 5.20 / 0.382 | 5.20 / 0.382 | 4.04 / 0.041 | 2.90 / 0.183 | 2.90 / 0.183 | 2.77 / 0.183 | 1.05 / 0.000 | UNCAPTURED shadow-edge: all 219 structural px at 4x lie in rows 0-40; `#drop-shadow` (feDropShadow) stripped both sides -> 0.003; no other filter moves it; 1x/2x master->stack #324 pending (3 unclipped) |
| **gemini-3-7-flash** | 1.37 / 0.003 | 1.37 / 0.003 | 1.37 / 0.003 | 3.82 / 0.694 | 3.82 / 0.694 | 3.82 / 0.694 | 5.84 / 2.671 | 5.84 / 2.671 | 5.84 / 2.671 | 0.02 / 0.000 | harness mapping: `#softGlow` glow idiom (0.653 of 0.694 at 2x, 2.022 of 2.671 at 4x) + #332 `mix-blend-mode: screen` (0.041 / 0.649), per blur-quadrature-evidence.md (c); master = stack (0 px) |
| **gemini-3-8-flash** | 1.21 / 0.119 | 1.21 / 0.119 | 1.21 / 0.119 | 2.40 / 0.049 | 2.40 / 0.049 | 2.40 / 0.049 | 2.37 / 0.000 | 2.37 / 0.000 | 2.37 / 0.000 | 0.63 / 0.002 | harness mapping: SVG filter-region clipping (`LAYER_BBOX_SCISSOR=1` -> 0.033, bbox (212,115)-(249,169); NO_SHADOW/NO_MASK/NO_TURBULENCE unchanged); master = stack (0 px) |
| **glm-5-3-flash** | 1.25 / 0.332 | 1.25 / 0.332 | 0.45 / 0.000 | 2.16 / 0.860 | 2.16 / 0.860 | 0.66 / 0.000 | 4.43 / 2.847 | 4.43 / 2.847 | 0.84 / 0.000 | 0.30 / 0.000 | stack 0.000; #324 pending (338 build = master) |
| **glm-5-3** | 0.47 / 0.013 | 0.47 / 0.013 | 0.08 / 0.000 | 1.71 / 0.418 | 1.71 / 0.418 | 0.17 / 0.000 | 2.72 / 1.275 | 2.72 / 1.275 | 0.10 / 0.000 | 0.03 / 0.000 | stack 0.000; #324 pending |
| **glm-5v-turbo** | 1.22 / 0.000 | 1.22 / 0.000 | 1.16 / 0.000 | 2.86 / 0.069 | 2.86 / 0.069 | 2.55 / 0.008 | 1.07 / 0.000 | 1.07 / 0.000 | 1.04 / 0.000 | 0.16 / 0.000 | stack <= 0.008; #324 pending (2x 0.069 -> 0.008) |
| **gpt-5-2-pro** | 3.36 / 0.185 | 3.36 / 0.185 | 3.36 / 0.186 | 11.65 / 3.615 | 11.65 / 3.615 | 11.62 / 3.611 | 27.44 / 15.653 | 27.44 / 15.653 | 27.50 / 15.659 | 0.06 / 0.000 | harness mapping: `#softShadow` drop-shadow idiom on ten groups (0.153 / 3.402 / 15.083) + #332 feBlend multiply (0.033 / 0.209 / 0.576), per blur-quadrature-evidence.md (c); master = stack to 0.01 pt |
| **gpt-5-6-luna-pro** | 0.49 / 0.013 | 0.49 / 0.013 | 0.27 / 0.000 | 1.51 / 0.388 | 1.51 / 0.388 | 0.43 / 0.000 | 0.32 / 0.001 | 0.32 / 0.001 | 0.18 / 0.000 | 0.01 / 0.000 | stack 0.000; #324 pending (2x 0.388) |
| **gpt-5-6-sol-pro** | 2.77 / 0.175 | 2.77 / 0.175 | 2.64 / 0.153 | 8.28 / 2.579 | 8.28 / 2.579 | 7.71 / 2.450 | 15.08 / 8.717 | 15.08 / 8.717 | 14.37 / 8.176 | 0.41 / 0.000 | harness mapping: `#shadow` drop-shadow idiom sd 15 (idiom stripped both sides -> 0.000 at every zoom); #332 multiply 0.000 once the idiom is out; master->stack 0.02-0.54 pt #324 pending |
| **gpt-5-6-sol** | 0.55 / 0.041 | 0.55 / 0.041 | 0.11 / 0.000 | 2.08 / 0.572 | 2.08 / 0.572 | 0.29 / 0.000 | 6.78 / 3.991 | 6.78 / 3.991 | 0.48 / 0.000 | 0.01 / 0.000 | stack 0.000; #324 pending |
| **gpt-5-6-terra-pro** | 2.60 / 0.194 | 2.60 / 0.194 | 2.58 / 0.193 | 6.29 / 2.450 | 6.29 / 2.450 | 6.23 / 2.375 | 8.77 / 5.437 | 8.77 / 5.437 | 8.52 / 5.191 | 0.00 / 0.000 | harness mapping: `#shadow` drop-shadow idiom sd 15 on face and neck (stripped both sides -> 0.000); master = stack to 0.25 pt |
| **gpt-6-astra** | 0.73 / 0.050 | 0.73 / 0.050 | 0.15 / 0.000 | 2.59 / 0.735 | 2.59 / 0.735 | 0.21 / 0.000 | 3.46 / 1.451 | 3.46 / 1.451 | 0.37 / 0.000 | 0.03 / 0.000 | stack 0.000; #324 pending (8 unclipped) |
| grok-4-5 | 0.78 / 0.000 | 0.78 / 0.000 | 0.78 / 0.000 | 0.74 / 0.000 | 0.74 / 0.000 | 0.74 / 0.000 | 0.35 / 0.000 | 0.35 / 0.000 | 0.35 / 0.000 | 0.10 / 0.000 | stack 0.000;  |
| **kimi-k2-6** | 8.01 / 6.192 | 8.01 / 6.192 | 0.22 / 0.000 | 21.35 / 18.713 | 21.35 / 18.713 | 0.37 / 0.000 | 28.93 / 26.980 | 28.93 / 26.980 | 0.69 / 0.058 | 0.03 / 0.000 | UNCAPTURED shadow-edge at 4x: `#shadow-soft` (feDropShadow dy 8 sd 10 on hair-back/eyebrows/hair-front) stripped both sides -> 0.000; band rows 0-14 cols 356-407, femtovg +10-13/255 lighter; frame-extension probe 69 -> 0 px; #324 pending: 6.192 / 18.713 / 26.980 -> 0.000 / 0.000 / 0.058 (338 build = master) |
| **kimi-k3** | 1.57 / 0.340 | 1.57 / 0.340 | 0.63 / 0.000 | 5.37 / 2.295 | 5.37 / 2.295 | 1.45 / 0.000 | 4.30 / 2.063 | 4.30 / 2.063 | 1.02 / 0.000 | 0.31 / 0.000 | stack 0.000; #324 pending |
| **muse-spark-1-3-contributor** | 1.34 / 0.248 | 1.34 / 0.248 | 0.76 / 0.041 | 4.06 / 1.599 | 4.06 / 1.599 | 1.47 / 0.000 | 1.90 / 0.293 | 1.90 / 0.293 | 0.84 / 0.000 | 0.07 / 0.000 | 1x 0.041 (under threshold, above the 0.000 envelope): a 3-row line at (199,115)-(260,117); `LAYER_BBOX_SCISSOR=1` -> 0.013 (filter-region class); NO_SHADOW/NO_MASK/NO_TURBULENCE unchanged; #324 pending |
| **muse-spark-1-3** | 0.82 / 0.216 | 0.82 / 0.216 | 0.30 / 0.000 | 2.63 / 1.285 | 2.63 / 1.285 | 0.64 / 0.000 | 1.76 / 0.646 | 1.76 / 0.646 | 0.77 / 0.000 | 0.07 / 0.000 | stack 0.000; #324 pending |
| **nex-n2-pro** | 3.40 / 1.486 | 3.40 / 1.486 | 0.51 / 0.000 | 7.62 / 4.366 | 7.62 / 4.366 | 1.10 / 0.000 | 5.91 / 2.514 | 5.91 / 2.514 | 1.28 / 0.088 | 0.17 / 0.000 | UNCAPTURED shadow-edge at 4x: `#hairShadow` (feDropShadow dy 16 sd 14 on hair-back/hair-front) stripped both sides -> 0.000 (105 -> 0 band px); the other four filters change nothing; #332 share 0.002; #324 pending (338 build = master) |
| ox-alpha | 0.12 / 0.000 | 0.09 / 0.000 | 0.09 / 0.000 | 0.38 / 0.000 | 0.26 / 0.000 | 0.20 / 0.000 | 0.70 / 0.002 | 0.44 / 0.000 | 0.36 / 0.000 | 0.01 / 0.000 | stack 0.000; master 0.000-0.002 |
| **qwen3-8-2-4t-a95b** | 1.26 / 0.209 | 1.29 / 0.227 | 0.62 / 0.000 | 4.05 / 1.563 | 4.14 / 1.644 | 1.01 / 0.000 | 8.08 / 4.771 | 8.08 / 4.782 | 0.89 / 0.000 | 0.43 / 0.000 | stack 0.000; #324 pending (338 build 0.227 / 1.644 / 4.782, i.e. turbulence without clip is no better) |
| **qwen3-8-27b** | 0.56 / 0.145 | 0.56 / 0.145 | 0.16 / 0.000 | 1.20 / 0.095 | 1.20 / 0.095 | 0.23 / 0.000 | 1.24 / 0.057 | 1.24 / 0.057 | 0.20 / 0.000 | 0.05 / 0.000 | stack 0.000; #324 pending |
| **qwen3-8-flash** | 1.10 / 0.182 | 1.10 / 0.186 | 0.19 / 0.000 | 3.93 / 1.643 | 4.05 / 1.645 | 0.41 / 0.000 | 7.68 / 4.916 | 8.53 / 5.142 | 0.56 / 0.000 | 0.00 / 0.000 | stack 0.000; #324 pending (338 build 0.186 / 1.645 / 5.142) |
| **qwen3-8-max** | 0.90 / 0.307 | 0.32 / 0.059 | 0.14 / 0.000 | 3.22 / 1.865 | 1.04 / 0.416 | 0.38 / 0.000 | 4.92 / 3.754 | 2.63 / 1.950 | 0.11 / 0.000 | 0.03 / 0.000 | stack 0.000; #338 pending 0.248 / 1.449 / 1.804 + #324 pending 0.059 / 0.416 / 1.950 |
| **mean (27)** | 1.94 / 0.632 | 1.80 / 0.527 | 0.85 / 0.026 | 5.36 / 2.582 | 4.82 / 2.111 | 2.07 / 0.358 | 7.93 / 5.078 | 6.96 / 4.158 | 3.11 / 1.303 | 0.19 / 0.000 | |

Stack files above 0.05 % structural: claude-fable-5-1 (2x 0.324, 4x 2.490); gemini-3-1-pro-preview (4x 0.183); gemini-3-1-pro-preview-custom-tools (2x 0.093, 4x 0.670); gemini-3-7-flash (2x 0.694, 4x 2.671); gemini-3-8-flash (1x 0.119); gpt-5-2-pro (1x 0.186, 2x 3.611, 4x 15.659); gpt-5-6-sol-pro (1x 0.153, 2x 2.450, 4x 8.176); gpt-5-6-terra-pro (1x 0.193, 2x 2.375, 4x 5.191); kimi-k2-6 (4x 0.058); nex-n2-pro (4x 0.088).

## corpus/banner, ember, svsdeid, mask-* (1x)

| file | master | stack | Chromium vs Firefox | attribution |
|---|---|---|---|---|
| banner | 5.25 / 4.293 | 5.25 / 4.293 | 0.02 / 0.000 | #332 (`mix-blend-mode: color-burn` group): stripped both sides 4.293 -> 0.112. Remainder 0.112 is #327: the outlined wordmark/tagline paths (7 paths, no live text) read femtovg/Chromium light-pixel ink 5.41x at box 200, 1.83x at box 400, 1.09x at box 800, structural 1.68 % -> 0.41 % -> 0.000 % of the banner area; master = stack (11 px) |
| ember | 1.32 / 0.000 | 1.28 / 0.000 | 0.03 / 0.000 | match (0.000 structural) |
| svsdeid | 0.33 / 0.000 | 0.33 / 0.000 | 0.19 / 0.000 | match (0.000 structural) |
| mask-luminance-radial-transform | 0.00 / 0.000 | 0.00 / 0.000 | 0.00 / 0.000 | match (0.000 structural) |
| mask-nested-origin-reduction | 0.13 / 0.000 | 0.13 / 0.000 | 0.00 / 0.000 | match (0.000 structural) |

## WPT css-masking (manifest framings, Chromium refs from corpus/wpt/chromium; numbers over the SVG box)

| case | zoom | master | stack | Chr vs FF (1x) | attribution |
|---|---|---|---|---|---|
| clip-path-clip-nested-twice | 1 | 75.00 / 69.030 | 53.43 / 48.610 | 0.00 / 0.000 | harness mapping: `<clipPath clip-path=...>` ancestor chain (`clip_ancestors` exists only in corpus/wpt/_wpt_masks.rs; RESULTS.md: 0 px with it). master->stack delta #324 pending |
| clip-path-clip-nested-twice | 2 | 75.00 / 72.007 | 53.53 / 51.123 |  | as 1x |
| mask-and-nested-clip-path | 1 | 33.33 / 31.577 | 11.11 / 10.240 | 0.00 / 0.000 | harness mapping: clipPath ancestor chain (as above). master->stack delta #324 pending |
| mask-and-nested-clip-path | 2 | 33.33 / 32.450 | 11.11 / 10.671 |  | as 1x |
| mask-negative-scale | 1 | 0.00 / 0.000 | 0.00 / 0.000 | 0.00 / 0.000 | match |
| mask-negative-scale | 2 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| mask-nested-clip-path-001 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: `<rect clip-path=...>` inside `<clipPath>` (`capture_clip_coverage`, _wpt_masks.rs only; RESULTS.md 0 px). master = stack |
| mask-nested-clip-path-001 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-002 | 1 | 64.00 / 55.200 | 0.00 / 0.000 | 0.00 / 0.000 | #324 pending on master (clip inside the mask drawn unclipped); stack 0 px (finding A fixed in merged #323) |
| mask-nested-clip-path-002 | 2 | 64.00 / 59.600 | 0.00 / 0.000 |  | as 1x |
| mask-nested-clip-path-003 | 1 | 64.00 / 55.200 | 0.00 / 0.000 | 0.00 / 0.000 | #324 pending on master; stack 0 px |
| mask-nested-clip-path-003 | 2 | 64.00 / 59.600 | 0.00 / 0.000 |  | as 1x |
| mask-nested-clip-path-004 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: clip coverage (as -001) |
| mask-nested-clip-path-004 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-005 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: clip coverage (as -001) |
| mask-nested-clip-path-005 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-006 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: clip coverage (as -001) |
| mask-nested-clip-path-006 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-007 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: clip coverage (as -001) |
| mask-nested-clip-path-007 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-008 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: clip coverage (as -001) |
| mask-nested-clip-path-008 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-009 | 1 | 64.00 / 55.200 | 64.00 / 55.200 | 0.00 / 0.000 | harness mapping: clip coverage (as -001) |
| mask-nested-clip-path-009 | 2 | 64.00 / 59.600 | 64.00 / 59.600 |  | as 1x |
| mask-nested-clip-path-010 | 1 | 49.75 / 46.800 | 0.00 / 0.000 | 0.00 / 0.000 | #324 pending on master; stack 0 px |
| mask-nested-clip-path-010 | 2 | 49.75 / 48.265 | 0.00 / 0.000 |  | as 1x |
| mask-nested-clip-path-panning-001 | 1 | 64.00 / 55.200 | 0.00 / 0.000 | 0.00 / 0.000 | #324 pending on master; stack 0 px |
| mask-nested-clip-path-panning-001 | 2 | 64.00 / 59.600 | 0.00 / 0.000 |  | as 1x |
| mask-nested-clip-path-panning-002 | 1 | 64.00 / 55.200 | 0.00 / 0.000 | 0.00 / 0.000 | #324 pending on master; stack 0 px |
| mask-nested-clip-path-panning-002 | 2 | 64.00 / 59.600 | 0.00 / 0.000 |  | as 1x |
| mask-objectboundingbox-content-clip-transform | 1 | 5.74 / 3.223 | 0.68 / 0.000 | 0.15 / 0.000 | #324 pending on master (0.609 -> 0.000); stack residual 0.13 % px>20 / 0.000 structural = finding B (hard clip edge, #324's documented follow-up) |
| mask-objectboundingbox-content-clip-transform | 2 | 5.56 / 4.162 | 0.32 / 0.000 |  | as 1x |
| mask-objectboundingbox-content-clip | 1 | 5.74 / 3.223 | 0.68 / 0.000 | 0.15 / 0.000 | as above |
| mask-objectboundingbox-content-clip | 2 | 5.56 / 4.162 | 0.32 / 0.000 |  | as 1x |
| mask-on-thin-stroked-path-userspaceonuse | 1 | 0.00 / 0.000 | 0.00 / 0.000 | 0.00 / 0.000 | match |
| mask-on-thin-stroked-path-userspaceonuse | 2 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| mask-text-001 | 1 | 1.75 / 0.010 | 1.75 / 0.010 | 1.81 / 0.000 | match |
| mask-text-001 | 2 | 1.24 / 0.020 | 1.24 / 0.020 |  | same |
| mask-userspaceonuse-content-clip-transform | 1 | 5.74 / 3.223 | 0.68 / 0.000 | 0.15 / 0.000 | as above |
| mask-userspaceonuse-content-clip-transform | 2 | 5.56 / 4.162 | 0.32 / 0.000 |  | as 1x |
| mask-userspaceonuse-content-clip | 1 | 5.74 / 3.223 | 0.68 / 0.000 | 0.15 / 0.000 | as above |
| mask-userspaceonuse-content-clip | 2 | 5.56 / 4.162 | 0.32 / 0.000 |  | as 1x |
| mask-with-filter | 1 | 0.00 / 0.000 | 0.00 / 0.000 | 0.00 / 0.000 | match |
| mask-with-filter | 2 | 0.00 / 0.000 | 0.00 / 0.000 |  | same |
| mask-text-001-arial | 1 | 2.03 / 0.080 | 2.03 / 0.080 | 1.83 / 0.000 | harness mapping (text/fonts): box-structural 0.080 at 1x (32 px of the 100x100 box) and 0.075 at 2x (30 px); usvg shapes the text into paths, Chromium rasterises glyphs; RESULTS.md's `_wpt_masks.rs` `<text>` translation reads 0.000 here. Master = stack |
| mask-text-001-arial | 2 | 1.56 / 0.075 | 1.56 / 0.075 |  | as 1x |
| **mean (22)** | 1 | 38.64 / 33.373 | 22.57 / 19.363 | | |
| **mean (22)** | 2 | 38.57 / 35.872 | 22.47 / 20.830 | | |

The 2026-09-16 RESULTS.md numbers (0 px on every clip-coverage / ancestor-chain case) were measured with `_wpt_masks.rs`, which adds those two translations to `_logos_full.rs`; this pass uses the plain `_logos_full` binaries, so those cases read as harness mapping here. The four finding-A files (-002, -003, -panning-001/-002) that failed on the pre-review #323 build now pass on the stack with 0 px.

## SVGenius (104 files, 625x625, box 625 at (0,0), 1x; master = stack on every file)

Mean over 104: 1.69 / 1.128; over the 97 files with a square viewBox: 0.31 / 0.000 (all 97 at 0.000 structural; Chromium vs Firefox mean 0.11 / 0.000). The seven files above threshold all declare a non-square viewBox with `width="200" height="200"`:

| file | viewBox | master = stack | Chr vs FF | width/height stripped, both sides | attribution |
|---|---|---|---|---|---|
| page_13_新年_48727_icon_24 | 0 0 1801 1024 | 40.09 / 38.239 | 0.18 / 0.000 | 0.23 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |
| page_300_马上创业网_12940_icon_61 | 0 0 1390 1024 | 28.29 / 25.429 | 0.01 / 0.000 | 0.02 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |
| page_37_教育图标_45273_icon_0 | 0 0 1115 1024 | 25.49 / 20.339 | 0.03 / 0.000 | 0.09 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |
| page_251_费哲软件IWMS_27516_icon_60 | 0 0 1154 1024 | 24.85 / 19.924 | 0.35 / 0.000 | 0.18 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |
| page_67_吃货联萌_40773_icon_25 | 0 0 1067 1024 | 14.74 / 8.925 | 0.23 / 0.000 | 0.13 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |
| page_46_可爱食物_icon_43742_icon_6 | 0 0 1048 1024 | 10.44 / 4.241 | 0.36 / 0.000 | 0.64 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |
| page_11_肖像_48949_icon_2 | 0 0 1033 1024 | 1.87 / 0.166 | 0.00 / 0.000 | 0.00 / 0.000 | harness mapping: `make_ref.py` fits the viewBox xMinYMin into the box while usvg fits it xMidYMid into the file's 200x200 size first |

## Inventory map

| item | files it explains in this pass |
|---|---|
| #324 pending (clip) | clipdemo; kit (master->stack part); 20 BuseyBench master residuals (claude-fable-5-1, claude-opus-5 [with #338], fugu-ultra, gemini-3-1-pro-preview[-custom-tools] 1x/2x, glm-5-3[-flash], glm-5v-turbo, gpt-5-6-luna-pro, gpt-5-6-sol[-pro delta], gpt-6-astra, kimi-k2-6, kimi-k3, muse-spark-1-3[-contributor], nex-n2-pro 1x/2x, qwen3-8-2-4t-a95b, qwen3-8-27b, qwen3-8-flash, qwen3-8-max [with #338]); WPT mask-nested-clip-path-002/-003/-010/-panning-001/-002, the four *-content-clip* cases (finding B is its documented follow-up), the master half of clip-path-clip-nested-twice / mask-and-nested-clip-path |
| #338 pending (turbulence) | claude-opus-5 (2.6 / 11.4 / 23.2 pt), qwen3-8-max (0.25 / 1.45 / 1.80 pt) |
| #332 blend modes | banner (4.18 pt), gemini-3-7-flash `screen` (0.041 / 0.649), gpt-5-2-pro multiply (0.03 / 0.21 / 0.58), nex-n2-pro (0.002) |
| #327 thin fills | banner remainder (0.112), Tiger 1x (0.003), AA-only px>20 on fox-with-box-on-cloud / duckduckgo / mr-settodefault / splash-logo / BuseyBench floors |
| #325 blur kernel | none attributable (no file's residual survives the both-sides ablations with a kernel-shaped remainder) |
| #335 state stack | none (not exercised by the harness) |
| #337 primitives | none on their own; feOffset/feMerge/feComposite occur only inside the drop-shadow idiom chains, where the harness's whole-group blur dominates |
| harness mapping: drop-shadow / glow idiom | claude-fable-5-1, gemini-3-7-flash, gpt-5-2-pro, gpt-5-6-sol-pro, gpt-5-6-terra-pro |
| harness mapping: filter-region clipping | gemini-3-8-flash 1x (0.086 of 0.119), custom-tools (0.475 of 0.670 at 4x, 0.018 at 2x), muse-spark-1-3-contributor 1x (0.028 of 0.041) |
| harness mapping: usvg ignores `<style>` | kit (all zooms, stack side) |
| harness mapping: `_wpt_masks.rs`-only translations | WPT -001, -004..-009 (clip coverage); clip-path-clip-nested-twice, mask-and-nested-clip-path (ancestor chain) |
| harness mapping: fonts | mask-text-001, mask-text-001-arial |
| harness mapping: `make_ref.py` framing | 7 SVGenius files with non-square viewBox |
| UNCAPTURED: off-canvas layer shadow | gemini-3-1-pro-preview 4x (0.183), nex-n2-pro 4x (0.088), kimi-k2-6 4x (0.058), custom-tools 2x/4x (0.075 / 0.195) |

## Files

`sweep.py` (the driver), `regression-2026-09-17-metrics.json` (all numbers: per file, zoom, binary, plus Chromium-vs-Firefox and master-vs-stack), `regression-2026-09-17-shadow-edge.png`, `corpus/shadow-offcanvas-reduction.svg`.
