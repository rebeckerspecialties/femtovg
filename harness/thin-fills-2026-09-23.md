# Thin fills (#327) and zero-area fills (#341) evidence, 2026-09-23

Branch thin-fills (stacked on mix-blend, femtovg/femtovg#356): antialiased
fills rasterized as exact per-pixel coverage on wgpu; a contour that
encloses nothing draws nothing. Before = #356's head (`_logos_full_mixblend7`),
after = `_logos_full_coverage1`, one harness, `SKIP_UNSUPPORTED_FILTERS=1
VIEWPORT_CLIP=1`, against Chromium 131. Columns: percent of pixels beyond
8/255 / structural after a 2 px erosion.

## Ink of a filled bar against its exact area (tests/coverage_fill_wgpu.rs)

    width | 45 deg | 30 deg      (master: 2.44x / 1.45x / 1.12x / 0.98x / 1.02x at 45 deg after #336)
    0.25 px | 0.998 | 1.000
    0.5 px  | 0.998 | 0.999
    1 px    | 1.001 | 0.999
    2 px    | 1.000 | 1.000
    4 px    | 0.999 | 1.000

Every pixel of a bar, an L, a triangle, a ring under nonzero and even-odd
(either hole winding) and a shape reaching past the canvas is within 2/255
of the area the path covers in it (analytic polygon clipping).

## The banner's text at 460x260 (#327's over-ink)

Near-white pixels in the text band: before 1069, after 737, Chromium 735.
`thin-fills-banner-text-1x.png` (6x nearest).

## Every corpus file with a Chromium reference, 1x / 2x / 4x

51 frames: 43 better, 7 unchanged, 1 within noise (gpt-5-2-pro at 4x,
45.88 -> 45.89). Mean px>8 4.308 -> 4.095; mean structural 1.466 -> 1.449.
(`harness/thin-fills-corpus-2026-09-23.txt`)

    file zoom | before px>8 struct | after px>8 struct
    banner 1 | 0.51% 0.132% | 0.14% 0.000%
    banner 2 | 0.01% 0.000% | 0.01% 0.000%
    banner 4 | 0.00% 0.000% | 0.00% 0.000%
    fox-with-box-on-cloud 1 | 1.84% 0.001% | 1.52% 0.000%
    fox-with-box-on-cloud 2 | 2.78% 0.000% | 2.53% 0.000%
    fox-with-box-on-cloud 4 | 2.18% 0.000% | 2.02% 0.000%
    fugu-ultra 1 | 2.27% 0.025% | 2.23% 0.018%
    fugu-ultra 2 | 5.18% 0.138% | 5.16% 0.135%
    fugu-ultra 4 | 5.00% 0.039% | 4.98% 0.040%
    gemini-3-1-pro-preview 1 | 4.66% 0.136% | 4.03% 0.008%
    gemini-3-1-pro-preview 2 | 8.88% 0.641% | 7.39% 0.102%
    gemini-3-1-pro-preview 4 | 8.03% 0.815% | 8.02% 0.814%
    gemini-3-7-flash 1 | 2.25% 0.009% | 1.75% 0.001%
    gemini-3-7-flash 2 | 4.56% 0.000% | 3.82% 0.000%
    gemini-3-7-flash 4 | 5.24% 0.000% | 4.77% 0.000%
    glm-5v-turbo 1 | 1.61% 0.022% | 1.27% 0.007%
    glm-5v-turbo 2 | 2.55% 0.001% | 2.24% 0.000%
    glm-5v-turbo 4 | 2.35% 0.000% | 2.10% 0.000%
    google-workspace-48px 1 | 0.27% 0.000% | 0.22% 0.000%
    google-workspace-48px 2 | 0.32% 0.000% | 0.27% 0.000%
    google-workspace-48px 4 | 0.18% 0.000% | 0.17% 0.000%
    gpt-5-2-pro 1 | 5.61% 1.679% | 5.60% 1.681%
    gpt-5-2-pro 2 | 18.94% 10.283% | 18.94% 10.271%
    gpt-5-2-pro 4 | 45.88% 33.327% | 45.89% 33.293%
    gpt-5-6-sol 1 | 0.72% 0.000% | 0.69% 0.000%
    gpt-5-6-sol 2 | 1.31% 0.000% | 1.27% 0.000%
    gpt-5-6-sol 4 | 1.56% 0.000% | 1.55% 0.000%
    gpt-5-6-sol-pro 1 | 5.95% 1.349% | 5.67% 1.345%
    gpt-5-6-sol-pro 2 | 17.47% 7.528% | 17.11% 7.543%
    gpt-5-6-sol-pro 4 | 30.43% 17.737% | 30.36% 17.738%
    kimi-k3 1 | 1.94% 0.006% | 1.80% 0.002%
    kimi-k3 2 | 4.34% 0.081% | 3.95% 0.083%
    kimi-k3 4 | 4.37% 0.158% | 4.37% 0.156%
    kit-in-circle 1 | 0.51% 0.000% | 0.49% 0.000%
    kit-in-circle 2 | 0.81% 0.000% | 0.76% 0.000%
    kit-in-circle 4 | 0.83% 0.000% | 0.80% 0.000%
    nex-n2-pro 1 | 1.42% 0.004% | 1.05% 0.002%
    nex-n2-pro 2 | 3.20% 0.017% | 2.72% 0.013%
    nex-n2-pro 4 | 5.21% 0.594% | 5.21% 0.595%
    qwen3-8-max 1 | 0.67% 0.000% | 0.59% 0.000%
    qwen3-8-max 2 | 1.92% 0.001% | 1.77% 0.001%
    qwen3-8-max 4 | 1.54% 0.028% | 1.53% 0.028%
    thin-fill-crescent 1 | 0.08% 0.000% | 0.07% 0.000%
    thin-fill-crescent 2 | 0.00% 0.000% | 0.00% 0.000%
    thin-fill-crescent 4 | 0.00% 0.000% | 0.00% 0.000%
    world-cup-widgets-cta 1 | 0.71% 0.000% | 0.61% 0.000%
    world-cup-widgets-cta 2 | 1.05% 0.000% | 0.96% 0.000%
    world-cup-widgets-cta 4 | 0.47% 0.000% | 0.45% 0.000%
    zero-area-fill 1 | 0.80% 0.000% | 0.00% 0.000%
    zero-area-fill 2 | 0.87% 0.000% | 0.00% 0.000%
    zero-area-fill 4 | 0.43% 0.000% | 0.00% 0.000%

1840x1040: banner 0.08 -> 0.04, fox-with-box-on-cloud 0.41 -> 0.39,
thin-fill-crescent 0.02 -> 0.02, kimi-k3 0.55 -> 0.55, kit 5.93 -> 5.93.
Sheet: `thin-fills-evidence-4x.png`.

## #341 alone (d32dcd2 vs #356), 460x260

    file zoom | before px>8/struct | after px>8/struct
zero-area-fill 1 | 0.80% 0.000% | 0.00% 0.000% 
zero-area-fill 2 | 0.87% 0.000% | 0.00% 0.000% 
zero-area-fill 4 | 0.43% 0.000% | 0.00% 0.000% 
qwen3-8-max 1 | 0.67% 0.000% | 0.62% 0.000% 
qwen3-8-max 2 | 1.92% 0.001% | 1.80% 0.001% 
qwen3-8-max 4 | 1.54% 0.028% | 1.54% 0.028% 
gemini-3-1-pro-preview 1 | 4.66% 0.136% | 4.39% 0.127% 
gemini-3-1-pro-preview 2 | 8.88% 0.641% | 8.30% 0.641% 
gemini-3-1-pro-preview 4 | 8.03% 0.815% | 8.03% 0.815% 
kimi-k3 1 | 1.94% 0.006% | 1.78% 0.002% 
kimi-k3 2 | 4.34% 0.081% | 3.94% 0.079% 
kimi-k3 4 | 4.37% 0.158% | 4.34% 0.158% 
thin-fill-crescent 1 | 0.08% 0.000% | 0.08% 0.000% 
thin-fill-crescent 2 | 0.00% 0.000% | 0.00% 0.000% 
thin-fill-crescent 4 | 0.00% 0.000% | 0.00% 0.000% 
fox-with-box-on-cloud 1 | 1.84% 0.001% | 1.84% 0.001% 
fox-with-box-on-cloud 2 | 2.78% 0.000% | 2.78% 0.000% 
fox-with-box-on-cloud 4 | 2.18% 0.000% | 2.18% 0.000% 
banner 1 | 0.51% 0.132% | 0.51% 0.132% 
banner 2 | 0.01% 0.000% | 0.01% 0.000% 
banner 4 | 0.00% 0.000% | 0.00% 0.000%

## Cost (harness soak, 200 files at 1x/2x/4x, 3 passes, Apple M4 Max)

    binary    | cpu p50/p95/p99/max ms | wall p50/p95/p99/max ms | maxrss MiB
    #356      |  2.8  134.6  219.7  365.1 |  3.1  129.5  207.8  345.2 | 790.7
    coverage  |  5.1  130.7  194.0  361.8 |  5.1  126.3  180.7  339.8 | 875.1

The median frame nearly doubles: every antialiased fill is now an
accumulate draw and a resolve draw, and every batch of non-overlapping
fills is two render-pass switches. The heavy tail falls: the stencil
passes of large concave fills cost more than the sweep. Knobs left for
review: routing wide convex fills back through the fringe, and packing
regions into one larger atlas so overlapping fills share a batch.
