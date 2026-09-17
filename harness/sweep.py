#!/usr/bin/env python3
"""Regression sweep: master2 and stack2 against Chromium 131 (and Firefox at 1x).

  sweep.py --corpus NAME --out results.json --refs DIR [--frame W,H,BOX,BX,BY]
           [--zooms 1,2,4] [--firefox] [--keep-ppm] [--manifest wpt/manifest.json] svg...

Per file and zoom: ensure the Chromium reference chr_<name>_<zoom>.png exists in
--refs (make_ref.py + chrome-headless-shell), optionally ff_<name>_1.0.png; render
with each binary; compare (px>20 %, structural % after 2-px erosion, max delta,
exact count) over the full frame and over the SVG box; record the harness's
LAYER_STATS lines; diff master vs stack; delete the PPMs.
"""
import argparse, json, os, re, subprocess, sys, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

S = "/private/tmp/claude-501/-Users-matt-src-femtovg/e8e3f9a7-e26b-426f-ad20-5815dcc2470f/scratchpad"
BINS = {"master": f"{S}/bin/_logos_full_master2", "stack": f"{S}/bin/_logos_full_stack2"}
HARN = "/private/tmp/wt-da/harness"
CHR = os.path.expanduser("~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell")
FF = "/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox"

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--refs", required=True)
ap.add_argument("--frame", default="460,260,200,130,30")
ap.add_argument("--zooms", default="1")
ap.add_argument("--firefox", action="store_true")
ap.add_argument("--manifest", help="WPT manifest: per-file framing and reference")
ap.add_argument("--wptrefs", help="WPT chromium ref dir (chr_<name>_test_<z>.png)")
ap.add_argument("--keep-ppm", action="store_true")
ap.add_argument("--ppmdir", default=f"{S}/reg/out")
ap.add_argument("svgs", nargs="+")
args = ap.parse_args()
os.makedirs(args.refs, exist_ok=True)
os.makedirs(args.ppmdir, exist_ok=True)
man = json.load(open(args.manifest)) if args.manifest else None


def ztag(z):
    z = float(z)
    return f"{z:.1f}" if z == int(z) else f"{z:g}"


def framing(name):
    if man:
        m = man[name]
        return dict(FRAME_W=str(m["frame_w"]), FRAME_H=str(m["frame_h"]), BOX=str(m["box"]), BOX_X=str(m["box_x"]), BOX_Y=str(m["box_y"])), m
    w, h, b, bx, by = args.frame.split(",")
    return dict(FRAME_W=w, FRAME_H=h, BOX=b, BOX_X=bx, BOX_Y=by), None


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=int)


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def bbox(m):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def cmp(a, c, box=None, thr=20):
    h, w = min(a.shape[0], c.shape[0]), min(a.shape[1], c.shape[1])
    a, c = a[:h, :w], c[:h, :w]
    dm = np.abs(a - c).max(axis=2)
    over = dm > thr
    r = {"px": round(100 * over.mean(), 3), "struct": round(100 * erode(over).mean(), 4), "max": int(dm.max()),
         "exact": int((dm > 0).sum()), "bbox": bbox(erode(over))}
    if box is not None:
        ys, xs = box
        ob = over[ys, xs]
        r["box_px"] = round(100 * ob.mean(), 3)
        r["box_struct"] = round(100 * erode(over)[ys, xs].mean(), 4)
    return r


def box_slice(fr, z, svg_w, svg_h):
    W, H, B, BX, BY = (float(fr[k]) for k in ("FRAME_W", "FRAME_H", "BOX", "BOX_X", "BOX_Y"))
    cx, cy = W / 2, H / 2
    x0 = cx + z * (BX - cx); y0 = cy + z * (BY - cy)
    x1 = x0 + z * svg_w; y1 = y0 + z * svg_h
    cl = lambda v, m: int(round(min(max(v, 0), m)))
    return slice(cl(y0, H), cl(y1, H)), slice(cl(x0, W), cl(x1, W))


def svg_box_size(svg, fr):
    """The SVG's extent inside the box (xMinYMin meet): box * (w,h)/max(w,h)."""
    t = open(svg).read()
    m = re.search(r"<svg\b([^>]*)>", t)
    attrs = m.group(1)
    vb = re.search(r'viewBox="([^"]*)"', attrs)
    if vb:
        p = [float(v) for v in vb.group(1).replace(",", " ").split()]
        w, h = p[2], p[3]
    else:
        w = float(re.search(r'width="([\d.]+)', attrs).group(1)); h = float(re.search(r'height="([\d.]+)', attrs).group(1))
    B = float(fr["BOX"])
    s = B / max(w, h)
    return w * s, h * s


def chrome_ref(svg, z, fr, png):
    if os.path.exists(png):
        return
    html = png[:-4] + ".html"
    with open(html, "w") as f:
        subprocess.run([sys.executable, f"{HARN}/make_ref.py", svg, str(z)], stdout=f, check=True, env={**os.environ, **fr})
    subprocess.run([CHR, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--window-size={fr['FRAME_W']},{fr['FRAME_H']}", "--default-background-color=FFFFFFFF",
                    f"--screenshot={png}", f"file://{html}"], capture_output=True, check=True)


def firefox_ref(svg, z, fr, png):
    if os.path.exists(png):
        return
    html = png[:-4] + ".html"
    with open(html, "w") as f:
        subprocess.run([sys.executable, f"{HARN}/make_ref.py", svg, str(z)], stdout=f, check=True, env={**os.environ, **fr})
    prof = tempfile.mkdtemp()
    subprocess.run([FF, "--headless", "--no-remote", "--profile", prof, f"--window-size={fr['FRAME_W']},{fr['FRAME_H']}",
                    "--screenshot", png, f"file://{html}"], capture_output=True)
    shutil.rmtree(prof, ignore_errors=True)


STAT = re.compile(r"harness cfgs: clip=(\w+) turbulence=(\w+)|filters skipped \(SKIP_UNSUPPORTED_FILTERS\): (\d+)|feTurbulence chains not run \(no harness_turbulence\): (\d+)|clip paths drawn unclipped \(no harness_clip\): (\d+)|filter attributes with invalid references dropped \(Filter Effects 5\): (\d+)")


def render(binkey, svg, z, fr, ppm):
    env = {**os.environ, **fr, "SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1", "LAYER_STATS": "1"}
    r = subprocess.run([BINS[binkey], str(z), ppm, svg], env=env, capture_output=True, text=True)
    stats = {}
    for m in STAT.finditer(r.stderr + r.stdout):
        if m.group(1):
            stats["cfg"] = f"clip={m.group(1)} turbulence={m.group(2)}"
        elif m.group(3):
            stats["skipped"] = int(m.group(3))
        elif m.group(4):
            stats["turb_not_run"] = int(m.group(4))
        elif m.group(5):
            stats["unclipped"] = int(m.group(5))
        elif m.group(6):
            stats["invalid_dropped"] = int(m.group(6))
    if r.returncode:
        stats["error"] = r.stderr[-300:]
    return stats


results = {}
zooms = [float(z) for z in args.zooms.split(",")]
# references first, in parallel
jobs = []
for svg in args.svgs:
    name = os.path.basename(svg)[:-4]
    fr, m = framing(name)
    for z in zooms:
        png = os.path.join(args.refs, f"chr_{name}_{ztag(z)}.png")
        if args.wptrefs:
            src = os.path.join(args.wptrefs, f"chr_{name}_test_{ztag(z)}.png")
            if os.path.exists(src) and not os.path.exists(png):
                shutil.copy(src, png)
        jobs.append((chrome_ref, svg, z, fr, png))
        if args.firefox and z == 1.0:
            ffpng = os.path.join(args.refs, f"ff_{name}_1.0.png")
            if args.wptrefs:
                src = os.path.join(os.path.dirname(args.wptrefs), "firefox", f"ff_{name}_test_1.0.png")
                if os.path.exists(src) and not os.path.exists(ffpng):
                    shutil.copy(src, ffpng)
            jobs.append((firefox_ref, svg, z, fr, ffpng))
with ThreadPoolExecutor(4) as ex:
    list(ex.map(lambda j: j[0](*j[1:]), jobs))

for svg in args.svgs:
    name = os.path.basename(svg)[:-4]
    fr, m = framing(name)
    sw, sh = svg_box_size(svg, fr)
    results[name] = {}
    for z in zooms:
        zt = ztag(z)
        row = {"frame": fr}
        chr_png = os.path.join(args.refs, f"chr_{name}_{zt}.png")
        c = load(chr_png)
        box = box_slice(fr, z, sw, sh)
        imgs = {}
        for key in BINS:
            ppm = os.path.join(args.ppmdir, f"{key}_{args.corpus}_{name}_{zt}.ppm")
            stats = render(key, svg, z, fr, ppm)
            row[key + "_stats"] = stats
            if os.path.exists(ppm):
                a = load(ppm)
                imgs[key] = a
                row[key] = cmp(a, c, box)
                if not args.keep_ppm:
                    os.remove(ppm)
        if "master" in imgs and "stack" in imgs:
            row["master_vs_stack"] = cmp(imgs["master"], imgs["stack"], box)
        if args.firefox and z == 1.0:
            ffpng = os.path.join(args.refs, f"ff_{name}_1.0.png")
            if os.path.exists(ffpng):
                f = load(ffpng)
                row["chr_vs_ff"] = cmp(c, f, box)
                for key in imgs:
                    row[key + "_vs_ff"] = cmp(imgs[key], f, box)
        results[name][zt] = row
        ms = row.get("master", {}); ss = row.get("stack", {})
        print(f"{args.corpus:9} {name[:44]:44} {zt:4} master {ms.get('px', -1):6.2f}%/{ms.get('struct', -1):6.3f}%  stack {ss.get('px', -1):6.2f}%/{ss.get('struct', -1):6.3f}%"
              + (f"  chr-ff {row['chr_vs_ff']['px']:5.2f}%/{row['chr_vs_ff']['struct']:6.3f}%" if "chr_vs_ff" in row else "")
              + (f"  m-vs-s exact {row['master_vs_stack']['exact']}" if "master_vs_stack" in row else ""), flush=True)

json.dump(results, open(args.out, "w"), indent=1)
