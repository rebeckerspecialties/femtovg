"""1080p transient-budget ladder on the full-stack harness binaries: renders every listed SVG
at each budget with each binary (FRAMES=1, LAYER_STATS=1), then measures each render against
(1) the same binary's 256 MiB render (exact differing pixels, px>20 %, max delta),
(2) the other binary's render at the same budget (exact), and
(3) the Chromium 131 reference at the same framing (frame and box px>20 %, structural after a
2-px erosion, max), with compare.py / boxstats.py semantics reimplemented in numpy.

Usage: ladder.py --bins fixed=/path orig=/path --budgets 256 48 32 --files f1.svg ... --refs DIR
       [--keep]
Refs are DIR/chr_<name>_1.0.png.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np
from PIL import Image

S = os.environ.get("S", "/private/tmp/claude-501/-Users-matt-src-femtovg/e8e3f9a7-e26b-426f-ad20-5815dcc2470f/scratchpad")
ap = argparse.ArgumentParser()
ap.add_argument("--bins", nargs="+", required=True)
ap.add_argument("--budgets", nargs="+", type=int, default=[256, 48, 32])
ap.add_argument("--files", nargs="+", required=True)
ap.add_argument("--refs", default=f"{S}/ladder/refs")
ap.add_argument("--out", default=f"{S}/cost/ladder")
ap.add_argument("--keep", action="store_true")
ap.add_argument("--env", nargs="*", default=[])
args = ap.parse_args()

bins = dict(b.split("=", 1) for b in args.bins)
env_base = {**os.environ, "FRAME_W": "1920", "FRAME_H": "1080", "BOX": "1080", "BOX_X": "420", "BOX_Y": "0",
            "SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1", "LAYER_STATS": "1", "FRAMES": "1"}
for kv in args.env:
    k, v = kv.split("=", 1)
    env_base[k] = v
BX, BY, BS = 420, 0, 1080

stat_re = {
    "layers": re.compile(r"^layers begun: (\d+)"),
    "transient_at_flush": re.compile(r"^transient bytes held at flush: (\d+)"),
    "pass_through": re.compile(r"^layers passed through: (\d+)"),
}


def render(tag, svg, mb):
    name = os.path.basename(svg)[:-4]
    d = f"{args.out}/{tag}"
    os.makedirs(d, exist_ok=True)
    ppm = f"{d}/{name}_{mb}.ppm"
    env = dict(env_base)
    if mb != 256:
        env["TRANSIENT_BUDGET_MB"] = str(mb)
    r = subprocess.run([bins[tag], "1.0", ppm, svg], env=env, capture_output=True, text=True)
    rec = {"exit": r.returncode}
    for line in r.stderr.splitlines():
        for k, rx in stat_re.items():
            m = rx.match(line)
            if m:
                rec[k] = int(m.group(1))
    if r.returncode != 0 or "layers" not in rec:
        print("FAILED", tag, svg, mb, r.stderr[-800:], file=sys.stderr)
    rec["ppm"] = ppm
    return rec


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=int)


def erode(m, it=2):
    for _ in range(it):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m


def vs(a, b):
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    d = np.abs(a[:h, :w] - b[:h, :w]).max(axis=2)
    m = d > 20
    e = erode(m)
    box = (slice(BY, BY + BS), slice(BX, BX + BS))
    return {
        "exact_px": int((d > 0).sum()), "frame_pct20": 100 * m.mean(), "frame_struct": 100 * e.mean(),
        "box_pct20": 100 * m[box].mean(), "box_struct": 100 * e[box].mean(), "max": int(d.max()),
    }


results = {}
images = {}
for svg in args.files:
    name = os.path.basename(svg)[:-4]
    for tag in bins:
        for mb in args.budgets:
            rec = render(tag, svg, mb)
            results[(name, tag, mb)] = rec
            print(f"{tag:6s} {mb:4d} {name:36s} layers {rec.get('layers')} pt {rec.get('pass_through')} "
                  f"held {rec.get('transient_at_flush', 0)/2**20:6.2f} MiB", flush=True)
    ref_path = f"{args.refs}/chr_{name}_1.0.png"
    ref = load(ref_path) if os.path.exists(ref_path) else None
    imgs = {(tag, mb): load(results[(name, tag, mb)]["ppm"]) for tag in bins for mb in args.budgets
            if os.path.exists(results[(name, tag, mb)]["ppm"])}
    for (tag, mb), img in imgs.items():
        rec = results[(name, tag, mb)]
        if (tag, 256) in imgs and mb != 256:
            rec["vs_256"] = vs(img, imgs[(tag, 256)])
        other = [t for t in bins if t != tag]
        if other and (other[0], mb) in imgs:
            rec["vs_other"] = {"tag": other[0], **vs(img, imgs[(other[0], mb)])}
        if ref is not None:
            rec["vs_chromium"] = vs(img, ref)
        else:
            rec["vs_chromium"] = None
    if not args.keep:
        for (tag, mb) in imgs:
            os.remove(results[(name, tag, mb)]["ppm"])

out = [{"file": k[0], "bin": k[1], "budget_mb": k[2], **v} for k, v in results.items()]
json.dump(out, open(f"{args.out}.json", "w"), indent=1)
print("wrote", f"{args.out}.json")
