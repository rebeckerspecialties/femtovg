"""Joins the pre-review measurements (harness/pz/measurements.json, release build, instrumented
harness, 2026-09-13) with the two debug-build runs of today (fixed.json = wt-all3 7bbcb5e with the
#323 review fixes; orig.json = the same stack before them) and prints the per-row delta tables as
Markdown, plus the JSON rows for the orchestrator.
"""
import json, os, sys

S = os.environ.get("S", "/private/tmp/claude-501/-Users-matt-src-femtovg/e8e3f9a7-e26b-426f-ad20-5815dcc2470f/scratchpad")
pre = {(r["file"], r["framing"]): r for r in json.load(open("/private/tmp/wt-da/harness/pz/measurements.json"))}
fixed = {(r["file"], r["framing"]): r for r in json.load(open(f"{S}/cost/fixed.json"))}
orig = {(r["file"], r["framing"]): r for r in json.load(open(f"{S}/cost/orig.json"))}
MB = 2 ** 20


def pct(a, b):
    return 0.0 if b == 0 else 100.0 * (a - b) / b


rows = []
for key in pre:
    p, f, o = pre[key], fixed.get(key), orig.get(key)
    if not f or not o:
        print("missing", key, file=sys.stderr)
        continue
    rows.append({
        "file": key[0], "framing": key[1], "set": p["set"],
        "layers_pre": p["layers"], "layers_fixed": f["layers"], "layers_orig": o["layers"],
        "pt_pre": p["pass_through"], "pt_fixed": f["pass_through"], "pt_orig": o["pass_through"],
        "tr_pre": p["transient_at_flush"], "tr_fixed": f["transient_at_flush"], "tr_orig": o["transient_at_flush"],
        "rec_pre": p["femtovg_record_ms"], "enc_pre": p["encode_ms"], "gpu_pre": p["gpu_ms"],
        "wall_fixed": f["frame_real_ms"], "wall_orig": o["frame_real_ms"],
        "cpu_fixed": f["frame_cpu_ms"], "cpu_orig": o["frame_cpu_ms"],
        "wall_fixed_all": f["frame_real_ms_all"], "wall_orig_all": o["frame_real_ms_all"],
        "cpu_fixed_all": f["frame_cpu_ms_all"], "cpu_orig_all": o["frame_cpu_ms_all"],
        "rss_fixed": f["maxrss_N"], "rss_orig": o["maxrss_N"], "rss_pre": p["time_maxrss_bytes"],
    })

order = {"640x480": 0, "1080p": 1}
rows.sort(key=lambda r: (r["set"], order[r["framing"]], r["file"]))
json.dump(rows, open(f"{S}/cost/matrix_join.json", "w"), indent=1)

moved = []
lines = []
for r in rows:
    d_tr = r["tr_fixed"] - r["tr_pre"]
    d_pt = r["pt_fixed"] - r["pt_pre"]
    d_wall = pct(r["wall_fixed"], r["wall_orig"])
    d_cpu = pct(r["cpu_fixed"], r["cpu_orig"])
    flag = []
    if d_tr:
        flag.append("transient")
    if d_pt:
        flag.append("pass-through")
    if r["layers_fixed"] != r["layers_pre"]:
        flag.append("layers")
    if abs(d_wall) > 20:
        flag.append("wall>20%")
    if abs(d_cpu) > 20:
        flag.append("cpu>20%")
    if flag:
        moved.append((r, flag))
    lines.append(f"| {r['set']} | {r['framing']} | {r['file']} | {r['layers_pre']}/{r['layers_fixed']} | "
                 f"{r['pt_pre']}/{r['pt_fixed']} | {r['tr_pre']/MB:.2f} | {r['tr_fixed']/MB:.2f} | "
                 f"{d_tr/MB:+.2f} ({pct(r['tr_fixed'], r['tr_pre']):+.1f} %) | "
                 f"{r['rec_pre']:.3f} / {r['enc_pre']:.2f} / {r['gpu_pre']:.2f} | "
                 f"{r['wall_orig']:.1f} | {r['wall_fixed']:.1f} | {d_wall:+.1f} % | "
                 f"{r['cpu_orig']:.1f} | {r['cpu_fixed']:.1f} | {d_cpu:+.1f} % | {' '.join(flag)} |")

hdr = ("| set | framing | file | layers pre/fixed | pass-through pre/fixed | transient pre MiB | transient fixed MiB | "
       "delta | pre record / encode / gpu ms (release) | wall/frame orig ms | wall/frame fixed ms | delta | "
       "cpu/frame orig ms | cpu/frame fixed ms | delta | moved |")
sep = "|" + "---|" * 16
print(hdr)
print(sep)
print("\n".join(lines))

# Totals per framing
print()
for framing in ("640x480", "1080p"):
    sub = [r for r in rows if r["framing"] == framing]
    tp = sum(r["tr_pre"] for r in sub) / MB
    tf = sum(r["tr_fixed"] for r in sub) / MB
    to = sum(r["tr_orig"] for r in sub) / MB
    wo = sum(r["wall_orig"] for r in sub)
    wf = sum(r["wall_fixed"] for r in sub)
    co = sum(r["cpu_orig"] for r in sub)
    cf = sum(r["cpu_fixed"] for r in sub)
    ptp = sum(r["pt_pre"] for r in sub)
    ptf = sum(r["pt_fixed"] for r in sub)
    lp = sum(r["layers_pre"] for r in sub)
    lf = sum(r["layers_fixed"] for r in sub)
    print(f"TOTAL {framing}: rows {len(sub)}; layers {lp} -> {lf}; pass-through {ptp} -> {ptf}; "
          f"transient sum {tp:.2f} -> {tf:.2f} MiB (orig today {to:.2f}) [{pct(tf, tp):+.2f} %]; "
          f"wall/frame sum orig {wo:.1f} -> fixed {wf:.1f} ms [{pct(wf, wo):+.1f} %]; "
          f"cpu/frame sum orig {co:.1f} -> fixed {cf:.1f} ms [{pct(cf, co):+.1f} %]")
print()
print("moved rows:", len(moved))
for r, flag in moved:
    print(f"  {r['set']}@{r['framing']} {r['file']}: {' '.join(flag)}; transient {r['tr_pre']/MB:.2f} -> {r['tr_fixed']/MB:.2f} MiB "
          f"(orig today {r['tr_orig']/MB:.2f}); pt {r['pt_pre']} -> {r['pt_fixed']}; wall {r['wall_orig']:.1f} -> {r['wall_fixed']:.1f} ms "
          f"(all: {[round(x) for x in r['wall_orig_all']]} vs {[round(x) for x in r['wall_fixed_all']]}); "
          f"cpu {r['cpu_orig']:.1f} -> {r['cpu_fixed']:.1f} ms")

# Distribution of the timing deltas (debug build A/B): how many rows within +-20 %?
import statistics
dw = [pct(r["wall_fixed"], r["wall_orig"]) for r in rows]
dc = [pct(r["cpu_fixed"], r["cpu_orig"]) for r in rows]
print()
print(f"wall/frame fixed vs orig: median {statistics.median(dw):+.1f} %, min {min(dw):+.1f} %, max {max(dw):+.1f} %, "
      f"rows beyond +-20 %: {sum(1 for x in dw if abs(x) > 20)}")
print(f"cpu/frame fixed vs orig: median {statistics.median(dc):+.1f} %, min {min(dc):+.1f} %, max {max(dc):+.1f} %, "
      f"rows beyond +-20 %: {sum(1 for x in dc if abs(x) > 20)}")
