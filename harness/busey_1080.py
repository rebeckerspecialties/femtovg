"""Every corpus file at 1080p: browser refs, femtovg with the default and a lifted transient budget, layer logs."""
import json, os, re, subprocess, sys, glob
S = os.environ["S"]; B = os.environ["BIN"]; CHR = os.environ["CHR"]; FF = os.environ["FF"]; H = f"{S}/harness"; O = f"{S}/b1080"
frame = {"FRAME_W": "1920", "FRAME_H": "1080", "BOX": "1080", "BOX_X": "420", "BOX_Y": "0"}
base = {**os.environ, **frame, "SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1"}
pat = re.compile(r"px>20 [\d.]+% frame / ([\d.]+)% box \| structural [\d.]+% frame / ([\d.]+)% box \| mean\|d\| box ([\d.]+)")
def stats(a, b):
    out = subprocess.run([sys.executable, f"{H}/boxstats.py", a, b], env={**os.environ, "BOXRECT": "420,0,1080"}, capture_output=True, text=True).stdout
    m = pat.search(out); return [float(m.group(1)), float(m.group(2)), float(m.group(3))]
prof = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
rows = {}
for svg in sorted(glob.glob(f"{S}/busey/*.svg")):
    n = os.path.basename(svg)[:-4]
    html = f"{O}/{n}.html"
    with open(html, "w") as fh:
        subprocess.run([sys.executable, f"{H}/make_ref.py", svg, "1.0"], env={**os.environ, **frame}, stdout=fh)
    subprocess.run([CHR, "--headless", "--disable-gpu", "--hide-scrollbars", f"--screenshot={O}/chr_{n}.png", "--window-size=1920,1080", "--default-background-color=FFFFFFFF", f"file://{html}"], capture_output=True)
    subprocess.run([FF, "--headless", "--profile", prof, "--window-size=1920,1080", "--screenshot", f"{O}/ff_{n}.png", f"file://{html}"], capture_output=True)
    r = subprocess.run([B, "1.0", f"{O}/def_{n}.ppm", svg], env={**base, "LAYER_LOG": "1"}, capture_output=True, text=True)
    open(f"{O}/{n}.layers", "w").write(r.stderr)
    subprocess.run([B, "1.0", f"{O}/lift_{n}.ppm", svg], env={**base, "TRANSIENT_BUDGET_MB": "4096"}, capture_output=True)
    sim = subprocess.run([sys.executable, f"{H}/poolsim.py", f"{O}/{n}.layers", "1080"], capture_output=True, text=True).stdout
    req = re.search(r"viewport-sized \(today\)\s+requested per frame\s+([\d.]+) MB \| peak live with a pool\s+([\d.]+) MB", sim)
    bb = re.search(r"bounding-box-sized\s+requested per frame\s+([\d.]+) MB \| peak live with a pool\s+([\d.]+) MB \| bytes moved per frame\s+([\d.]+) MB", sim)
    nl = re.search(r"layers (\d+) \((\d+) blurred", sim)
    rows[n] = {"layers": int(nl.group(1)), "blurred": int(nl.group(2)), "requested_mb": float(req.group(1)), "peak_pool_mb": float(req.group(2)),
               "bbox_requested_mb": float(bb.group(1)), "bbox_peak_pool_mb": float(bb.group(2)), "bbox_traffic_mb": float(bb.group(3)),
               "def_chr": stats(f"{O}/def_{n}.ppm", f"{O}/chr_{n}.png"), "lift_chr": stats(f"{O}/lift_{n}.ppm", f"{O}/chr_{n}.png"),
               "def_ff": stats(f"{O}/def_{n}.ppm", f"{O}/ff_{n}.png"), "lift_ff": stats(f"{O}/lift_{n}.ppm", f"{O}/ff_{n}.png"),
               "envelope": stats(f"{O}/ff_{n}.png", f"{O}/chr_{n}.png")}
    d = rows[n]
    print(f"{n:<40} layers {d['layers']:3d} req {d['requested_mb']:6.0f} MB | vs chr: default {d['def_chr'][0]:5.2f}%/{d['def_chr'][1]:5.2f}%  lifted {d['lift_chr'][0]:5.2f}%/{d['lift_chr'][1]:5.2f}% | vs ff lifted {d['lift_ff'][0]:5.2f}%/{d['lift_ff'][1]:5.2f}% | envelope {d['envelope'][0]:5.2f}%", flush=True)
json.dump(rows, open(f"{O}/busey_1080.json", "w"), indent=1)
