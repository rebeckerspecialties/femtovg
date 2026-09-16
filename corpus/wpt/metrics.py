#!/usr/bin/env python3
"""Per-case metrics for the WPT css-masking renders.

For each case and zoom: femtovg vs Chromium(test), femtovg vs Chromium(ref),
Chromium(test) vs Chromium(ref) (does the browser itself pass the reftest in
this framing), Chromium vs Firefox on the test at 1x (the browser envelope),
and femtovg vs Firefox(test) at 1x.

Numbers per pair, computed over the SVG box only (box mapped through the
pivot zoom, so a padded frame does not dilute the percentages) and over the
full frame: px>20 (compare.py's metric), structural after 2-px erosion,
max channel delta, and the exact count of pixels that differ in any channel.
Writes strips/<case>_<zoom>.png: femtovg | chromium test | chromium ref |
firefox test | diff overlay (femtovg vs chromium test).
"""
import json, os, sys
import numpy as np
from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
man = json.load(open(f"{W}/manifest.json"))
os.makedirs(f"{W}/strips", exist_ok=True)


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=int)


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def box_slice(m, z):
    cx, cy = m["frame_w"] / 2, m["frame_h"] / 2
    x0 = cx + z * (m["box_x"] - cx); y0 = cy + z * (m["box_y"] - cy)
    x1 = x0 + z * m["svg_w"]; y1 = y0 + z * m["svg_h"]  # SVG's own extent inside the box
    clampx = lambda v: int(round(min(max(v, 0), m["frame_w"])))
    clampy = lambda v: int(round(min(max(v, 0), m["frame_h"])))
    return slice(clampy(y0), clampy(y1)), slice(clampx(x0), clampx(x1))


def cmp(a, c, sl, thr=20):
    h, w = min(a.shape[0], c.shape[0]), min(a.shape[1], c.shape[1])
    a, c = a[:h, :w], c[:h, :w]
    d = np.abs(a - c)
    dm = d.max(axis=2)
    over = dm > thr
    exact = dm > 0
    ys, xs = sl
    ob = over[ys, xs]
    r = {
        "box_px": int(ob.size),
        "box_over20": int(ob.sum()), "box_over20_pct": 100 * ob.mean(),
        "box_struct_pct": 100 * erode(over)[ys, xs].mean(),
        "box_exact": int(exact[ys, xs].sum()), "box_exact_pct": 100 * exact[ys, xs].mean(),
        "frame_over20_pct": 100 * over.mean(), "frame_struct_pct": 100 * erode(over).mean(),
        "frame_exact": int(exact.sum()),
        "max": int(dm.max()),
    }
    return r, over


rows = []
sel = sys.argv[1:] or list(man)
for name in sel:
    m = man[name]
    for z in ("1.0", "2.0"):
        fv = load(f"{W}/out/fvg_{name}_{z}.ppm")
        ct = load(f"{W}/out/chr_{name}_test_{z}.png")
        cr = load(f"{W}/out/chr_{name}_ref_{z}.png")
        sl = box_slice(m, float(z))
        row = {"case": name, "zoom": z, "box_slice": [sl[0].start, sl[0].stop, sl[1].start, sl[1].stop]}
        row["fvg_vs_chr_test"], over = cmp(fv, ct, sl)
        row["fvg_vs_chr_ref"], _ = cmp(fv, cr, sl)
        row["chr_test_vs_chr_ref"], _ = cmp(ct, cr, sl)
        panels = [fv, ct, cr]
        if z == "1.0":
            ft = load(f"{W}/out/ff_{name}_test_{z}.png")
            fr = load(f"{W}/out/ff_{name}_ref_{z}.png")
            row["chr_test_vs_ff_test"], _ = cmp(ct, ft, sl)
            row["fvg_vs_ff_test"], _ = cmp(fv, ft, sl)
            row["ff_test_vs_ff_ref"], _ = cmp(ft, fr, sl)
            panels.append(ft)
        o = fv.copy(); o[over[: o.shape[0], : o.shape[1]]] = [255, 0, 0]
        panels.append(o)
        h = min(p.shape[0] for p in panels); w = min(p.shape[1] for p in panels)
        strip = np.concatenate([p[:h, :w] for p in panels], axis=1).astype(np.uint8)
        Image.fromarray(strip).save(f"{W}/strips/{name}_{z}.png")
        rows.append(row)
        t, r, tr = row["fvg_vs_chr_test"], row["fvg_vs_chr_ref"], row["chr_test_vs_chr_ref"]
        line = (f"{name:46s} {z}  vs chr-test {t['box_over20_pct']:6.2f}% s{t['box_struct_pct']:6.3f}% max{t['max']:3d} exact{t['box_exact']:7d}"
                f" | vs chr-ref {r['box_over20_pct']:6.2f}% s{r['box_struct_pct']:6.3f}% max{r['max']:3d}"
                f" | chr test-vs-ref {tr['box_over20_pct']:5.2f}% max{tr['max']:3d}")
        if z == "1.0":
            e = row["chr_test_vs_ff_test"]; f = row["fvg_vs_ff_test"]
            line += f" | chr-vs-ff {e['box_over20_pct']:5.2f}% s{e['box_struct_pct']:5.3f}% | fvg-vs-ff {f['box_over20_pct']:6.2f}% s{f['box_struct_pct']:6.3f}%"
        print(line)

json.dump(rows, open(f"{W}/metrics.json", "w"), indent=1)
