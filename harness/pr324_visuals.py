#!/usr/bin/env python3
"""Regenerate PR #324 base/branch/browser comparison panels."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


W, H = 460, 260
ZOOMS = (0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.3, 1.5, 1.7, 2.1, 2.5)
HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, text=True, **kwargs)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image(path):
    im = Image.open(path).convert("RGB")
    if im.size != (W, H):
        raise ValueError(f"unexpected image size {path}: {im.size}")
    return im


def metric(a, b):
    delta = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    mask = delta > 20
    eroded = mask.copy()
    for _ in range(2):
        eroded = (eroded & np.roll(eroded, 1, 0) & np.roll(eroded, -1, 0)
                   & np.roll(eroded, 1, 1) & np.roll(eroded, -1, 1))
    return {"raw_percent": round(float(mask.mean() * 100), 3),
            "structural_percent": round(float(eroded.mean() * 100), 3)}


def overlay(a, b):
    arr = np.asarray(a).copy()
    delta = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    arr[delta > 20] = (255, 0, 0)
    return Image.fromarray(arr)


def panel(cells, labels, title):
    gap, label_h, title_h = 6, 17, 20
    out = Image.new("RGB", (4 * W + 5 * gap, title_h + label_h + H + gap), "#f7f8fa")
    draw = ImageDraw.Draw(out)
    draw.text((gap, 3), title, fill="#20232a")
    for i, (im, label) in enumerate(zip(cells, labels)):
        x = gap + i * (W + gap)
        draw.text((x, title_h + 1), label, fill="#20232a")
        out.paste(im, (x, title_h + label_h))
    return out


def capture(name, svg, zoom, args, work, firefox=False):
    tag = f"{name}_{zoom:g}"
    html = work / f"{tag}.html"
    html.write_text(run([args.python, str(HERE / "make_ref.py"), str(svg), str(zoom)]).stdout)
    chrome = work / f"chromium_{tag}.png"
    run([args.chromium, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", f"--window-size={W},{H}",
         "--default-background-color=FFFFFFFF", f"--screenshot={chrome}", html.as_uri()])
    outputs = {"chromium": image(chrome)}
    if firefox:
        ff = work / f"firefox_{tag}.png"
        run([args.firefox, "--headless", "--no-remote", "--profile", str(work / "ff-profile"),
             f"--window-size={W},{H}", "--screenshot", str(ff), html.as_uri()])
        outputs["firefox"] = image(ff)
    for label, binary in (("base", args.base_bin), ("pr", args.pr_bin)):
        ppm = work / f"{label}_{tag}.ppm"
        run([binary, str(zoom), str(ppm), str(svg)],
            env={**os.environ, "SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1"})
        outputs[label] = image(ppm)
    return outputs


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-src", required=True)
    ap.add_argument("--pr-src", required=True)
    ap.add_argument("--base-bin", required=True)
    ap.add_argument("--pr-bin", required=True)
    ap.add_argument("--chromium", required=True)
    ap.add_argument("--firefox", required=True)
    ap.add_argument("--python", default="python3")
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    (args.work / "ff-profile").mkdir(exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)

    clip = ASSETS / "clipdemo.svg"
    busey = ASSETS / "corpus/buseybench/gpt-6-astra.svg"
    version = lambda command: run(command).stdout.strip()
    manifest = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": version(["git", "-C", args.base_src, "rev-parse", "HEAD"]),
        "pr_commit": version(["git", "-C", args.pr_src, "rev-parse", "HEAD"]),
        "fixture_asset_commit": version(["git", "-C", str(ASSETS), "rev-parse", "HEAD"]),
        "chromium": version([args.chromium, "--version"]),
        "firefox": version([args.firefox, "--version"]),
        "host": version(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "rustc": version(["rustc", "--version"]),
        "platform": "macOS WGPU/Metal, 460x260 Rgba8Unorm, white background",
        "build_cfg": {"base": ["harness_turbulence"],
                      "pr": ["harness_clip", "harness_turbulence"]},
        "render_env": {"SKIP_UNSUPPORTED_FILTERS": "1", "VIEWPORT_CLIP": "1"},
        "framing": "200x200 SVG box at (130,30), pivot zoom about (230,130)",
        "comparison": "max RGB channel delta >20/255; structural is two-pixel binary erosion",
        "harness_sha256": sha256(HERE / "_logos_full.rs"),
        "make_ref_sha256": sha256(HERE / "make_ref.py"),
        "inputs": {str(p.relative_to(ASSETS)): sha256(p) for p in (clip, busey)},
        "scenes": {},
    }

    rows = []
    for name, svg, zoom in (("clipdemo", clip, 1.5), ("gpt-6-astra", busey, 1.0)):
        frames = capture(name, svg, zoom, args, args.work, firefox=True)
        base, pr, chrome, ff = (frames[k] for k in ("base", "pr", "chromium", "firefox"))
        base_m, pr_m, ff_m = metric(base, chrome), metric(pr, chrome), metric(pr, ff)
        manifest["scenes"][name] = {
            "zoom": zoom, "base_vs_chromium": base_m,
            "pr_vs_chromium": pr_m, "pr_vs_firefox": ff_m,
            "chromium_vs_firefox": metric(chrome, ff),
        }
        rows.append(panel((base, pr, chrome, ff),
                          ("master " + manifest["base_commit"][:7],
                           "PR " + manifest["pr_commit"][:7],
                           "Chromium 156", "Firefox 157"),
                          f"{name}  zoom {zoom:g}x"))
        rows.append(panel((overlay(base, chrome), overlay(pr, chrome),
                           overlay(pr, ff), overlay(chrome, ff)),
                          (f"master vs Chromium  {base_m['raw_percent']:.2f}%",
                           f"PR vs Chromium  {pr_m['raw_percent']:.2f}%",
                           f"PR vs Firefox  {ff_m['raw_percent']:.2f}%",
                           "Chromium vs Firefox"),
                          "Red pixels differ by >20/255 in at least one RGB channel"))
    gap = 6
    static = Image.new("RGB", (rows[0].width, sum(im.height for im in rows) + gap * (len(rows) - 1)), "#f7f8fa")
    y = 0
    for im in rows:
        static.paste(im, (0, y))
        y += im.height + gap
    static.save(args.output / "clip-and-corpus-static.png", optimize=True)

    gif = []
    manifest["zoom_ladder"] = {}
    for zoom in ZOOMS:
        frames = capture("clipdemo", clip, zoom, args, args.work)
        base, pr, chrome = (frames[k] for k in ("base", "pr", "chromium"))
        base_m, pr_m = metric(base, chrome), metric(pr, chrome)
        manifest["zoom_ladder"][f"{zoom:g}"] = {"base_vs_chromium": base_m, "pr_vs_chromium": pr_m}
        gif.append(panel((base, pr, chrome, overlay(pr, chrome)),
                         ("master " + manifest["base_commit"][:7],
                          "PR " + manifest["pr_commit"][:7],
                          "Chromium 156", f"PR diff  {pr_m['raw_percent']:.2f}% / {pr_m['structural_percent']:.3f}%"),
                         f"clipdemo  zoom {zoom:g}x  |  master {base_m['raw_percent']:.2f}% / {base_m['structural_percent']:.3f}%"))
    gif[0].save(args.output / "clip-zoom-11.gif", save_all=True, append_images=gif[1:],
                duration=800, loop=0, optimize=True)
    manifest["output_sha256"] = {p.name: sha256(p) for p in args.output.glob("*.png")}
    manifest["output_sha256"].update({p.name: sha256(p) for p in args.output.glob("*.gif")})
    (args.output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["scenes"], indent=2))


if __name__ == "__main__":
    main()
