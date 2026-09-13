# `sample` profiles of the harness main thread (release build, 640x480, 1 ms sampling over 12 s)

Inclusive sample counts of the outermost matching frames in the main thread. Rows indented under a phase are a percentage of that phase's samples; phase rows are a percentage of all main-thread samples. Frames rendered: Tiger 3000, gpt-6-astra 400, qwen3-8-2-4t-a95b 250. The recording phase includes the harness's usvg->Path conversion (first indented row), which an application that keeps its Paths would not pay.

| frame | Ghostscript_Tiger | gpt-6-astra | qwen3-8-2-4t-a95b |
|---|---|---|---|
| main-thread samples | 4838 | 6994 | 6939 |
| recording = draw_nodes (femtovg recording + harness usvg->Path conversion) | 576 (12%) | 179 (3%) | 96 (1%) |
|   harness: usvg segment iteration + Path building (tiny_skia_path, Path::bezier_to/line_to/move_to/close/rect) | 46 (8%) | 13 (7%) | 5 (5%) |
|   fill_path_internal (inclusive) | 357 (62%) | 53 (30%) | 36 (38%) |
|   stroke_path_internal (inclusive) | 40 (7%) | 57 (32%) | 14 (15%) |
|   PathCache::new = Path::cache rebuild (flatten + transform) | 142 (25%) | 34 (19%) | 15 (16%) |
|     tesselate_bezier | 103 (18%) | 21 (12%) | 9 (9%) |
|   expand_fill (inclusive, incl. calculate_joins) | 175 (30%) | 29 (16%) | 19 (20%) |
|   expand_stroke (inclusive, incl. calculate_joins) | 24 (4%) | 29 (16%) | 10 (10%) |
|   calculate_joins (self+children, from either expand) | 48 (8%) | 12 (7%) | 7 (7%) |
|   Params::new | 3 (1%) | 2 (1%) | 3 (3%) |
|   append_cmd + every Vec regrowth in recording (RawVec::grow/finish_grow: verts, contours, points; the command Vec regrowth is already removed by patch 05 in this binary) | 132 (23%) | 39 (22%) | 21 (22%) |
|   clip_path (inclusive) | 0 (0%) | 6 (3%) | 2 (2%) |
|   restore/pop_clips_to/replay_clip_stack | 0 (0%) | 2 (1%) | 0 (0%) |
|   begin_layer (inclusive) | 0 (0%) | 6 (3%) | 11 (11%) |
|   end_layer (inclusive: chain, mask, composite) | 0 (0%) | 20 (11%) | 15 (16%) |
|     filter_image_chain | 0 (0%) | 0 (0%) | 3 (3%) |
|     apply_layer_mask | 0 (0%) | 0 (0%) | 0 (0%) |
|   render_shadow (inclusive) | 0 (0%) | 0 (0%) | 0 (0%) |
|   acquire_transient_image / TransientPool::acquire | 0 (0%) | 9 (5%) | 13 (14%) |
|   ImageStore::info / SlotMap get | 0 (0%) | 0 (0%) | 0 (0%) |
|   allocator (malloc/free/realloc) anywhere in recording | 158 (27%) | 43 (24%) | 18 (19%) |
|   hashing (SipHash/DefaultHasher/hash_one) in recording | 16 (3%) | 3 (2%) | 7 (7%) |
|   Transform2D::cache_key | 2 (0%) | 1 (1%) | 0 (0%) |
| encode = flush_to_output (wgpu command encoding) | 1188 (25%) | 2827 (40%) | 2592 (37%) |
|   hashing in encode (pipeline/bind-group cache) | 147 (12%) | 54 (2%) | 34 (1%) |
|   allocator in encode | 58 (5%) | 452 (16%) | 402 (16%) |
| GPU wait = queue.submit + device.poll | 3044 (63%) | 3965 (57%) | 4236 (61%) |
