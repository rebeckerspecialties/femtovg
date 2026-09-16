"""Low-end device cost model over the measured frames (a copy of harness/pz/model_pi.py's structure with
device profiles as parameters).

Inputs (measured on this Mac, harness/pz/measurements.json): per-frame fragment counts by pass type,
blur/turbulence taps, pass store/load pixels, pass switches, draw-call mix, blur count, femtovg
recording CPU ms, wgpu encode ms, Metal GPU ms, image/transient bytes.  Everything device-specific is
a stated rate or factor in DEVICES below (central, optimistic, pessimistic).  Frame time = max(CPU, GPU)
with perfect overlap (the verdict), CPU + GPU without (the worst end of the range).

Resolutions: "640x480" and "1080p" are measured framings.  "4k" (3840x2160, box 2160 at 840,0) is
extrapolated from the 1080p counts with each file's own measured 640x480 -> 1080p scaling exponent per
count type (area ratio 5.0625 -> 4.0), draw calls / passes / CPU recording unchanged.

Variants: "patched" applies the per-file count reductions measured for the six parked patches
(harness/pz/patched_all6.md); "bbox" estimates application-side scissoring of every layer to its
group's layer bounding box, from the per-layer bbox the fixed harness logs (LAYER_LOG=1); "budget"
applies the fixed-tree pass-through counts under a 32/48 MiB transient budget.

Usage: PZ=<harness/pz dir> RUNS=<dir of fixed-binary .err logs> OUT=<dir> python3 model_devices.py
"""
import json, os, re, statistics, glob, math

PZ = os.environ.get("PZ", "/private/tmp/wt-da/harness/pz")
RUNS = os.environ.get("RUNS", "")
OUT = os.environ.get("OUT", os.path.dirname(os.path.abspath(__file__)))
meas = json.load(open(f"{PZ}/measurements.json"))
ORDER = ["central", "low", "high"]  # index 1 = optimistic (fast), 2 = pessimistic (slow)

# ---- device profiles (central, optimistic, pessimistic) -------------------------------------------
# Every rate is Gfrag/s (fragments of that pass type per second), Gtap/s for texture taps, GB/s for the
# bus, a dimensionless slowdown vs this Mac (Apple M4 Max) for the CPU, and us per driver event.
DEVICES = {
    "pi_zero": {
        "name": "Raspberry Pi Zero (BCM2835: ARM11 1 GHz, VideoCore IV GLES2 via Mesa vc4, LPDDR2 ~1.5 GB/s shared)",
        "short": "Pi Zero",
        "api": "OpenGL ES 2 (femtovg GL backend, Mesa vc4)",
        "resolutions": ["640x480", "1080p"],
        "color_gfrag":   (0.40, 0.60, 0.30),
        "image_gfrag":   (0.30, 0.50, 0.20),
        "stencil_gfrag": (0.80, 1.00, 0.60),
        "clear_gfrag":   (1.00, 1.20, 0.80),
        "tap_gtap":      (1.00, 1.50, 0.70),
        "noise_gtap":    (0.50, 0.80, 0.35),
        "bandwidth_gbs": (1.50, 2.00, 1.00),
        "zs_fraction":   (0.5, 0.0, 1.0),
        "cpu_factor":    (45.0, 30.0, 60.0),
        "us_per_draw":   (60.0, 30.0, 120.0),
        "us_per_pass":   (150.0, 80.0, 300.0),
        "us_per_tex_alloc": (600.0, 300.0, 1500.0),
        "us_per_pass_gpu": (0.0, 0.0, 0.0),   # not in model_pi.py; kept at 0 so these rows equal model.md
        "stencil_bpp":   (4, 1, 4),
        "gpu_mem_limit_mb": 64,   # gpu_mem=64 default split
    },
    "iphone_xs": {
        "name": "iPhone XS (Apple A12: 2x Vortex 2.49 GHz, 4-core Apple GPU ~1.13 GHz, LPDDR4X-4266 34.1 GB/s), Metal via wgpu",
        "short": "iPhone XS",
        "api": "Metal (femtovg wgpu backend)",
        "resolutions": ["640x480", "1080p"],
        # 576 GFLOPS FP32 (4 cores x 64 FMA/clk x 1.13 GHz, cpu-monkey/nanoreview estimate) over ~60 scalar
        # flops per femtovg gradient/colour fragment (scissor mask, paint matrix, sdroundrect, dither, mix,
        # premultiply) = 9.6 Gfrag/s ideal; x0.6 for issue/occupancy losses and blending.
        "color_gfrag":   (6.0, 9.0, 4.0),
        "image_gfrag":   (5.0, 8.0, 3.0),     # + one bilinear fetch (27.8 GTexel/s peak, not limiting)
        "stencil_gfrag": (15.0, 25.0, 10.0),  # no colour math; TBDR stencil stays in tile memory
        "clear_gfrag":   (30.0, 60.0, 15.0),  # tile clears
        "tap_gtap":      (12.0, 20.0, 8.0),   # GFXBench texturing 27.8 GTexel/s offscreen; 1-D blur taps
        "noise_gtap":    (4.0, 8.0, 2.5),     # dependent nearest taps into the 512x256 lattice + ~30 ALU/octave
        "bandwidth_gbs": (25.0, 30.0, 18.0),  # 34.1 GB/s LPDDR4X-4266 peak, GPU-achievable share
        "zs_fraction":   (0.5, 0.0, 1.0),
        "cpu_factor":    (3.1, 2.5, 4.0),     # Geekbench 6 single-core 4060 (M4 Max) / 1306 (iPhone XS)
        # wgpu's Metal encode on this Mac fits encode_ms = 0.72 us x draws + 18.4 us x pass switches +
        # 15.3 us x blurs (R^2 0.996 over the 70 measured frames); scaled by the CPU factor.
        "us_per_draw":   (2.2, 1.8, 2.9),
        "us_per_pass":   (57.0, 46.0, 74.0),
        "us_per_tex_alloc": (47.0, 38.0, 61.0),
        # GPU-side cost of a render-pass boundary on a TBDR (tile flush + pipeline drain): this Mac's measured
        # Metal GPU time fits 25-27 us per pass switch (R^2 0.97 over 70 frames) on an M4 Max at ~1.6 GHz;
        # an A12 at 1.13 GHz with a quarter of the cores is taken at 2-4x that.
        "us_per_pass_gpu": (60.0, 30.0, 120.0),
        "stencil_bpp":   (1, 1, 1),           # wgpu Stencil8
        "gpu_mem_limit_mb": 1500,             # unified 4 GB; iOS jetsam limit ~1.4-2 GB for a foreground app
    },
    "tvbox_s905x2": {
        "name": "Android 9 TV box, Amlogic S905X2 (4x Cortex-A53 1.8 GHz, Mali-G31 MP2 650 MHz GLES 3.2, DDR4 32-bit ~8.5-10.7 GB/s peak)",
        "short": "S905X2 / Mali-G31 MP2",
        "api": "OpenGL ES 3.2 (femtovg GL backend, Arm proprietary driver)",
        "resolutions": ["640x480", "1080p", "4k"],
        # 20.8 GFLOPS FP32 (2 cores x 8 FMA/clk x 650 MHz); highp shader runs FP32 on Bifrost; ~60 flops per
        # colour fragment at ~0.85 utilisation (scalar clause ISA) -> 0.3 Gfrag/s ALU-bound, against a 1.3-2.6
        # Gpix/s pixel rate. glmark2-es2 offscreen puts the G31 MP2 (ODROID-C4 ~300) ~1.4x a VideoCore IV at
        # 300 MHz (Pi 3B 218) and ~1.5x a Mali-450 MP3 (Hardkernel), so the central colour rate is held at the
        # Pi Zero's 0.4 with the same range.
        "color_gfrag":   (0.40, 0.60, 0.25),
        "image_gfrag":   (0.32, 0.50, 0.20),
        "stencil_gfrag": (1.20, 2.00, 0.70),  # 1 px/clk/core (uni-pixel) = 1.3 Gpix/s; dual-pixel 2.6
        "clear_gfrag":   (1.30, 2.60, 0.80),
        "tap_gtap":      (1.10, 1.60, 0.70),  # 1 bilinear texel/clk/core = 1.3 Gtexel/s peak
        "noise_gtap":    (0.40, 0.70, 0.25),
        "bandwidth_gbs": (5.0, 7.0, 3.5),     # DDR4-2133..2666 x32: 8.5-10.7 GB/s peak, shared with CPU/VPU/scanout
        "zs_fraction":   (0.5, 0.0, 1.0),
        "cpu_factor":    (24.0, 18.0, 32.0),  # Cortex-A53 1.8 GHz: Snapdragon 450 GB6 single 169 vs M4 Max 4060
        "us_per_draw":   (25.0, 12.0, 50.0),  # Arm GLES driver on an A53: descriptor build + state validation
        "us_per_pass":   (300.0, 150.0, 600.0),  # FBO switch = tile flush + new job chain + kernel submit
        "us_per_tex_alloc": (500.0, 250.0, 1500.0),
        "us_per_pass_gpu": (200.0, 100.0, 400.0),  # Mali: an FBO switch ends the tiler job and starts a fragment job
        "stencil_bpp":   (4, 1, 4),           # stencil renderbuffer backed by D24S8 unless the driver packs S8
        "gpu_mem_limit_mb": 1024,             # 2-4 GB unified; Android app heap/graphics limit
    },
    "tvbox_s905": {
        "name": "Android TV box, Amlogic S905 (4x Cortex-A53 1.5 GHz, Mali-450 MP3 750 MHz GLES2, DDR3 32-bit ~7.5 GB/s peak)",
        "short": "S905 / Mali-450 MP3",
        "api": "OpenGL ES 2 (femtovg GL backend, Arm Utgard driver; fragment shaders FP16 only)",
        "resolutions": ["640x480", "1080p", "4k"],
        # 3 fragment processors x ~6.75 GFLOPS (FP16) at 750 MHz = 20 GFLOPS; the highp shader silently runs
        # at FP16; VLIW packing ~0.7 -> 0.24 Gfrag/s.
        "color_gfrag":   (0.25, 0.40, 0.15),
        "image_gfrag":   (0.20, 0.35, 0.12),
        "stencil_gfrag": (1.50, 2.20, 1.00),  # 1 px/clk/PP = 2.25 Gpix/s peak
        "clear_gfrag":   (1.50, 2.20, 1.00),
        "tap_gtap":      (0.80, 1.50, 0.50),  # 1 texel/clk/PP = 2.25 Gtexel/s peak; unrolled 24-tap loop
        "noise_gtap":    (0.25, 0.50, 0.15),  # 10-octave dependent-fetch loop fully unrolled on Utgard
        "bandwidth_gbs": (4.0, 5.5, 2.5),     # DDR3-1866 x32 (7.5 GB/s peak), shared
        "zs_fraction":   (0.5, 0.0, 1.0),
        "cpu_factor":    (29.0, 22.0, 40.0),  # Cortex-A53 1.5 GHz: 169 x 1.5/1.8 = 141 vs 4060
        "us_per_draw":   (30.0, 15.0, 60.0),
        "us_per_pass":   (350.0, 150.0, 700.0),
        "us_per_tex_alloc": (600.0, 300.0, 1500.0),
        "us_per_pass_gpu": (250.0, 120.0, 500.0),
        "stencil_bpp":   (4, 1, 4),
        "gpu_mem_limit_mb": 512,
    },
}
DEVICE_ORDER = ["pi_zero", "iphone_xs", "tvbox_s905x2", "tvbox_s905"]

# Mac GPU (M4 Max 40-core, Metal) -> A12 cross-check factor from Geekbench 6 Metal: 192,532 / 6,525.
MAC_TO_A12_GPU = (30.0, 25.0, 40.0)

FRAME = {"640x480": (640, 480, 480), "1080p": (1920, 1080, 1080), "4k": (3840, 2160, 2160)}
LAYER_GRANULARITY = 64

PIXEL_KEYS = ["color_pixels", "image_pixels", "stencil_pixels", "full_target_stencil_pixels", "clear_pixels",
              "filter_pixels", "filter_taps", "pass_store_pixels", "pass_load_pixels", "pass_clear_pixels",
              "transient_bytes", "image_bytes", "fringe_pixels", "cover_pixels", "winding_pixels"]

def draw_calls(st):
    """GL draw calls per frame from the command mix (per-command sub-passes as in opengl.rs)."""
    extra_drawables = max(0.0, st["drawables"] - (st["convex_fill"] + st["concave_fill"] + st["stroke"] + st["stencil_stroke"] + st["clip_fill"]))
    return (2 * st["convex_fill"] + 3 * st["concave_fill"] + st["stroke"] + 3 * st["stencil_stroke"]
            + st["triangles"] + st["clear_rect"] + st["clip_reset"] + 3 * st["clip_fill"]
            + 2 * st["blur_filters"] + st["turbulence_filters"] + st["other_filters"] + 2 * extra_drawables)

def model(rec, dev, which=0):
    st = rec["stats"]; a = {k: v[which] for k, v in dev.items() if isinstance(v, tuple)}
    noise_share = 0.5 if st["turbulence_filters"] > 0 else 0.0
    frag_ms = {
        "color":   (st["color_pixels"] - st["image_pixels"]) / (a["color_gfrag"] * 1e9) * 1e3,
        "image":   st["image_pixels"] / (a["image_gfrag"] * 1e9) * 1e3,
        "stencil": st["stencil_pixels"] / (a["stencil_gfrag"] * 1e9) * 1e3,
        "clear":   st["clear_pixels"] / (a["clear_gfrag"] * 1e9) * 1e3,
        "filter":  st["filter_taps"] * (1 - noise_share) / (a["tap_gtap"] * 1e9) * 1e3 + st["filter_taps"] * noise_share / (a["noise_gtap"] * 1e9) * 1e3,
    }
    gpu_frag_ms = sum(frag_ms.values())
    tile_bytes = (st["pass_store_pixels"] + st["pass_load_pixels"]) * 4 * (1 + a["zs_fraction"])
    tile_ms = tile_bytes / (a["bandwidth_gbs"] * 1e9) * 1e3
    pass_gpu_ms = st["pass_switches"] * a["us_per_pass_gpu"] / 1e3
    gpu_ms = gpu_frag_ms + tile_ms + pass_gpu_ms
    cpu_record_ms = rec["femtovg_record_ms"] * a["cpu_factor"]
    dc = draw_calls(st)
    cpu_gl_ms = dc * a["us_per_draw"] / 1e3 + st["pass_switches"] * a["us_per_pass"] / 1e3 + st["blur_filters"] * a["us_per_tex_alloc"] / 1e3
    cpu_ms = cpu_record_ms + cpu_gl_ms
    return {
        "gpu_frag_ms": gpu_frag_ms, "gpu_frag_breakdown_ms": frag_ms, "tile_bytes_mb": tile_bytes / 1e6, "tile_ms": tile_ms,
        "pass_gpu_ms": pass_gpu_ms, "gpu_ms": gpu_ms, "cpu_record_ms": cpu_record_ms, "draw_calls": dc, "cpu_gl_ms": cpu_gl_ms, "cpu_ms": cpu_ms,
        "frame_ms_best": max(cpu_ms, gpu_ms), "frame_ms_worst": cpu_ms + gpu_ms,
    }

def verdict(ms):
    if ms <= 16.7: return "60 fps"
    if ms <= 33.3: return "30 fps"
    if ms <= 100: return "10-30 fps"
    return "non-interactive"
VERDICTS = ["60 fps", "30 fps", "10-30 fps", "non-interactive"]

def gpu_mem_mb(rec, dev, which=0):
    st = rec["stats"]; a = {k: v[which] for k, v in dev.items() if isinstance(v, tuple)}
    fw, fh, _ = FRAME[rec["framing"]]
    target_px = st["image_bytes"] / 4
    screen = fw * fh * (4 * 2 + 4)
    blur_scratch = (st["transient_bytes"] / max(1, st["transient_images"])) * (1 + a["stencil_bpp"] / 4) if st["blur_filters"] > 0 else 0
    total = st["image_bytes"] + target_px * a["stencil_bpp"] + screen + blur_scratch + st["vert_capacity_bytes"]
    return {"images_mb": st["image_bytes"] / 2**20, "image_stencil_mb": target_px * a["stencil_bpp"] / 2**20, "screen_mb": screen / 2**20,
            "blur_scratch_mb": blur_scratch / 2**20, "vertex_buffer_mb": st["vert_capacity_bytes"] / 2**20, "total_mb": total / 2**20}

# ---- derived inputs ---------------------------------------------------------------------------------
import copy
base = {(r["set"], r["framing"], r["file"]): r for r in meas}

def make_4k(r1080, r640):
    """Extrapolate a 4k record from the 1080p one with the file's own 640x480 -> 1080p exponent per count."""
    r = copy.deepcopy(r1080); r["framing"] = "4k"; r["derived"] = "4k extrapolated"
    st, s1, s0 = r["stats"], r1080["stats"], r640["stats"]
    area_meas, area_4k = (1080 / 480) ** 2, (2160 / 1080) ** 2
    exps = {}
    for k in PIXEL_KEYS:
        if s0.get(k, 0) > 0 and s1.get(k, 0) > 0:
            e = math.log(s1[k] / s0[k]) / math.log(area_meas)
            e = min(1.5, max(0.8, e))
        else:
            e = 1.0
        exps[k] = e
        st[k] = s1[k] * area_4k ** e
    r["exponents_4k"] = exps
    r["transient_at_flush"] = st["transient_bytes"]
    return r

for key in list(base):
    setname, framing, file = key
    if framing == "1080p":
        base[(setname, "4k", file)] = make_4k(base[key], base[(setname, "640x480", file)])

# ---- patch deltas (harness/pz/patched_all6.md: measured before -> after on this Mac) -----------------
def parse_patched(path):
    out = {}
    section = None
    for line in open(path):
        m = re.match(r"## (\w+) @ (\S+)", line)
        if m: section = (m.group(1), m.group(2)); continue
        if not section or not line.startswith("| ") or line.startswith("| file") or line.startswith("|---"): continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 15: continue
        def pair(c):
            a, b = c.split("->"); return float(a), float(b)
        out[(section[0], section[1], cells[0])] = {
            "clipq_mpx": pair(cells[1]), "pass_switches": pair(cells[2]), "tile_mpx": pair(cells[3]), "filter_mpx": pair(cells[4]),
            "transient_mb": pair(cells[5]), "allocs": pair(cells[6]), "record_ms": pair(cells[9]),
        }
    return out
PATCHED = parse_patched(f"{PZ}/patched_all6.md") if os.path.exists(f"{PZ}/patched_all6.md") else {}

def apply_patches(rec):
    """Scale the measured counts by the per-file before->after ratios of the six patches (1080p ratios for 4k)."""
    fr = "1080p" if rec["framing"] == "4k" else rec["framing"]
    p = PATCHED.get((rec["set"], fr, rec["file"]))
    if not p: return None
    r = copy.deepcopy(rec); st = r["stats"]; r["derived"] = (rec.get("derived", "") + " patched").strip()
    ratio = lambda k: (p[k][1] / p[k][0]) if p[k][0] > 0 else 1.0
    # clip quads: full-target stencil pixels shrink by the measured Mpx difference (scaled for 4k)
    scale = (2160 / 1080) ** 2 if rec["framing"] == "4k" else 1.0
    dq = (p["clipq_mpx"][0] - p["clipq_mpx"][1]) * 1e6 * scale
    st["stencil_pixels"] = max(0.0, st["stencil_pixels"] - dq)
    st["full_target_stencil_pixels"] = max(0.0, st["full_target_stencil_pixels"] - dq)
    st["pass_switches"] = st["pass_switches"] * ratio("pass_switches")
    for k in ("pass_store_pixels", "pass_load_pixels"): st[k] *= ratio("tile_mpx")
    for k in ("filter_pixels", "filter_taps"): st[k] *= ratio("filter_mpx")
    st["transient_bytes"] *= ratio("transient_mb")
    # patch 02 removes one transient + parity pass per lone blur: the image (composite) pixels of that
    # pass go with the filter pixels; approximate with the same ratio on image pixels' filter share.
    st["image_pixels"] *= (0.5 + 0.5 * ratio("filter_mpx"))
    st["color_pixels"] -= rec["stats"]["image_pixels"] - st["image_pixels"]
    r["femtovg_record_ms"] = rec["femtovg_record_ms"] * ratio("record_ms")
    return r

# ---- fixed-binary runs (LAYER_LOG / LAYER_STATS) ----------------------------------------------------
def parse_run(path):
    layers, masks = [], []
    stats = {}
    for line in open(path):
        m = re.match(r"LAYER kind=(\w+) depth=(\d+) bbox=(\d+)x(\d+) sigma=([\d.]+) opacity=([\d.]+)", line)
        if m:
            layers.append({"kind": m.group(1), "depth": int(m.group(2)), "w": int(m.group(3)), "h": int(m.group(4)),
                           "sigma": float(m.group(5)), "opacity": float(m.group(6))}); continue
        m = re.match(r"MASK (\d+)x(\d+)", line)
        if m: masks.append((int(m.group(1)), int(m.group(2)))); continue
        for key, pat in (("layers", r"layers begun: (\d+)"), ("transient", r"transient bytes held at flush: (\d+)"),
                         ("pass_through", r"layers passed through: (\d+)")):
            m = re.match(pat, line)
            if m: stats[key] = int(m.group(1))
    return {"layers_log": layers, "masks": masks, **stats}

RUN = {}
if RUNS and os.path.isdir(RUNS):
    for path in glob.glob(f"{RUNS}/*.err"):
        tag = os.path.basename(path)[:-4]
        name, fr, mb, bb = tag.split("__")
        RUN[(name, fr, mb[1:], bb)] = parse_run(path)

def bbox_factor(rec):
    """Share of the viewport-sized layer work that remains when each layer is scissored to its group's bbox
    (blur padding 3 sigma each side, 64-px granularity), from the fixed harness's LAYER_LOG at this framing."""
    run = RUN.get((rec["file"], rec["framing"], "default", "viewport"))
    if not run: return None
    if not run["layers_log"]: return 1.0  # no layers: nothing to scissor, the frame is unchanged
    _, _, box = FRAME[rec["framing"]]
    g = LAYER_GRANULARITY
    full = (math.ceil(box / g) * g) ** 2
    num = den = 0.0
    for l in run["layers_log"]:
        pad = 2 * math.ceil(3 * l["sigma"])
        w = min(box + pad, l["w"] + pad); h = min(box + pad, l["h"] + pad)
        w = math.ceil(max(w, 1) / g) * g; h = math.ceil(max(h, 1) / g) * g
        num += w * h
        fw = math.ceil((box + pad) / g) * g
        den += fw * fw
    return num / den if den else None

def apply_bbox(rec):
    f = bbox_factor(rec)
    if f is None: return None
    r = copy.deepcopy(rec); st = r["stats"]; s0 = rec["stats"]; r["derived"] = (rec.get("derived", "") + " bbox").strip()
    r["bbox_factor"] = f
    fw, fh, _ = FRAME[rec["framing"]]
    frame_px = fw * fh
    # layer-sized work: composites/parity/mask draws (image px), layer clears, filter passes, full-target clip
    # quads, and the layer-sized half of the tile store/load traffic (the other half is the parent's).
    st["image_pixels"] = s0["image_pixels"] * f
    st["color_pixels"] = s0["color_pixels"] - (s0["image_pixels"] - st["image_pixels"])
    st["clear_pixels"] = frame_px + max(0.0, s0["clear_pixels"] - frame_px) * f
    for k in ("filter_pixels", "filter_taps"): st[k] = s0[k] * f
    st["stencil_pixels"] = s0["stencil_pixels"] - s0["full_target_stencil_pixels"] * (1 - f)
    st["full_target_stencil_pixels"] = s0["full_target_stencil_pixels"] * f
    for k in ("pass_store_pixels", "pass_load_pixels"): st[k] = s0[k] * (0.5 + 0.5 * f)
    st["transient_bytes"] = s0["transient_bytes"] * f
    st["image_bytes"] = s0["image_bytes"] * f
    return r

# ---- rows -------------------------------------------------------------------------------------------
def row(rec, devkey, variant="base"):
    dev = DEVICES[devkey]
    m = {w: model(rec, dev, i) for i, w in enumerate(ORDER)}
    c = m["central"]
    out = {
        "device": devkey, "variant": variant, "set": rec["set"], "file": rec["file"], "resolution": rec["framing"],
        "gpu_ms": c["gpu_ms"], "gpu_frag_ms": c["gpu_frag_ms"], "tile_ms": c["tile_ms"], "pass_gpu_ms": c["pass_gpu_ms"], "frag_breakdown": c["gpu_frag_breakdown_ms"],
        "cpu_ms": c["cpu_ms"], "cpu_record_ms": c["cpu_record_ms"], "cpu_gl_ms": c["cpu_gl_ms"], "draw_calls": c["draw_calls"],
        "frame_ms": c["frame_ms_best"], "frame_ms_opt": m["low"]["frame_ms_best"], "frame_ms_pess": m["high"]["frame_ms_worst"],
        "verdict": verdict(c["frame_ms_best"]), "verdict_opt": verdict(m["low"]["frame_ms_best"]), "verdict_pess": verdict(m["high"]["frame_ms_worst"]),
        "gpu_mem_mb": gpu_mem_mb(rec, dev)["total_mb"],
        "layers": rec.get("layers"), "blurs": rec["stats"]["blur_filters"], "turbulence": rec["stats"]["turbulence_filters"],
        "masks": rec["stats"]["masks_applied"], "clip_quads_mpx": rec["stats"]["full_target_stencil_pixels"] / 1e6,
        "filter_mtaps": rec["stats"]["filter_taps"] / 1e6, "tile_mpx": (rec["stats"]["pass_store_pixels"] + rec["stats"]["pass_load_pixels"]) / 1e6,
        "pixels_touched_mpx": (rec["stats"]["color_pixels"] + rec["stats"]["stencil_pixels"] + rec["stats"]["filter_pixels"] + rec["stats"]["clear_pixels"]) / 1e6,
        "gpu_ms_mac": rec.get("gpu_ms"), "bbox_factor": rec.get("bbox_factor"),
    }
    if devkey == "iphone_xs" and rec.get("gpu_ms") and rec["framing"] != "4k" and variant == "base":
        out["gpu_ms_crosscheck"] = rec["gpu_ms"] * MAC_TO_A12_GPU[0]
    return out

rows = []
for key in sorted(base):
    rec = base[key]
    for devkey in DEVICE_ORDER:
        if rec["framing"] not in DEVICES[devkey]["resolutions"]: continue
        rows.append(row(rec, devkey, "base"))
        p = apply_patches(rec)
        if p: rows.append(row(p, devkey, "patched"))
        b = apply_bbox(rec)
        if b:
            rows.append(row(b, devkey, "bbox"))
            pb = apply_patches(b)
            if pb: rows.append(row(pb, devkey, "patched+bbox"))

def pct(vals, q):
    vals = sorted(vals)
    if not vals: return float("nan")
    k = (len(vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)

def summary(rs):
    ms = [r["frame_ms"] for r in rs]
    v = {k: sum(1 for r in rs if r["verdict"] == k) for k in VERDICTS}
    return {"n": len(rs), "median_ms": statistics.median(ms), "p90_ms": pct(ms, 0.9), "worst_ms": max(ms), "verdicts": v,
            "approachable": f"{v['60 fps']}/{v['30 fps']}/{v['10-30 fps']}/{v['non-interactive']} at 60/30/10-30/non"}

SUMMARY = {}
for devkey in DEVICE_ORDER:
    for res in DEVICES[devkey]["resolutions"]:
        for setname in ("icons", "busey"):
            for variant in ("base", "patched", "bbox", "patched+bbox"):
                rs = [r for r in rows if r["device"] == devkey and r["resolution"] == res and r["set"] == setname and r["variant"] == variant]
                if rs: SUMMARY[(devkey, res, setname, variant)] = summary(rs)

# ---- budget pass-through effect (fixed tree) ------------------------------------------------------
# From harness/pz/mask-budget-ladder.md (le-fix dc0f9a9, gated harness, 1080p): refused layers per file.
LADDER = {
    "48": {"gpt-5-2-pro": 7, "qwen3-8-max": 6},
    "32": {"claude-fable-5-1": 1, "fugu-ultra": 2, "gpt-5-2-pro": 7, "gpt-5-6-sol-pro": 3, "grok-4-5": 3, "nex-n2-pro": 3,
           "qwen3-8-27b": 1, "qwen3-8-flash": 2, "qwen3-8-max": 41},
}
def layer_machinery_ms(rec, dev, which=0):
    """GPU + driver ms of the per-layer machinery (tile traffic, clears, composites, filters, per-pass CPU)."""
    m = model(rec, dev, which)
    fb = m["gpu_frag_breakdown_ms"]
    gpu = m["tile_ms"] + fb["clear"] + fb["image"] + fb["filter"] + m["pass_gpu_ms"]
    st = rec["stats"]
    a = {k: v[which] for k, v in dev.items() if isinstance(v, tuple)}
    cpu = st["pass_switches"] * a["us_per_pass"] / 1e3 + st["blur_filters"] * a["us_per_tex_alloc"] / 1e3
    return gpu, cpu

BUDGET = []
for res, budgets in (("1080p", ("48", "32")), ("4k", ("128", "64"))):
    for mb in budgets:
        for file in sorted(set(k[2] for k in base if k[0] == "busey")):
            rec = base[("busey", res, file)]
            ladder_n = LADDER[mb].get(file, 0) if res == "1080p" else None
            run = RUN.get((file, res, mb, "viewport"), {})
            run_n = run.get("pass_through")
            run_layers = run.get("layers")
            run_default = RUN.get((file, res, "default", "viewport"), {})
            if not ladder_n and not run_n: continue
            n = run_n if run_n is not None else (ladder_n or 0)
            entry = {"file": file, "resolution": res, "budget_mib": int(mb), "layers": rec["layers"], "ladder_refused": ladder_n,
                     "fixed_full_stack_refused": run_n, "fixed_full_stack_layers": run_layers, "refused_used": n,
                     "peak_mib_default": (run_default.get("transient") or 0) / 2**20, "peak_mib": (run.get("transient") or 0) / 2**20, "per_device": {}}
            for devkey in DEVICE_ORDER:
                if res not in DEVICES[devkey]["resolutions"]: continue
                dev = DEVICES[devkey]
                gpu_l, cpu_l = layer_machinery_ms(rec, dev)
                m = model(rec, dev)
                per_layer_gpu = gpu_l / max(1, rec["layers"]); per_layer_cpu = cpu_l / max(1, rec["layers"])
                d_gpu, d_cpu = n * per_layer_gpu, n * per_layer_cpu
                new_frame = max(m["gpu_ms"] - d_gpu, m["cpu_ms"] - d_cpu)
                entry["per_device"][devkey] = {"frame_ms": m["frame_ms_best"], "frame_ms_refused": new_frame,
                                               "delta_ms": m["frame_ms_best"] - new_frame, "delta_pct": 100 * (m["frame_ms_best"] - new_frame) / m["frame_ms_best"],
                                               "verdict": verdict(m["frame_ms_best"]), "verdict_refused": verdict(new_frame)}
            BUDGET.append(entry)

# 640x480 and 4k budget checks from the fixed-binary runs
BUDGET_CHECK = {}
for (name, fr, mb, bb), run in RUN.items():
    if bb != "viewport": continue
    BUDGET_CHECK.setdefault((fr, mb), {})[name] = (run.get("layers"), run.get("pass_through"), (run.get("transient") or 0) / 2**20)

# ---- mechanism labels -------------------------------------------------------------------------------
def mechanisms(rec, devkey="pi_zero"):
    m = model(rec, DEVICES[devkey]); fb = m["gpu_frag_breakdown_ms"]; st = rec["stats"]
    parts = {"blur taps": fb["filter"] * (0.5 if st["turbulence_filters"] > 0 else 1.0),
             "layer store/load (tile traffic)": m["tile_ms"], "layer composites": fb["image"], "layer clears": fb["clear"],
             "clip stencil quads": st["full_target_stencil_pixels"] / (DEVICES[devkey]["stencil_gfrag"][0] * 1e9) * 1e3,
             "content fill": fb["color"], "pass boundaries": m["pass_gpu_ms"]}
    if st["turbulence_filters"] > 0: parts["turbulence"] = fb["filter"] * 0.5
    tot = sum(parts.values())
    ranked = sorted(parts.items(), key=lambda kv: -kv[1])
    flags = []
    if st["masks_applied"] > 0: flags.append(f"{int(st['masks_applied'])} viewport-sized mask(s)")
    if st["turbulence_filters"] > 0: flags.append(f"{int(st['turbulence_filters'])} feTurbulence")
    return {"shares": {k: v / tot for k, v in parts.items()}, "top": [k for k, _ in ranked[:2]], "flags": flags,
            "cpu_bound": m["cpu_ms"] > m["gpu_ms"]}

MECH = {}
for key in sorted(base):
    if key[1] == "1080p":
        MECH[(key[0], key[2])] = mechanisms(base[key])

json.dump({"devices": {k: {kk: vv for kk, vv in v.items()} for k, v in DEVICES.items()}, "assumption_order": ORDER,
           "rows": rows, "summary": {"|".join(k): v for k, v in SUMMARY.items()}, "budget": BUDGET,
           "budget_check": {"|".join(k): v for k, v in BUDGET_CHECK.items()},
           "mechanisms": {"|".join(k): v for k, v in MECH.items()},
           "bbox_factor": {"|".join(k): bbox_factor(base[k]) for k in base},
           "runs": {"|".join(k): {kk: vv for kk, vv in v.items() if kk != "layers_log"} for k, v in RUN.items()}},
          open(f"{OUT}/model_devices.json", "w"), indent=1, default=str)
print("rows", len(rows))
