#!/usr/bin/env python3
"""Write framed copies of the WPT css-masking candidates.

Most of these WPT files declare no width/height/viewBox: a browser gives the
root a 100%x100% viewport, usvg gives it Options::default_size (100x100). Both
renderers must see the same user space, so every framed copy gets an explicit
width/height/viewBox chosen from the content extent (the reference's extent is
the same by construction), and the harness box is sized to max(vb.w, vb.h) so
zoom 1.0 is one user unit per device pixel and zoom 2.0 is DPR 2.

The panning tests move the viewport with a <script> (currentTranslate.x=-75);
usvg has no DOM, and in a nested-svg reference page the script would pan the
outer frame, so the script is dropped and the pan is expressed as the viewBox
origin (75 0 200 200), which is what a currentTranslate of -75 does.

mask-text-001 asks for the WPT Ahem font (served from /fonts/ahem.css), which
is not installed here; besides the original, a copy set in Arial is written so
both renderers shape the same face.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS, REFS, OUT = f"{HERE}/tests", f"{HERE}/refs", f"{HERE}/framed"
os.makedirs(OUT, exist_ok=True)

# name -> (viewBox, ref file). None viewBox = keep the file's own.
CASES = {
    "clip-path-clip-nested-twice": ("0 0 200 200", "clip-path-square-002-ref.svg"),
    "mask-and-nested-clip-path": ("0 0 300 300", "mask-and-nested-clip-path-ref.svg"),
    "mask-negative-scale": ("0 0 200 200", "mask-negative-scale-001-ref.svg"),
    "mask-nested-clip-path-001": ("0 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-002": ("0 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-003": ("0 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-004": ("0 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-005": ("0 0 200 200", "mask-nested-clip-path-002-ref.svg"),
    "mask-nested-clip-path-006": ("0 0 200 200", "mask-nested-clip-path-002-ref.svg"),
    "mask-nested-clip-path-007": ("0 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-008": ("0 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-009": ("0 0 200 200", "mask-nested-clip-path-002-ref.svg"),
    "mask-nested-clip-path-010": ("0 0 400 100", "mask-nested-clip-path-003-ref.svg"),
    "mask-nested-clip-path-panning-001": ("75 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-nested-clip-path-panning-002": ("75 0 200 200", "mask-nested-clip-path-001-ref.svg"),
    "mask-objectboundingbox-content-clip-transform": ("0 0 200 200", "mask-content-clip-002-ref.svg"),
    "mask-objectboundingbox-content-clip": ("0 0 200 200", "mask-content-clip-001-ref.svg"),
    "mask-on-thin-stroked-path-userspaceonuse": ("0 0 200 100", "mask-on-thin-stroked-path-userspaceonuse-ref.svg"),
    "mask-text-001": ("0 0 100 100", "mask-text-001-ref.svg"),
    "mask-userspaceonuse-content-clip-transform": ("0 0 200 200", "mask-content-clip-002-ref.svg"),
    "mask-userspaceonuse-content-clip": ("0 0 200 200", "mask-content-clip-001-ref.svg"),
    "mask-with-filter": ("0 0 200 200", "mask-green-square-001-ref.svg"),
}
# A reference is framed in the test's own viewBox but with the pan removed
# (the ref files are all unpanned 0-origin drawings).
REF_VB = {
    "mask-nested-clip-path-panning-001": "0 0 200 200",
    "mask-nested-clip-path-panning-002": "0 0 200 200",
}


def reframe(text, vb):
    m = re.search(r"<svg\b([^>]*)>", text)
    attrs = m.group(1)
    attrs = re.sub(r'\s+(?:width|height|viewBox)="[^"]*"', "", attrs)
    w, h = vb.split()[2:]
    attrs += f' width="{w}" height="{h}" viewBox="{vb}"'
    text = text[: m.start()] + f"<svg{attrs}>" + text[m.end():]
    text = re.sub(r"<script>.*?</script>\s*", "", text, flags=re.S)
    return text


manifest = {}
for name, (vb, ref) in CASES.items():
    t = open(f"{TESTS}/{name}.svg").read()
    open(f"{OUT}/{name}.svg", "w").write(reframe(t, vb))
    rvb = REF_VB.get(name, vb)
    r = open(f"{REFS}/{ref}").read()
    rname = ref[:-4]
    open(f"{OUT}/{rname}.svg", "w").write(reframe(r, rvb))
    x, y, w, h = (float(v) for v in vb.split())
    B = int(max(w, h))
    frame = 2 * B + 60
    manifest[name] = {
        "viewBox": vb, "ref": rname, "ref_viewBox": rvb, "box": B,
        "frame_w": frame, "frame_h": frame, "box_x": B // 2 + 30, "box_y": B // 2 + 30,
        "svg_w": int(w), "svg_h": int(h),
    }

# Font-substituted copies of the text test and its reference.
for src in ("mask-text-001", "mask-text-001-ref"):
    t = open(f"{OUT}/{src}.svg").read().replace('font-family="Ahem"', 'font-family="Arial"')
    dst = src.replace("mask-text-001", "mask-text-001-arial")
    open(f"{OUT}/{dst}.svg", "w").write(t)
manifest["mask-text-001-arial"] = dict(manifest["mask-text-001"], ref="mask-text-001-arial-ref")

json.dump(manifest, open(f"{HERE}/manifest.json", "w"), indent=1)
print(f"{len(manifest)} cases, {len(os.listdir(OUT))} framed files")
