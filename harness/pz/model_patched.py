"""Applies model_pi.py's Pi Zero model to a second measurement file (the tree with patches
01-05 applied) and writes a before/after table against the unpatched measurements."""
import json, os, statistics, sys
S = os.environ["S"]
PATCHED = sys.argv[1]
OUT = sys.argv[2]
src = open(f"{S}/pz/model_pi.py").read().split("rows = []")[0]
exec(src)  # defines meas (unpatched), A, model(), verdict(), gpu_mem_mb()
base = {(r["set"], r["framing"], r["file"]): r for r in meas}
pat = {(r["set"], r["framing"], r["file"]): r for r in json.load(open(PATCHED))}

def row(r):
    st = r["stats"]; c = model(r, 0); hi = model(r, 2)
    return dict(clipq=st["full_target_stencil_pixels"]/1e6, sw=st["pass_switches"], tile=(st["pass_store_pixels"]+st["pass_load_pixels"])/1e6,
                filt=st["filter_pixels"]/1e6, trans=st["transient_bytes"]/2**20, allocs=r["record_allocs"], reallocs=r["record_reallocs"],
                abytes=r["record_alloc_bytes"]/2**20, rec=r["femtovg_record_ms"], gpu=c["gpu_ms"], cpu=c["cpu_ms"], frame=c["frame_ms_best"],
                worst=hi["frame_ms_worst"], verdict=verdict(c["frame_ms_best"]), gpumem=gpu_mem_mb(r)["total_mb"])

lines = ["# Before/after all five patches (01 bounded clip quads, 02 lone-blur parity, 03 clip fans kept, 04 GL blur scratch cache [GL only, not measurable here], 05 sized command Vec)", "",
         "Measured on this Mac (release, median of frames 2-6) and modelled for the Pi Zero with model_pi.py's central assumptions. before -> after.", ""]
summary = {}
for framing in ["640x480", "1080p"]:
    for setname in ["icons", "busey"]:
        lines += [f"## {setname} @ {framing}", "",
                  "| file | clip quad Mpx | pass switches | tile st+ld Mpx | filter Mpx | transient MB | allocs | reallocs | alloc MB | record ms (Mac) | Pi GPU ms | Pi CPU ms | Pi frame ms | verdict | GPU mem MB |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        agg = {k: [0, 0] for k in ["clipq", "sw", "tile", "filt", "trans", "allocs", "reallocs", "abytes", "rec", "gpu", "cpu", "gpumem"]}
        frames = [[], []]
        for key in sorted(base):
            if key[0] != setname or key[1] != framing or key not in pat: continue
            b, p = row(base[key]), row(pat[key])
            for k in agg: agg[k][0] += b[k]; agg[k][1] += p[k]
            frames[0].append(b["frame"]); frames[1].append(p["frame"])
            f = lambda k, d=1: f"{b[k]:.{d}f} -> {p[k]:.{d}f}"
            lines.append(f"| {key[2]} | {f('clipq',2)} | {f('sw',0)} | {f('tile',0)} | {f('filt',1)} | {f('trans',1)} | {f('allocs',0)} | {f('reallocs',0)} | {f('abytes',2)} | {f('rec',3)} | {f('gpu',0)} | {f('cpu',1)} | {f('frame',0)} | {b['verdict']} -> {p['verdict']} | {f('gpumem',0)} |")
        med = (statistics.median(frames[0]), statistics.median(frames[1]))
        summary[(setname, framing)] = (agg, med)
        lines += ["", f"{setname} @ {framing}: median Pi frame ms {med[0]:.0f} -> {med[1]:.0f}; totals over the set: clip quad Mpx {agg['clipq'][0]:.1f} -> {agg['clipq'][1]:.1f}; pass switches {agg['sw'][0]:.0f} -> {agg['sw'][1]:.0f}; tile Mpx {agg['tile'][0]:.0f} -> {agg['tile'][1]:.0f}; filter Mpx {agg['filt'][0]:.0f} -> {agg['filt'][1]:.0f}; transient MB {agg['trans'][0]:.1f} -> {agg['trans'][1]:.1f}; allocs {agg['allocs'][0]:.0f} -> {agg['allocs'][1]:.0f}; reallocs {agg['reallocs'][0]:.0f} -> {agg['reallocs'][1]:.0f}; alloc MB {agg['abytes'][0]:.1f} -> {agg['abytes'][1]:.1f}; record ms {agg['rec'][0]:.2f} -> {agg['rec'][1]:.2f}; Pi GPU ms {agg['gpu'][0]:.0f} -> {agg['gpu'][1]:.0f}; Pi CPU ms {agg['cpu'][0]:.0f} -> {agg['cpu'][1]:.0f}; GPU mem MB {agg['gpumem'][0]:.0f} -> {agg['gpumem'][1]:.0f}", ""]
open(OUT, "w").write("\n".join(lines))
json.dump({f"{k[0]}@{k[1]}": {"totals_before_after": v[0], "median_pi_frame_ms_before_after": v[1]} for k, v in summary.items()}, open(OUT.replace(".md", ".json"), "w"), indent=1)
print("\n".join(l for l in lines if l.startswith("icons @") or l.startswith("busey @")))
