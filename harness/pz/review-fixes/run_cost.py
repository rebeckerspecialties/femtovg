"""Runs a _logos_full harness binary over the 70-row matrix (27 BuseyBench + 8 icon files,
framings 640x480 and 1080p as in harness/pz/run_matrix.py) and collects what this binary prints
under LAYER_STATS=1 (layers begun, layers passed through, transient bytes held at flush - the
counters are cumulative over FRAMES, so per-frame values divide by FRAMES) plus /usr/bin/time -l
real/user/sys and peak RSS for a FRAMES=1 and a FRAMES=N run; per-frame steady-state cost is the
(N - 1)-frame delta between the two. Each configuration is run `repeats` times and the minimum
kept. The binary has no per-phase timers (record/encode/gpu), so wall - (user + sys) per frame is
the only GPU-wait proxy available; see RESULTS.md.

Usage: python3 run_cost.py --bin BIN --tag TAG [--frames 11] [--repeats 2] [--budget-mb N]
       [--only busey@640x480 ...] [--env KEY=VAL ...]
"""
import argparse, glob, json, os, re, subprocess, sys, time

S = os.environ.get("S", "/private/tmp/claude-501/-Users-matt-src-femtovg/e8e3f9a7-e26b-426f-ad20-5815dcc2470f/scratchpad")
ap = argparse.ArgumentParser()
ap.add_argument("--bin", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--frames", type=int, default=11)
ap.add_argument("--repeats", type=int, default=2)
ap.add_argument("--budget-mb", type=int, default=None)
ap.add_argument("--only", nargs="*", default=[])
ap.add_argument("--env", nargs="*", default=[])
ap.add_argument("--keep-ppm", action="store_true")
args = ap.parse_args()

OUT = os.path.join(S, "cost", "out", args.tag)
os.makedirs(OUT, exist_ok=True)

framings = {
    "640x480": {"FRAME_W": "640", "FRAME_H": "480", "BOX": "480", "BOX_X": "80", "BOX_Y": "0"},
    "1080p": {"FRAME_W": "1920", "FRAME_H": "1080", "BOX": "1080", "BOX_X": "420", "BOX_Y": "0"},
}
common = {"SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1", "LAYER_STATS": "1"}
if args.budget_mb is not None:
    common["TRANSIENT_BUDGET_MB"] = str(args.budget_mb)
for kv in args.env:
    k, v = kv.split("=", 1)
    common[k] = v

busey = sorted(glob.glob("/private/tmp/wt-da/corpus/buseybench/*.svg"))
icon_dirs = ["/private/tmp/wt-da", "/private/tmp/wt-all3/examples/assets"]
icon_names = ["google-workspace-48px.svg", "clipdemo.svg", "kit.svg", "splash-logo.svg", "mr-settodefault.svg",
              "fox-with-box-on-cloud.svg", "duckduckgo-com_2x.svg", "Ghostscript_Tiger.svg"]
icons = []
for n in icon_names:
    for d in icon_dirs:
        p = os.path.join(d, n)
        if os.path.exists(p):
            icons.append(p)
            break
    else:
        sys.exit(f"missing icon {n}")
sets = {"busey": busey, "icons": icons}

stat_re = {
    "layers": re.compile(r"^layers begun: (\d+)"),
    "transient_at_flush": re.compile(r"^transient bytes held at flush: (\d+)"),
    "pass_through": re.compile(r"^layers passed through: (\d+)"),
    "filters_skipped": re.compile(r"^filters skipped \(SKIP_UNSUPPORTED_FILTERS\): (\d+)"),
    "cfgs": re.compile(r"^harness cfgs: (.*)"),
}
time_re = re.compile(r"^\s*([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys")


def run_once(svg, framing, frames):
    env = {**os.environ, **framings[framing], **common, "FRAMES": str(frames)}
    name = os.path.basename(svg)[:-4]
    ppm = f"{OUT}/{name}_{framing}_f{frames}.ppm"
    t0 = time.perf_counter()
    r = subprocess.run(["/usr/bin/time", "-l", args.bin, "1.0", ppm, svg], env=env, capture_output=True, text=True)
    wall = time.perf_counter() - t0
    rec = {"frames": frames, "wall_py": wall, "exit": r.returncode}
    for line in r.stderr.splitlines():
        for k, rx in stat_re.items():
            m = rx.match(line)
            if m:
                rec[k] = m.group(1) if k == "cfgs" else int(m.group(1))
        m = time_re.match(line)
        if m:
            rec["real"], rec["user"], rec["sys"] = (float(x) for x in m.groups())
        if "maximum resident set size" in line:
            rec["maxrss"] = int(line.split()[0])
    if "layers" not in rec or r.returncode != 0:
        print("FAILED", svg, framing, frames, r.stderr[-1500:], file=sys.stderr)
        rec["failed"] = True
    if not args.keep_ppm:
        try:
            os.remove(ppm)
        except FileNotFoundError:
            pass
    return rec


def measure(svg, framing):
    name = os.path.basename(svg)[:-4]
    runs1, runsN = [], []
    for _ in range(args.repeats):
        runs1.append(run_once(svg, framing, 1))
        runsN.append(run_once(svg, framing, args.frames))
    ok1 = [r for r in runs1 if not r.get("failed")]
    okN = [r for r in runsN if not r.get("failed")]
    if not ok1 or not okN:
        return None
    n = args.frames
    # Per-frame deltas, paired per repeat, minimum over repeats.
    deltas = [{k: (b[k] - a[k]) / (n - 1) for k in ("real", "user", "sys")} for a, b in zip(ok1, okN)]
    best = min(range(len(deltas)), key=lambda i: deltas[i]["real"])
    rec = {
        "file": name, "framing": framing, "frames_n": n, "repeats": args.repeats,
        "layers": ok1[0]["layers"], "pass_through": ok1[0]["pass_through"],
        "transient_at_flush": ok1[0]["transient_at_flush"],
        "filters_skipped": ok1[0].get("filters_skipped"), "cfgs": ok1[0].get("cfgs"),
        # The FRAMES=N run's counters are cumulative; per-frame = /N. A mismatch with the FRAMES=1
        # run means state leaked across frames.
        "layers_per_frame_N": okN[0]["layers"] / n, "pass_through_per_frame_N": okN[0]["pass_through"] / n,
        "transient_at_flush_N": okN[0]["transient_at_flush"],
        "frame_real_ms": deltas[best]["real"] * 1e3, "frame_user_ms": deltas[best]["user"] * 1e3,
        "frame_sys_ms": deltas[best]["sys"] * 1e3,
        "frame_real_ms_all": [d["real"] * 1e3 for d in deltas],
        "frame_cpu_ms_all": [(d["user"] + d["sys"]) * 1e3 for d in deltas],
        "real_1_min": min(r["real"] for r in ok1), "real_N_min": min(r["real"] for r in okN),
        "user_1_min": min(r["user"] for r in ok1), "user_N_min": min(r["user"] for r in okN),
        "sys_1_min": min(r["sys"] for r in ok1), "sys_N_min": min(r["sys"] for r in okN),
        "maxrss_1": min(r["maxrss"] for r in ok1), "maxrss_N": min(r["maxrss"] for r in okN),
        "runs1": runs1, "runsN": runsN,
    }
    rec["frame_cpu_ms"] = rec["frame_user_ms"] + rec["frame_sys_ms"]
    rec["frame_gpu_wait_ms"] = rec["frame_real_ms"] - rec["frame_cpu_ms"]
    return rec


results = []
for setname, files in sets.items():
    for framing in framings:
        key = f"{setname}@{framing}"
        if args.only and key not in args.only:
            continue
        for svg in files:
            rec = measure(svg, framing)
            if rec:
                rec["set"] = setname
                results.append(rec)
                flag = "" if rec["layers_per_frame_N"] == rec["layers"] and rec["transient_at_flush_N"] == rec["transient_at_flush"] else "  <-- frame-N mismatch"
                print(f"{key:14} {rec['file']:38} layers {rec['layers']:4d} pt {rec['pass_through']:3d} "
                      f"transient {rec['transient_at_flush']/2**20:6.2f} MiB  frame real {rec['frame_real_ms']:7.1f} ms "
                      f"cpu {rec['frame_cpu_ms']:7.1f} ms gpu-wait {rec['frame_gpu_wait_ms']:7.1f} ms{flag}", flush=True)

path = os.path.join(S, "cost", f"{args.tag}.json")
json.dump(results, open(path, "w"), indent=1)
print("wrote", path)
