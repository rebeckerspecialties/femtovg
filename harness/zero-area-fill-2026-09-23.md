# Zero-area fills (#341) evidence, 2026-09-23

Branch zero-area-fill (off master ae66a1e): a fill of a contour whose
points all lie on one line draws nothing. Before = master
(`_logos_full_master_h6`), after = `_logos_full_zeroarea`, one harness,
`SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1`, against Chromium 131. Columns:
percent of pixels beyond 8/255 / structural after a 2 px erosion, at the
460x260 pivot framing (1x/2x/4x) and at 1840x1040 (the whole artwork at four
times the resolution; the sheet crops it 1:1).

Classifier: fewer than three points, or none farther than 1/256 px from the
line through the first point and the point farthest from it. A fixed
device band, so a thin sliver stays a sliver at any zoom; collinearity
rather than area against perimeter, so a unit square on a 1000-unit
retraced tail keeps its area (tests/zero_area_fill_wgpu.rs, six zooms from
1x to 64x).

    file zoom | master px>8/struct | #341 px>8/struct
    zero-area-fill 2 | 0.87% 0.000% | 0.00% 0.000% 
    zero-area-fill 4 | 0.43% 0.000% | 0.00% 0.000% 
    zero-area-fill 1840x1040 | 0.13% 0.000% | 0.00% 0.000% 
    qwen3-8-max 1 | 0.67% 0.000% | 0.62% 0.000% 
    qwen3-8-max 2 | 1.92% 0.001% | 1.80% 0.001% 
    qwen3-8-max 4 | 1.54% 0.028% | 1.54% 0.028% 
    qwen3-8-max 1840x1040 | 0.34% 0.000% | 0.32% 0.000% 
    gemini-3-1-pro-preview 1 | 4.66% 0.136% | 4.39% 0.127% 
    gemini-3-1-pro-preview 2 | 8.88% 0.641% | 8.30% 0.641% 
    gemini-3-1-pro-preview 4 | 8.03% 0.815% | 8.03% 0.815% 
    gemini-3-1-pro-preview 1840x1040 | 4.12% 2.073% | 4.12% 2.071% 
    kimi-k3 1 | 2.04% 0.005% | 1.88% 0.002% 
    kimi-k3 2 | 4.56% 0.089% | 4.18% 0.087% 
    kimi-k3 4 | 4.90% 0.158% | 4.87% 0.158% 
    kimi-k3 1840x1040 | 0.60% 0.046% | 0.60% 0.046% 

## 920x520 (twice the default framing, the tooth strokes at their thinnest visible width), zoom 1

    file | master px>8/struct | #341 px>8/struct
    zero-area-fill 920x520 | 0.27% 0.000% | 0.00% 0.000% 
    qwen3-8-max 920x520 | 0.52% 0.000% | 0.49% 0.000% 
    kimi-k3 920x520 | 1.39% 0.023% | 1.29% 0.022% 
    gemini-3-1-pro-preview 920x520 | 2.60% 0.136% | 2.46% 0.136%

Darkness (sum of 255 - min channel, /255) over the 240x135 window where the
PR fixes most pixels, master / #341 / Chromium: qwen3-8-max 23877 / 23830 /
23816, kimi-k3 18675 / 18589 / 18486, gemini-3-1-pro-preview 16676 / 16500 /
16453 - the fill under the tooth strokes is what the PR removes, and it is
most of the way to Chromium. Sheet: `zero-area-evidence-2x.png` (1:1 crops).

The reduction (a bare path and a bare line under the default black fill)
goes to exact. The three BuseyBench portraits draw their teeth as open
paths with strokes on top; the black band under a stroke narrower than
about three device pixels, or translucent, is gone at 1x and 2x, and at 4x
the strokes cover it either way. Sheet: `zero-area-evidence-4x.png`.

## Old-vs-new A/B over every corpus (`harness/ab.py`)

`ab.py --a _logos_full_master_h6 --b _logos_full_zeroarea` over the 8 corpus
icons, 27 BuseyBench portraits, 55 Firefox assets, 33 resvg cases, 9 probes
and the 10 demo-assets reductions at 1x/2x/4x (426 frames), plus 100
SVGenius files at 1x: 50 + 6 frames differ
(`harness/zero-area-fill-ab-2026-09-23.txt`): the reduction, 15 BuseyBench
portraits whose teeth or hair strands are open paths under the default
fill, five icons and six SVGenius files by single-digit pixel counts.
Every changed file with a Chromium reference moves toward it or stays
within a few pixels (`harness/zero-area-fill-changed-2026-09-23.txt`).
Everything else is bit-identical.
