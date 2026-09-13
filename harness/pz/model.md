# Pi Zero model (ARM11 1 GHz, VideoCore IV GLES2, 1.5 GB/s shared)

Modelled, not measured. Inputs are the measured per-frame counts in measurements.md; rates and factors are the assumptions below. `frame best` = max(CPU, GPU) (perfect overlap), `frame worst` = CPU + GPU (synchronous driver). Verdicts use the central assumptions and the best-case overlap; the pessimistic verdict uses the slow-end assumptions without overlap. GPU mem = image texels + a stencil attachment per image target + screen buffers + blur scratch + vertex buffer.

## Assumptions (central, optimistic, pessimistic)

| parameter | central | optimistic | pessimistic |
|---|---|---|---|
| color_gfrag | 0.4 | 0.6 | 0.3 |
| image_gfrag | 0.3 | 0.5 | 0.2 |
| stencil_gfrag | 0.8 | 1.0 | 0.6 |
| clear_gfrag | 1.0 | 1.2 | 0.8 |
| tap_gtap | 1.0 | 1.5 | 0.7 |
| noise_gtap | 0.5 | 0.8 | 0.35 |
| bandwidth_gbs | 1.5 | 2.0 | 1.0 |
| zs_fraction | 0.5 | 0.0 | 1.0 |
| cpu_factor | 45.0 | 30.0 | 60.0 |
| us_per_draw | 60.0 | 30.0 | 120.0 |
| us_per_pass | 150.0 | 80.0 | 300.0 |
| us_per_tex_alloc | 600.0 | 300.0 | 1500.0 |
| stencil_bpp | 4 | 1 | 4 |

## icons @ 640x480

| file | GPU frag ms | GPU tile ms | GPU ms | CPU record ms | draw calls | CPU GL ms | CPU ms | frame ms (range) | verdict | pessimistic | GPU mem MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| google-workspace-48px | 38.7 | 24.0 | 62.8 | 3.9 | 25 | 3.9 | 7.8 | 63 (38-117) | 10-30 fps | non-interactive | 19 |
| clipdemo | 4.1 | 1.2 | 5.3 | 1.3 | 25 | 1.5 | 2.8 | 5 (4-13) | 60 fps | 60 fps | 4 |
| kit | 7.2 | 17.5 | 24.7 | 4.3 | 29 | 3.1 | 7.4 | 25 (14-57) | 30 fps | 10-30 fps | 10 |
| splash-logo | 1.6 | 1.2 | 2.8 | 2.3 | 39 | 2.3 | 4.6 | 5 (3-12) | 60 fps | 60 fps | 4 |
| mr-settodefault | 7.7 | 8.2 | 15.9 | 9.6 | 139 | 8.9 | 18.5 | 19 (11-58) | 30 fps | 10-30 fps | 6 |
| fox-with-box-on-cloud | 4.2 | 1.2 | 5.4 | 8.3 | 184 | 11.0 | 19.3 | 19 (11-41) | 30 fps | 10-30 fps | 4 |
| duckduckgo-com_2x | 3.1 | 4.7 | 7.9 | 3.5 | 38 | 2.6 | 6.1 | 8 (5-24) | 60 fps | 30 fps | 6 |
| Ghostscript_Tiger | 5.1 | 1.2 | 6.3 | 23.9 | 869 | 52.1 | 76.1 | 76 (42-145) | 10-30 fps | non-interactive | 5 |

## busey @ 640x480

| file | GPU frag ms | GPU tile ms | GPU ms | CPU record ms | draw calls | CPU GL ms | CPU ms | frame ms (range) | verdict | pessimistic | GPU mem MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 1560.4 | 1091.9 | 2652.3 | 29.5 | 1336 | 208.4 | 237.9 | 2652 (1548-4886) | non-interactive | non-interactive | 29 |
| claude-opus-5 | 1377.1 | 742.1 | 2119.2 | 22.0 | 1013 | 154.1 | 176.1 | 2119 (1254-3804) | non-interactive | non-interactive | 37 |
| fugu-ultra | 324.9 | 553.1 | 878.1 | 22.0 | 796 | 104.6 | 126.6 | 878 (492-1814) | non-interactive | non-interactive | 38 |
| gemini-3-1-pro-preview-custom-tools | 903.6 | 773.9 | 1677.5 | 17.0 | 910 | 160.8 | 177.8 | 1677 (989-3202) | non-interactive | non-interactive | 27 |
| gemini-3-1-pro-preview | 1019.0 | 1131.4 | 2150.4 | 18.3 | 963 | 216.8 | 235.1 | 2150 (1245-4205) | non-interactive | non-interactive | 27 |
| gemini-3-7-flash | 172.0 | 273.7 | 445.7 | 19.8 | 1187 | 100.5 | 120.2 | 446 (251-1024) | non-interactive | non-interactive | 20 |
| gemini-3-8-flash | 338.9 | 749.5 | 1088.4 | 21.4 | 1317 | 171.1 | 192.6 | 1088 (600-2367) | non-interactive | non-interactive | 22 |
| glm-5-3-flash | 522.7 | 471.7 | 994.3 | 15.7 | 611 | 91.4 | 107.1 | 994 (584-1901) | non-interactive | non-interactive | 27 |
| glm-5-3 | 735.2 | 949.3 | 1684.6 | 23.5 | 1496 | 209.2 | 232.7 | 1685 (965-3417) | non-interactive | non-interactive | 28 |
| glm-5v-turbo | 505.7 | 425.3 | 931.0 | 13.7 | 570 | 87.8 | 101.5 | 931 (549-1775) | non-interactive | non-interactive | 26 |
| gpt-5-2-pro | 232.6 | 330.6 | 563.2 | 13.6 | 376 | 62.2 | 75.7 | 563 (320-1141) | non-interactive | non-interactive | 28 |
| gpt-5-6-luna-pro | 154.3 | 188.0 | 342.3 | 12.3 | 408 | 44.9 | 57.2 | 342 (197-705) | non-interactive | non-interactive | 24 |
| gpt-5-6-sol-pro | 230.5 | 231.9 | 462.4 | 15.3 | 531 | 56.3 | 71.6 | 462 (270-929) | non-interactive | non-interactive | 32 |
| gpt-5-6-sol | 111.5 | 215.3 | 326.8 | 13.0 | 504 | 51.1 | 64.1 | 327 (182-711) | non-interactive | non-interactive | 24 |
| gpt-5-6-terra-pro | 176.2 | 184.7 | 360.8 | 12.8 | 450 | 48.4 | 61.2 | 361 (210-738) | non-interactive | non-interactive | 20 |
| gpt-6-astra | 529.0 | 833.8 | 1362.8 | 36.1 | 2461 | 239.2 | 275.3 | 1363 (769-2960) | non-interactive | non-interactive | 25 |
| grok-4-5 | 215.4 | 436.4 | 651.7 | 17.9 | 824 | 100.6 | 118.5 | 652 (361-1412) | non-interactive | non-interactive | 19 |
| kimi-k2-6 | 400.2 | 454.6 | 854.8 | 13.6 | 519 | 90.8 | 104.5 | 855 (494-1691) | non-interactive | non-interactive | 26 |
| kimi-k3 | 188.4 | 236.1 | 424.5 | 13.0 | 451 | 54.2 | 67.2 | 424 (243-870) | non-interactive | non-interactive | 28 |
| muse-spark-1-3-contributor | 259.5 | 372.7 | 632.2 | 13.2 | 534 | 76.7 | 90.0 | 632 (359-1293) | non-interactive | non-interactive | 20 |
| muse-spark-1-3 | 273.4 | 367.6 | 641.0 | 14.3 | 657 | 86.5 | 100.9 | 641 (366-1325) | non-interactive | non-interactive | 20 |
| nex-n2-pro | 264.9 | 434.2 | 699.1 | 18.8 | 812 | 89.5 | 108.3 | 699 (393-1454) | non-interactive | non-interactive | 37 |
| ox-alpha | 633.5 | 573.3 | 1206.9 | 16.3 | 775 | 113.1 | 129.4 | 1207 (694-2309) | non-interactive | non-interactive | 28 |
| qwen3-8-2-4t-a95b | 2027.4 | 1611.1 | 3638.5 | 34.7 | 1760 | 321.0 | 355.7 | 3639 (2108-6842) | non-interactive | non-interactive | 41 |
| qwen3-8-27b | 747.2 | 691.1 | 1438.3 | 19.1 | 914 | 138.5 | 157.7 | 1438 (844-2764) | non-interactive | non-interactive | 29 |
| qwen3-8-flash | 1338.2 | 907.7 | 2245.9 | 24.2 | 1200 | 185.8 | 210.1 | 2246 (1314-4147) | non-interactive | non-interactive | 39 |
| qwen3-8-max | 739.8 | 681.7 | 1421.5 | 19.4 | 811 | 133.9 | 153.2 | 1422 (816-2726) | non-interactive | non-interactive | 35 |

## icons @ 1080p

| file | GPU frag ms | GPU tile ms | GPU ms | CPU record ms | draw calls | CPU GL ms | CPU ms | frame ms (range) | verdict | pessimistic | GPU mem MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| google-workspace-48px | 159.8 | 136.7 | 296.4 | 4.5 | 25 | 3.9 | 8.4 | 296 (175-515) | non-interactive | non-interactive | 90 |
| clipdemo | 26.2 | 8.3 | 34.5 | 1.8 | 25 | 1.5 | 3.3 | 34 (25-57) | 10-30 fps | 10-30 fps | 24 |
| kit | 38.4 | 106.6 | 145.0 | 4.6 | 29 | 3.1 | 7.7 | 145 (81-279) | non-interactive | non-interactive | 58 |
| splash-logo | 8.4 | 8.3 | 16.7 | 3.2 | 39 | 2.3 | 5.5 | 17 (10-37) | 30 fps | 10-30 fps | 24 |
| mr-settodefault | 40.2 | 50.9 | 91.2 | 11.4 | 139 | 8.9 | 20.3 | 91 (54-191) | 10-30 fps | non-interactive | 33 |
| fox-with-box-on-cloud | 24.1 | 8.3 | 32.4 | 10.7 | 183 | 11.0 | 21.7 | 32 (23-85) | 30 fps | 10-30 fps | 24 |
| duckduckgo-com_2x | 16.1 | 29.6 | 45.7 | 4.1 | 38 | 2.6 | 6.7 | 46 (26-92) | 10-30 fps | 10-30 fps | 33 |
| Ghostscript_Tiger | 25.2 | 8.3 | 33.5 | 29.5 | 873 | 52.4 | 81.9 | 82 (46-194) | 10-30 fps | non-interactive | 25 |

## busey @ 1080p

| file | GPU frag ms | GPU tile ms | GPU ms | CPU record ms | draw calls | CPU GL ms | CPU ms | frame ms (range) | verdict | pessimistic | GPU mem MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-fable-5-1 | 9289.4 | 6319.6 | 15609.0 | 28.2 | 1336 | 208.4 | 236.6 | 15609 (9123-26385) | non-interactive | non-interactive | 139 |
| claude-opus-5 | 7979.3 | 4352.6 | 12332.0 | 24.7 | 1013 | 154.1 | 178.8 | 12332 (7293-20460) | non-interactive | non-interactive | 126 |
| fugu-ultra | 1722.5 | 2983.4 | 4705.9 | 21.8 | 796 | 104.6 | 126.4 | 4706 (2635-8674) | non-interactive | non-interactive | 152 |
| gemini-3-1-pro-preview-custom-tools | 5421.5 | 4529.3 | 9950.9 | 20.7 | 910 | 160.8 | 181.5 | 9951 (5876-17173) | non-interactive | non-interactive | 147 |
| gemini-3-1-pro-preview | 6960.5 | 6376.6 | 13337.1 | 19.0 | 963 | 216.8 | 235.8 | 13337 (7827-23186) | non-interactive | non-interactive | 102 |
| gemini-3-7-flash | 1094.4 | 1606.8 | 2701.2 | 21.2 | 1188 | 100.5 | 121.7 | 2701 (1530-5012) | non-interactive | non-interactive | 74 |
| gemini-3-8-flash | 2350.9 | 4336.7 | 6687.6 | 22.6 | 1318 | 171.2 | 193.8 | 6688 (3729-12424) | non-interactive | non-interactive | 92 |
| glm-5-3-flash | 3080.9 | 2747.8 | 5828.7 | 16.8 | 611 | 91.4 | 108.2 | 5829 (3427-10111) | non-interactive | non-interactive | 104 |
| glm-5-3 | 5546.3 | 5751.8 | 11298.2 | 26.2 | 1496 | 209.2 | 235.4 | 11298 (6575-19899) | non-interactive | non-interactive | 126 |
| glm-5v-turbo | 3419.4 | 2511.7 | 5931.1 | 14.5 | 570 | 87.8 | 102.3 | 5931 (3533-10114) | non-interactive | non-interactive | 112 |
| gpt-5-2-pro | 1931.0 | 1835.6 | 3766.6 | 15.4 | 376 | 62.2 | 77.6 | 3767 (2203-6581) | non-interactive | non-interactive | 176 |
| gpt-5-6-luna-pro | 919.2 | 1129.6 | 2048.8 | 12.3 | 408 | 44.9 | 57.2 | 2049 (1177-3681) | non-interactive | non-interactive | 107 |
| gpt-5-6-sol-pro | 1477.2 | 1245.4 | 2722.6 | 14.8 | 532 | 56.4 | 71.2 | 2723 (1607-4737) | non-interactive | non-interactive | 118 |
| gpt-5-6-sol | 647.0 | 1300.4 | 1947.4 | 14.1 | 504 | 51.1 | 65.2 | 1947 (1081-3648) | non-interactive | non-interactive | 107 |
| gpt-5-6-terra-pro | 1190.7 | 1116.4 | 2307.1 | 12.6 | 451 | 48.5 | 61.1 | 2307 (1351-4051) | non-interactive | non-interactive | 74 |
| gpt-6-astra | 3885.6 | 5072.6 | 8958.2 | 39.7 | 2461 | 239.2 | 278.9 | 8958 (5128-16239) | non-interactive | non-interactive | 108 |
| grok-4-5 | 1557.2 | 2645.6 | 4202.8 | 18.8 | 826 | 100.7 | 119.5 | 4203 (2357-7752) | non-interactive | non-interactive | 112 |
| kimi-k2-6 | 2986.5 | 2728.6 | 5715.2 | 14.2 | 519 | 90.8 | 105.0 | 5715 (3353-9936) | non-interactive | non-interactive | 102 |
| kimi-k3 | 1246.9 | 1087.5 | 2334.4 | 14.2 | 451 | 54.2 | 68.4 | 2334 (1373-4088) | non-interactive | non-interactive | 111 |
| muse-spark-1-3-contributor | 1926.8 | 2259.9 | 4186.7 | 14.9 | 534 | 76.7 | 91.6 | 4187 (2414-7452) | non-interactive | non-interactive | 73 |
| muse-spark-1-3 | 2269.7 | 2245.4 | 4515.1 | 14.4 | 659 | 86.6 | 101.1 | 4515 (2635-7934) | non-interactive | non-interactive | 73 |
| nex-n2-pro | 1330.8 | 2414.8 | 3745.6 | 20.0 | 814 | 89.6 | 109.7 | 3746 (2091-6942) | non-interactive | non-interactive | 154 |
| ox-alpha | 4629.3 | 3455.3 | 8084.5 | 18.7 | 777 | 113.2 | 132.0 | 8085 (4696-13789) | non-interactive | non-interactive | 121 |
| qwen3-8-2-4t-a95b | 13029.4 | 7015.2 | 20044.6 | 32.6 | 1756 | 320.8 | 353.4 | 20045 (11862-33369) | non-interactive | non-interactive | 189 |
| qwen3-8-27b | 5195.2 | 4144.3 | 9339.5 | 20.4 | 915 | 138.6 | 159.0 | 9339 (5542-16024) | non-interactive | non-interactive | 118 |
| qwen3-8-flash | 9022.3 | 5358.9 | 14381.2 | 27.5 | 1200 | 185.8 | 213.4 | 14381 (8471-24029) | non-interactive | non-interactive | 175 |
| qwen3-8-max | 5618.9 | 4028.6 | 9647.5 | 21.0 | 811 | 133.9 | 154.9 | 9648 (5620-16394) | non-interactive | non-interactive | 169 |

## Summary

- icons @ 640x480: median frame 19 ms (central, overlapped); verdicts: {'10-30 fps': 2, '60 fps': 3, '30 fps': 3}
- busey @ 640x480: median frame 931 ms (central, overlapped); verdicts: {'non-interactive': 27}
- icons @ 1080p: median frame 64 ms (central, overlapped); verdicts: {'non-interactive': 2, '10-30 fps': 4, '30 fps': 2}
- busey @ 1080p: median frame 5829 ms (central, overlapped); verdicts: {'non-interactive': 27}
