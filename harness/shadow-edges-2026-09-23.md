# Shadow casters at the canvas edges (#342, PR #361), 2026-09-23

Master ae66a1e (`_logos_full_master_h8`) versus branch shadow-capture
(`_logos_full_shadowcap`), one harness, against Chromium 131 at the
460x260 pivot framing. Columns: percent of pixels beyond 8/255 /
structural; then shadow pixels in the box (darker than the background by
more than 8/255), Chromium / master / #361.

    case zoom | master | #361 | shadow px
    above-dy16 2 | 0.00% 0.000% | 0.00% 0.000% | 0/0/0
    above-dy0 1 | 0.00% 0.000% | 0.00% 0.000% | 0/0/0
    above-dy0 2 | 0.00% 0.000% | 0.00% 0.000% | 0/0/0
    left-dx16 1 | 1.05% 0.696% | 0.00% 0.000% | 1250/0/1330
    left-dx16 2 | 4.34% 3.627% | 0.00% 0.000% | 5188/0/5194
    beyond-right 1 | 0.00% 0.000% | 0.00% 0.000% | 1250/1330/1330
    beyond-right 2 | 0.00% 0.000% | 0.00% 0.000% | 5188/5192/5194
    beyond-bottom 1 | 0.00% 0.000% | 0.00% 0.000% | 886/936/936
    beyond-bottom 2 | 0.00% 0.000% | 0.00% 0.000% | 0/0/0
    crossing-top 1 | 0.09% 0.012% | 0.00% 0.000% | 4438/4502/4580
    crossing-top 2 | 0.52% 0.216% | 0.00% 0.000% | 7574/7332/7582

The site was the layer's capture (the scissor's rect plus a blur's
reach), not the shadow pass, which sizes its box from the shape it is
given without a canvas clamp: with the capture taking in what reaches into
the scissor once shifted by the offset and spread by the blur, every
placement is exact. #342's four BuseyBench files, structural at 4x:
gemini-3-1-pro-preview 0.857 -> 0.278, gemini-3-1-pro-preview-custom-tools
3.543 -> 2.742, nex-n2-pro 0.594 -> 0.271, kimi-k2-6 0.228 -> 0.104.
