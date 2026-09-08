import json, os
S = os.environ["S"]; d = json.load(open(f"{S}/b1080/busey_1080.json"))
print(f"{'file':<38} {'layers':>6} {'blur':>4} {'req MB':>7} {'bbox MB':>7} {'pool pk':>7} | {'default':>13} | {'lifted':>13} | {'vs ff lifted':>13} | {'env':>5}")
over = []; helped = []
for n, r in sorted(d.items(), key=lambda kv: -kv[1]["def_chr"][1]):
    dc, lc, lf, env = r["def_chr"], r["lift_chr"], r["lift_ff"], r["envelope"]
    flag = "*" if r["requested_mb"] > 256 else " "
    print(f"{n:<38} {r['layers']:6d} {r['blurred']:4d} {r['requested_mb']:7.0f}{flag}{r['bbox_requested_mb']:7.0f} {r['peak_pool_mb']:7.1f} | {dc[0]:5.2f}%/{dc[1]:5.2f}% | {lc[0]:5.2f}%/{lc[1]:5.2f}% | {lf[0]:5.2f}%/{lf[1]:5.2f}% | {env[0]:4.2f}%")
    if r["requested_mb"] > 256: over.append(n)
    if dc[1] - lc[1] >= 0.05 or dc[0] - lc[0] >= 0.5: helped.append((n, dc, lc))
m = lambda k, i: sum(r[k][i] for r in d.values()) / len(d)
print(f"\nMEAN over 27 files, % of SVG box: default {m('def_chr',0):.2f}% / {m('def_chr',1):.3f}% structural; lifted {m('lift_chr',0):.2f}% / {m('lift_chr',1):.3f}%; vs Firefox lifted {m('lift_ff',0):.2f}% / {m('lift_ff',1):.3f}%; envelope {m('envelope',0):.3f}%")
print(f"files requesting more than the 256 MiB budget per frame (viewport-sized layers): {len(over)}/27: {', '.join(over)}")
print(f"files where lifting the budget changes the result (>=0.05 structural or >=0.5 px points): {len(helped)}")
for n, dc, lc in helped: print(f"  {n:<38} {dc[0]:5.2f}%/{dc[1]:5.2f}% -> {lc[0]:5.2f}%/{lc[1]:5.2f}%")
still = [(n, r) for n, r in d.items() if r["lift_chr"][1] > 0.05]
print(f"files still above 0.05% structural with the budget lifted: {len(still)}"); [print(f"  {n:<38} {r['lift_chr'][0]:5.2f}%/{r['lift_chr'][1]:5.2f}%  layers {r['layers']}") for n, r in sorted(still, key=lambda kv: -kv[1]['lift_chr'][1])]
print(f"\nbbox-sized + pool peak (MB) max over corpus: {max(r['bbox_peak_pool_mb'] for r in d.values()):.1f}; viewport-sized + pool peak max: {max(r['peak_pool_mb'] for r in d.values()):.1f}; bbox traffic max {max(r['bbox_traffic_mb'] for r in d.values()):.0f} MB/frame")
