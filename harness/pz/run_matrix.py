"""Runs the instrumented harness over the corpus and framings, collecting PZ_* lines
and /usr/bin/time -l peak RSS into measurements.json."""
import json, os, re, subprocess, sys, glob, statistics
S = os.environ["S"]
BIN = os.environ.get("BIN", "/private/tmp/wt-pz/target/release/examples/_logos_full")
FRAMES = int(os.environ.get("FRAMES", "6"))
OUT = os.path.join(S, "pz", "out")
os.makedirs(OUT, exist_ok=True)

framings = {
    "640x480": {"FRAME_W": "640", "FRAME_H": "480", "BOX": "480", "BOX_X": "80", "BOX_Y": "0"},
    "1080p": {"FRAME_W": "1920", "FRAME_H": "1080", "BOX": "1080", "BOX_X": "420", "BOX_Y": "0"},
}
common = {"SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1", "PZ_STATS": "1", "FRAMES": str(FRAMES)}

busey = sorted(glob.glob(f"{S}/da/corpus/buseybench/*.svg"))
icons = [f"{S}/pz/assets/{n}" for n in [
    "google-workspace-48px.svg", "clipdemo.svg", "kit.svg", "splash-logo.svg", "mr-settodefault.svg",
    "fox-with-box-on-cloud.svg", "duckduckgo-com_2x.svg", "Ghostscript_Tiger.svg"]]

sets = {"busey": busey, "icons": icons}
only = sys.argv[1:]  # optional: subset of "busey@640x480" style keys

stats_re = re.compile(r"(\w+): ([\d.]+)")

def run(svg, framing):
    env = {**os.environ, **framings[framing], **common}
    name = os.path.basename(svg)[:-4]
    ppm = f"{OUT}/{name}_{framing}.ppm"
    r = subprocess.run(["/usr/bin/time", "-l", BIN, "1.0", ppm, svg], env=env, capture_output=True, text=True)
    frames, stats = [], []
    rss = {}
    maxrss = None
    for line in r.stderr.splitlines():
        if line.startswith("PZ_FRAME "):
            frames.append(json.loads(line[len("PZ_FRAME "):]))
        elif line.startswith("PZ_STATS "):
            body = line.split(" ", 2)[2]
            stats.append({k: float(v) for k, v in stats_re.findall(body)})
        elif line.startswith("PZ_RSS "):
            rss = json.loads(line[len("PZ_RSS "):])
        elif "maximum resident set size" in line:
            maxrss = int(line.split()[0])
    if not frames:
        print("FAILED", svg, framing, r.stderr[-2000:], file=sys.stderr)
        return None
    steady = frames[1:] if len(frames) > 1 else frames
    med = lambda k: statistics.median(f[k] for f in steady)
    rec = {
        "file": name, "framing": framing, "frames": len(frames),
        "record_ms": med("record_ms"), "femtovg_record_ms": med("femtovg_record_ms"), "path_build_ms": med("path_build_ms"),
        "encode_ms": med("encode_ms"), "gpu_ms": med("gpu_ms"),
        "record_ms_min": min(f["femtovg_record_ms"] for f in steady),
        "record_allocs": med("record_allocs"), "record_reallocs": med("record_reallocs"), "record_alloc_bytes": med("record_alloc_bytes"),
        "path_build_allocs": med("path_build_allocs"), "encode_allocs": med("encode_allocs"), "encode_alloc_bytes": med("encode_alloc_bytes"),
        "heap_live_after_frame": steady[-1]["heap_live_after_frame"], "heap_peak_record": med("heap_peak_record"),
        "heap_growth_per_frame": (frames[-1]["heap_live_after_frame"] - frames[1]["heap_live_after_frame"]) / max(1, len(frames) - 2) if len(frames) > 2 else 0,
        "layers": steady[-1]["layers"], "pass_through": steady[-1]["pass_through"], "transient_at_flush": steady[-1]["transient_at_flush"],
        "rss_first_kb": frames[0]["rss_kb"], "rss_frames_kb": [f["rss_kb"] for f in frames],
        "rss_after_device_kb": rss.get("rss_after_device_kb"), "rss_after_tree_kb": rss.get("rss_after_tree_kb"),
        "rss_end_kb": rss.get("rss_end_kb"), "time_maxrss_bytes": maxrss,
        "first_frame": frames[0],
        "stats": stats[-1] if stats else {},
    }
    return rec

results = []
for setname, files in sets.items():
    for framing in framings:
        key = f"{setname}@{framing}"
        if only and key not in only:
            continue
        for svg in files:
            rec = run(svg, framing)
            if rec:
                rec["set"] = setname
                results.append(rec)
                st = rec["stats"]
                print(f"{key:14} {rec['file']:38} cmds {int(st.get('commands',0)):5d} layers {int(rec['layers']):4d} "
                      f"rec {rec['femtovg_record_ms']:7.3f} ms enc {rec['encode_ms']:7.3f} gpu {rec['gpu_ms']:7.3f} "
                      f"allocs {int(rec['record_allocs']):6d} rss {rec['rss_end_kb']/1024:6.0f} MB", flush=True)

path = os.path.join(S, "pz", "measurements.json" if not only else f"measurements_{'_'.join(k.replace('@','-') for k in only)}.json")
json.dump(results, open(path, "w"), indent=1)
print("wrote", path)
