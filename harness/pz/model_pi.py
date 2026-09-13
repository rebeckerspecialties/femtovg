"""Raspberry Pi Zero (ARM11 + VideoCore IV, GLES2) scaling model over the measured frames.

Everything under "measured" comes from measurements.json (this Mac, release build, median of
steady-state frames). Everything under "model" is: measured pixel / byte / call counts times a
stated Pi Zero rate, or a measured Mac CPU time times a stated ARM11 slowdown factor. Ranges give
the low/high assumptions; the central column is what the fps verdicts use.
"""
import json, os, statistics
S = os.environ["S"]
meas = json.load(open(f"{S}/pz/measurements.json"))

# ---- Pi Zero assumptions (central, low, high) -------------------------------------------------
A = {
    # VideoCore IV fragment throughput per pass type, Gfrag/s. The chip's 1 Gpix/s is for a trivial
    # shader; femtovg's main fragment shader evaluates the scissor mask, paint matrix, gradient or
    # image sample and the stroke/AA mask per fragment, and every color pass is blended (RMW).
    "color_gfrag":   (0.40, 0.60, 0.30),   # solid/gradient fills, fringes, cover quads
    "image_gfrag":   (0.30, 0.50, 0.20),   # image-sampling composites (layer stores, blits): +1 TMU fetch
    "stencil_gfrag": (0.80, 1.00, 0.60),   # stencil-only passes: no color math, no blend
    "clear_gfrag":   (1.00, 1.20, 0.80),   # glClear -> tile clear, near peak
    "tap_gtap":      (1.00, 1.50, 0.70),   # texture taps in blur passes (linear reads along one axis)
    "noise_gtap":    (0.50, 0.80, 0.35),   # turbulence lattice taps: dependent, nearest, scattered
    # Memory: tile load/store per render pass at the shared bandwidth. Color 4 B/px; the Z/S buffer
    # is 4 B/px on VC4 (packed depth24/stencil8) and is loaded/stored when the job touches stencil.
    "bandwidth_gbs": (1.50, 2.00, 1.00),
    "zs_fraction":   (0.5, 0.0, 1.0),      # fraction of passes that also load+store the Z/S tile
    # CPU: ARM11 @ 1 GHz, single-issue in-order, VFP11 scalar, 16 KB L1, no L2, static branch
    # prediction, vs. an M4 performance core. Compute-bound scalar float ~25-35x; allocation- and
    # pointer-chasing-bound code 40-80x (DRAM latency with no L2). Recording is a mix.
    "cpu_factor":    (45.0, 30.0, 60.0),
    # Mesa vc4 GL driver CPU cost per draw call on ARM11 (state validation, uniform upload of
    # femtovg's 11 vec4 params, command-list emission). Range from vc4 driver overhead reports.
    "us_per_draw":   (60.0, 30.0, 120.0),
    # Per render-pass CPU cost in the driver (FBO bind, job submit ioctl, tile list setup).
    "us_per_pass":   (150.0, 80.0, 300.0),
    # Per texture allocate+free (blur scratch): CMA BO alloc ioctl + FBO create/validate.
    "us_per_tex_alloc": (600.0, 300.0, 1500.0),
    # Bytes of GPU memory a Pi pays per image render target beyond its color texels (stencil RBO).
    "stencil_bpp":   (4, 1, 4),
}
ORDER = ["central", "low", "high"]  # index 1 = optimistic (fast) assumptions, 2 = pessimistic

def draw_calls(st):
    """GL draw calls per frame from the command mix (per-command sub-passes as in opengl.rs)."""
    extra_drawables = max(0.0, st["drawables"] - (st["convex_fill"] + st["concave_fill"] + st["stroke"] + st["stencil_stroke"] + st["clip_fill"]))
    return (2 * st["convex_fill"] + 3 * st["concave_fill"] + st["stroke"] + 3 * st["stencil_stroke"]
            + st["triangles"] + st["clear_rect"] + st["clip_reset"] + 3 * st["clip_fill"]
            + 2 * st["blur_filters"] + st["turbulence_filters"] + st["other_filters"] + 2 * extra_drawables)

def model(rec, which=0):
    st = rec["stats"]; a = {k: v[which] for k, v in A.items()}
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
    gpu_ms = gpu_frag_ms + tile_ms
    cpu_record_ms = rec["femtovg_record_ms"] * a["cpu_factor"]
    dc = draw_calls(st)
    cpu_gl_ms = dc * a["us_per_draw"] / 1e3 + st["pass_switches"] * a["us_per_pass"] / 1e3 + st["blur_filters"] * a["us_per_tex_alloc"] / 1e3
    cpu_ms = cpu_record_ms + cpu_gl_ms
    return {
        "gpu_frag_ms": gpu_frag_ms, "gpu_frag_breakdown_ms": frag_ms, "tile_bytes_mb": tile_bytes / 1e6, "tile_ms": tile_ms,
        "gpu_ms": gpu_ms, "cpu_record_ms": cpu_record_ms, "draw_calls": dc, "cpu_gl_ms": cpu_gl_ms, "cpu_ms": cpu_ms,
        "frame_ms_best": max(cpu_ms, gpu_ms), "frame_ms_worst": cpu_ms + gpu_ms,
    }

def verdict(ms):
    if ms <= 16.7: return "60 fps"
    if ms <= 33.3: return "30 fps"
    if ms <= 100: return "10-30 fps"
    return "non-interactive"

def gpu_mem_mb(rec, which=0):
    st = rec["stats"]; a = {k: v[which] for k, v in A.items()}
    fw, fh = (640, 480) if rec["framing"] == "640x480" else (1920, 1080)
    target_px = st["image_bytes"] / 4  # masks + transients are render targets; LUT/lattice are negligible
    screen = fw * fh * (4 * 2 + 4)      # double-buffered color + one Z/S
    blur_scratch = (st["transient_bytes"] / max(1, st["transient_images"])) * (1 + a["stencil_bpp"] / 4) if st["blur_filters"] > 0 else 0
    total = st["image_bytes"] + target_px * a["stencil_bpp"] + screen + blur_scratch + st["vert_capacity_bytes"]
    return {"images_mb": st["image_bytes"] / 2**20, "image_stencil_mb": target_px * a["stencil_bpp"] / 2**20, "screen_mb": screen / 2**20,
            "blur_scratch_mb": blur_scratch / 2**20, "vertex_buffer_mb": st["vert_capacity_bytes"] / 2**20, "total_mb": total / 2**20}

rows = []
for rec in meas:
    st = rec["stats"]
    m = {w: model(rec, i) for i, w in enumerate(ORDER)}
    rows.append({
        "set": rec["set"], "file": rec["file"], "framing": rec["framing"],
        "measured": {
            "commands": st["commands"], "layers": rec["layers"], "pass_through": rec["pass_through"],
            "clip_path_calls": st["clip_path_calls"], "clip_replays": st["clip_replays"], "clip_replay_entries": st["clip_replay_entries"],
            "full_target_stencil_quads": st["full_target_stencil_quads"], "full_target_stencil_mpx": st["full_target_stencil_pixels"] / 1e6,
            "color_mpx": st["color_pixels"] / 1e6, "image_mpx": st["image_pixels"] / 1e6, "stencil_mpx": st["stencil_pixels"] / 1e6,
            "filter_mpx": st["filter_pixels"] / 1e6, "filter_mtaps": st["filter_taps"] / 1e6, "clear_mpx": st["clear_pixels"] / 1e6,
            "pixels_touched_mpx": (st["color_pixels"] + st["stencil_pixels"] + st["filter_pixels"] + st["clear_pixels"]) / 1e6,
            "pass_switches": st["pass_switches"], "tile_store_mpx": st["pass_store_pixels"] / 1e6, "tile_load_mpx": st["pass_load_pixels"] / 1e6,
            "blur_filters": st["blur_filters"], "turbulence_filters": st["turbulence_filters"], "other_filters": st["other_filters"],
            "shadows": st["shadows"], "masks": st["masks_applied"],
            "transient_mb": st["transient_bytes"] / 2**20, "transient_images": st["transient_images"], "image_mb": st["image_bytes"] / 2**20,
            "verts": st["verts"], "vert_kb": st["vert_bytes"] / 1024, "command_kb": st["command_bytes"] / 1024,
            "path_cache_rebuilds": st["path_cache_rebuilds"], "expand_fills": st["expand_fills"], "expand_strokes": st["expand_strokes"],
            "transient_acquires": st["transient_acquires"], "transient_reuses": st["transient_reuses"], "transient_scan_steps": st["transient_scan_steps"],
            "clip_active_scans": st["clip_active_scans"], "clip_active_steps": st["clip_active_steps"],
            "allocs_per_frame": rec["record_allocs"], "reallocs_per_frame": rec["record_reallocs"], "alloc_bytes_per_frame": rec["record_alloc_bytes"],
            "allocs_path_build": rec["path_build_allocs"],
            "femtovg_record_ms_mac": rec["femtovg_record_ms"], "path_build_ms_mac": rec["path_build_ms"],
            "encode_ms_mac_wgpu": rec["encode_ms"], "gpu_ms_mac_metal": rec["gpu_ms"],
            "heap_live_mb": rec["heap_live_after_frame"] / 2**20, "heap_peak_record_mb": rec["heap_peak_record"] / 2**20,
            "rss_mac_mb": rec["rss_end_kb"] / 1024, "rss_mac_after_device_mb": rec["rss_after_device_kb"] / 1024,
            "time_maxrss_mb": (rec["time_maxrss_bytes"] or 0) / 2**20,
        },
        "model": m, "gpu_mem_model_mb": gpu_mem_mb(rec),
        "verdict_central": verdict(m["central"]["frame_ms_best"]),
        "verdict_pessimistic": verdict(m["high"]["frame_ms_worst"]),
        "verdict_optimistic": verdict(m["low"]["frame_ms_best"]),
    })
json.dump({"assumptions": A, "assumption_order": ORDER, "rows": rows}, open(f"{S}/pz/model.json", "w"), indent=1)

def md_table(headers, lines):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in lines]
    return "\n".join(out)

with open(f"{S}/pz/measurements.md", "w") as f:
    f.write("# Measured per frame (this Mac: Apple M4 Max, wgpu/Metal, release build, median of frames 2-6)\n\n")
    f.write("Columns: commands; layers begun; clip_path calls; full-target stencil quads (1 per ClipReset + 2 per ClipFill) and their Mpx; pixels touched = color + stencil + filter + clear fragments (Mpx); "
            "tile store/load = render-target areas stored/loaded at pass boundaries (Mpx); blur passes; transient MB held at flush; vertex KB; heap allocations during "
            "recording (path-build share in parentheses: usvg->Path conversion, harness work); femtovg record CPU ms (Mac, excluding that conversion); "
            "wgpu encode ms (Mac); GPU submit+wait ms (Mac, Metal); Rust heap live MB; RSS at end (Mac, includes Metal residency).\n\n")
    for framing in ["640x480", "1080p"]:
        for setname in ["icons", "busey"]:
            f.write(f"## {setname} @ {framing}\n\n")
            lines = []
            for r in rows:
                if r["framing"] != framing or r["set"] != setname: continue
                m = r["measured"]
                lines.append([r["file"], int(m["commands"]), int(m["layers"]), int(m["clip_path_calls"]), int(m["full_target_stencil_quads"]),
                              f'{m["full_target_stencil_mpx"]:.1f}', f'{m["pixels_touched_mpx"]:.1f}', f'{m["tile_store_mpx"]:.0f}/{m["tile_load_mpx"]:.0f}',
                              int(m["blur_filters"]), f'{m["transient_mb"]:.1f}', f'{m["vert_kb"]:.0f}',
                              f'{int(m["allocs_per_frame"])} ({int(m["allocs_path_build"])})',
                              f'{m["femtovg_record_ms_mac"]:.3f}', f'{m["encode_ms_mac_wgpu"]:.2f}', f'{m["gpu_ms_mac_metal"]:.2f}',
                              f'{m["heap_live_mb"]:.2f}', f'{m["rss_mac_mb"]:.0f}'])
            f.write(md_table(["file", "cmds", "layers", "clips", "FT stencil quads", "FT stencil Mpx", "px touched Mpx", "tile st/ld Mpx", "blurs",
                              "transient MB", "vert KB", "allocs (path build)", "record ms", "encode ms", "gpu ms", "heap MB", "RSS MB"], lines))
            f.write("\n\n")

with open(f"{S}/pz/model.md", "w") as f:
    f.write("# Pi Zero model (ARM11 1 GHz, VideoCore IV GLES2, 1.5 GB/s shared)\n\n")
    f.write("Modelled, not measured. Inputs are the measured per-frame counts in measurements.md; rates and factors are the assumptions below. "
            "`frame best` = max(CPU, GPU) (perfect overlap), `frame worst` = CPU + GPU (synchronous driver). Verdicts use the central assumptions and the best-case overlap; "
            "the pessimistic verdict uses the slow-end assumptions without overlap. GPU mem = image texels + a stencil attachment per image target + screen buffers + blur scratch + vertex buffer.\n\n")
    f.write("## Assumptions (central, optimistic, pessimistic)\n\n")
    f.write(md_table(["parameter", "central", "optimistic", "pessimistic"], [[k, *v] for k, v in A.items()]))
    f.write("\n\n")
    for framing in ["640x480", "1080p"]:
        for setname in ["icons", "busey"]:
            f.write(f"## {setname} @ {framing}\n\n")
            lines = []
            for r in rows:
                if r["framing"] != framing or r["set"] != setname: continue
                c = r["model"]["central"]; lo = r["model"]["low"]; hi = r["model"]["high"]
                lines.append([r["file"], f'{c["gpu_frag_ms"]:.1f}', f'{c["tile_ms"]:.1f}', f'{c["gpu_ms"]:.1f}',
                              f'{c["cpu_record_ms"]:.1f}', int(c["draw_calls"]), f'{c["cpu_gl_ms"]:.1f}', f'{c["cpu_ms"]:.1f}',
                              f'{c["frame_ms_best"]:.0f} ({lo["frame_ms_best"]:.0f}-{hi["frame_ms_worst"]:.0f})',
                              r["verdict_central"], r["verdict_pessimistic"], f'{r["gpu_mem_model_mb"]["total_mb"]:.0f}'])
            f.write(md_table(["file", "GPU frag ms", "GPU tile ms", "GPU ms", "CPU record ms", "draw calls", "CPU GL ms", "CPU ms",
                              "frame ms (range)", "verdict", "pessimistic", "GPU mem MB"], lines))
            f.write("\n\n")
    f.write("## Summary\n\n")
    for framing in ["640x480", "1080p"]:
        for setname in ["icons", "busey"]:
            sub = [r for r in rows if r["framing"] == framing and r["set"] == setname]
            v = {}
            for r in sub: v[r["verdict_central"]] = v.get(r["verdict_central"], 0) + 1
            best = statistics.median(r["model"]["central"]["frame_ms_best"] for r in sub)
            f.write(f"- {setname} @ {framing}: median frame {best:.0f} ms (central, overlapped); verdicts: {v}\n")
print("model written")
