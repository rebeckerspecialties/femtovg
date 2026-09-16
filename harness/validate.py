#!/usr/bin/env python3
"""BuseyBench sweep: render every corpus file with a harness binary at the
playbook's zoom triple and compare each frame with its Chromium reference.

  validate.py --bin target/debug/examples/_logos_full --refs REFS [--out OUT]
              [--corpus DIR] [--files a,b,c] [--zooms 1,2,4] [--threshold 20]
              [--make-refs] [--json metrics.json]
  validate.py ... --single-zoom 1.0 [--gws google-workspace-48px.svg]

Framing is the playbook's: a 460x260 canvas, pivot zoom about (230,130), the
SVG fitted into a 200x200 box at (130,30) (FRAME_W/FRAME_H/BOX/BOX_X/BOX_Y
override it for both sides). References are `chr_<name>_<zoom>.png` in
--refs; --make-refs renders any that are missing with make_ref.py and
chrome-headless-shell. Output: one table with a column per zoom (percent of
pixels above the threshold / structural percent after 2 px erosion), the
per-zoom mean, and the files above 0.05 % structural at each zoom.

--single-zoom keeps the previous behaviour: one zoom (references also
accepted as `chr_<name>.png`), the old one-line summary, and the Google
Workspace icon ladder when --gws is given.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHR = os.path.expanduser(
    "~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell"
)
PAT = re.compile(r"px>(\d+): ([\d.]+)%\s+structural \(2px erosion\): ([\d.]+)%\s+max delta: (\d+)")
LADDER = [0.6, 0.75, 0.9, 1.0, 1.15, 1.3, 1.6, 1.9, 2.35]

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--bin", default=os.environ.get("BIN"), help="harness binary (_logos_full)")
ap.add_argument("--refs", default=os.environ.get("REFS"), help="directory of chr_<name>_<zoom>.png references")
ap.add_argument("--out", default=os.environ.get("OUT", "validate-out"), help="where the .ppm frames go")
ap.add_argument("--corpus", default=os.path.join(HERE, "..", "corpus", "buseybench"))
ap.add_argument("--files", help="comma-separated basenames (without .svg) to restrict the sweep")
ap.add_argument("--zooms", default="1,2,4", help="comma-separated zoom triple (default 1,2,4)")
ap.add_argument("--single-zoom", type=float, help="previous behaviour: one zoom, old summary line")
ap.add_argument("--threshold", type=int, default=20)
ap.add_argument("--make-refs", action="store_true", help="render missing Chromium references")
ap.add_argument("--gws", help="Google Workspace icon SVG for the zoom ladder (single-zoom mode only)")
ap.add_argument("--json", help="write the per-file, per-zoom numbers here")
args = ap.parse_args()
if not args.bin or not args.refs:
    sys.exit("need --bin (or BIN) and --refs (or REFS)")
os.makedirs(args.out, exist_ok=True)
env = {**os.environ, "SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1"}
frame_w = env.get("FRAME_W", "460")
frame_h = env.get("FRAME_H", "260")


def zoom_tag(z):
    return f"{float(z):g}" if float(z) != int(float(z)) else f"{float(z):.1f}"


def ref_path(name, z):
    p = os.path.join(args.refs, f"chr_{name}_{zoom_tag(z)}.png")
    if not os.path.exists(p) and args.single_zoom is not None:
        legacy = os.path.join(args.refs, f"chr_{name}.png")
        if os.path.exists(legacy):
            return legacy
    return p


def make_ref(svg, z, png):
    html = png[:-4] + ".html"
    with open(html, "w") as f:
        subprocess.run([sys.executable, os.path.join(HERE, "make_ref.py"), svg, str(z)], stdout=f, check=True, env=env)
    subprocess.run(
        [CHR, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
         f"--window-size={frame_w},{frame_h}", "--default-background-color=FFFFFFFF", f"--screenshot={png}", f"file://{html}"],
        capture_output=True, check=True,
    )


def run(svg, z, name):
    """Render one frame and compare it; returns (px%, structural%, max delta) or None."""
    ppm = os.path.join(args.out, f"{name}_{zoom_tag(z)}.ppm")
    r = subprocess.run([args.bin, str(z), ppm, svg], env=env, capture_output=True, text=True)
    if r.returncode:
        print("HARNESS FAILED", name, z, r.stderr[-300:])
        return None
    ref = ref_path(name, z)
    if not os.path.exists(ref):
        if not args.make_refs:
            print("MISSING REFERENCE", ref, "(pass --make-refs)")
            return None
        make_ref(svg, z, ref)
    c = subprocess.run(
        [sys.executable, os.path.join(HERE, "compare.py"), ppm, ref, "--threshold", str(args.threshold)],
        capture_output=True, text=True,
    ).stdout
    m = PAT.search(c)
    return (float(m.group(2)), float(m.group(3)), int(m.group(4)))


svgs = sorted(glob.glob(os.path.join(args.corpus, "*.svg")))
if args.files:
    keep = set(args.files.split(","))
    svgs = [s for s in svgs if os.path.basename(s)[:-4] in keep]
if not svgs:
    sys.exit(f"no corpus files under {args.corpus}")
zooms = [args.single_zoom] if args.single_zoom is not None else [float(z) for z in args.zooms.split(",")]
thr = args.threshold

results = {}
for svg in svgs:
    n = os.path.basename(svg)[:-4]
    results[n] = {zoom_tag(z): run(svg, z, n) for z in zooms}


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else float("nan")


if args.single_zoom is not None:
    z = zoom_tag(zooms[0])
    rows = [(n, r[z]) for n, r in results.items() if r[z] is not None]
    print(
        "BuseyBench vs Chromium 131 @%sx%s zoom %s: mean px>%d %.3f%%  mean structural %.3f%%  files>0.05%% structural: %s"
        % (frame_w, frame_h, z, thr, mean(r[0] for _, r in rows), mean(r[1] for _, r in rows),
           [(n, r[1]) for n, r in rows if r[1] > 0.05])
    )
    for n, r in rows:
        print(f"  {n:45} {r[0]:6.2f}% / {r[1]:6.3f}%")
    if args.gws:
        print("Google Workspace icon ladder:")
        for lz in LADDER:
            r = run(args.gws, lz, os.path.basename(args.gws)[:-4])
            if r:
                print(f"  {lz:<5} {r[0]:6.2f}% / {r[1]:6.3f}%")
else:
    tags = [zoom_tag(z) for z in zooms]
    head = f"{'file':45}" + "".join(f"{'zoom ' + t:>20}" for t in tags)
    print(f"BuseyBench vs Chromium 131 @{frame_w}x{frame_h}, px>{thr} % / structural % (2 px erosion)")
    print(head)
    for n, r in results.items():
        cells = "".join(f"{r[t][0]:9.2f}% /{r[t][1]:7.3f}%" if r[t] else f"{'n/a':>20}" for t in tags)
        print(f"{n:45}{cells}")
    means = "".join(
        f"{mean(r[t][0] for r in results.values() if r[t]):9.2f}% /{mean(r[t][1] for r in results.values() if r[t]):7.3f}%"
        for t in tags
    )
    print(f"{'mean (' + str(len(results)) + ' files)':45}{means}")
    for t in tags:
        over = [(n, r[t][1]) for n, r in results.items() if r[t] and r[t][1] > 0.05]
        print(f"  zoom {t}: files > 0.05% structural: {over}")

if args.json:
    with open(args.json, "w") as f:
        json.dump(
            {"threshold": thr, "frame": [frame_w, frame_h], "zooms": [zoom_tag(z) for z in zooms],
             "files": {n: {t: (list(v) if v else None) for t, v in r.items()} for n, r in results.items()}},
            f, indent=1,
        )
