"""Renders every matrix row once (FRAMES=1) with two binaries and reports whether the renders
are bit-identical (cmp); a differing pair gets compare.py-style numbers.
Usage: identity.py --a fixed=/path --b orig=/path [--framings 640x480 1080p] [--sets busey icons]
"""
import argparse, glob, os, subprocess, sys
import numpy as np
from PIL import Image

S = os.environ.get("S", "/private/tmp/claude-501/-Users-matt-src-femtovg/e8e3f9a7-e26b-426f-ad20-5815dcc2470f/scratchpad")
ap = argparse.ArgumentParser()
ap.add_argument("--a", required=True)
ap.add_argument("--b", required=True)
ap.add_argument("--framings", nargs="+", default=["640x480", "1080p"])
ap.add_argument("--sets", nargs="+", default=["busey", "icons"])
args = ap.parse_args()
ta, pa = args.a.split("=", 1)
tb, pb = args.b.split("=", 1)

framings = {
    "640x480": {"FRAME_W": "640", "FRAME_H": "480", "BOX": "480", "BOX_X": "80", "BOX_Y": "0"},
    "1080p": {"FRAME_W": "1920", "FRAME_H": "1080", "BOX": "1080", "BOX_X": "420", "BOX_Y": "0"},
}
common = {"SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1", "FRAMES": "1"}
busey = sorted(glob.glob("/private/tmp/wt-da/corpus/buseybench/*.svg"))
icon_dirs = ["/private/tmp/wt-da", "/private/tmp/wt-all3/examples/assets"]
icon_names = ["google-workspace-48px.svg", "clipdemo.svg", "kit.svg", "splash-logo.svg", "mr-settodefault.svg",
              "fox-with-box-on-cloud.svg", "duckduckgo-com_2x.svg", "Ghostscript_Tiger.svg"]
icons = [next(os.path.join(d, n) for d in icon_dirs if os.path.exists(os.path.join(d, n))) for n in icon_names]
sets = {"busey": busey, "icons": icons}
OUT = f"{S}/cost/out/identity"
os.makedirs(OUT, exist_ok=True)

identical = differing = 0
for setname in args.sets:
    for framing in args.framings:
        for svg in sets[setname]:
            name = os.path.basename(svg)[:-4]
            env = {**os.environ, **framings[framing], **common}
            outs = {}
            for tag, b in ((ta, pa), (tb, pb)):
                ppm = f"{OUT}/{name}_{framing}_{tag}.ppm"
                subprocess.run([b, "1.0", ppm, svg], env=env, capture_output=True, text=True, check=True)
                outs[tag] = ppm
            same = subprocess.run(["cmp", "-s", outs[ta], outs[tb]]).returncode == 0
            if same:
                identical += 1
                print(f"{setname}@{framing:8s} {name:38s} identical", flush=True)
            else:
                differing += 1
                a = np.asarray(Image.open(outs[ta]).convert("RGB"), dtype=int)
                b = np.asarray(Image.open(outs[tb]).convert("RGB"), dtype=int)
                d = np.abs(a - b).max(axis=2)
                ys, xs = np.nonzero(d)
                print(f"{setname}@{framing:8s} {name:38s} DIFFER: {int((d > 0).sum())} px, max {int(d.max())}, "
                      f"px>20 {100 * (d > 20).mean():.3f} %, bbox ({xs.min()},{ys.min()})-({xs.max()},{ys.max()})", flush=True)
            for p in outs.values():
                os.remove(p)
print(f"identical {identical}, differing {differing}")
