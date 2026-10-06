"""Shared pieces of the full-corpus run: paths, the file list, the four framings and the builds.

Environment:
  CORPUS_RUN_OUT  where results, references and temporaries go (default ./corpus-run)
  HARNESS_BIN     directory holding the harness binaries named _logos_full_<build>
  CHROMIUM, FIREFOX  the reference browsers
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
HARN = os.path.dirname(HERE)
DA = os.path.dirname(HARN)
OUT = os.environ.get('CORPUS_RUN_OUT', os.path.join(os.getcwd(), 'corpus-run'))
REFS = f'{OUT}/refs'
BIN = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(DA), 'bin'))
CHR = os.environ.get('CHROMIUM', os.path.expanduser(
    '~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell'))
FF = os.environ.get('FIREFOX', '/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox')

DEFAULT = {'FRAME_W': '460', 'FRAME_H': '260', 'BOX': '200', 'BOX_X': '130', 'BOX_Y': '30'}
HD = {'FRAME_W': '1920', 'FRAME_H': '1080', 'BOX': '1080', 'BOX_X': '420', 'BOX_Y': '0'}
# name -> (frame env, pivot zoom)
FRAMINGS = {'z1': (DEFAULT, 1.0), 'z2': (DEFAULT, 2.0), 'z4': (DEFAULT, 4.0), 'hd': (HD, 1.0)}
# Below the fit: the 200-unit box at a tenth, a quarter and half its size - natural size for a 20 px icon and
# up - looked up by name; the corpus scripts iterate DEFAULT_FRAMINGS unless asked for more.
FRAMINGS.update({'z01': (DEFAULT, 0.1), 'z025': (DEFAULT, 0.25), 'z05': (DEFAULT, 0.5)})
# Zooms about the top-centre band of the box (PIVOT at frame 230,48) for wide artwork that the centre pivot zooms past.
FRAMINGS.update({'zt2': ({**DEFAULT, 'PIVOT': '230,48'}, 2.0), 'zt4': ({**DEFAULT, 'PIVOT': '230,48'}, 4.0)})
DEFAULT_FRAMINGS = ['z1', 'z2', 'z4', 'hd']

# build -> (binary, extra env). Every binary is the harness built with all cfgs
# (harness_clip, harness_turbulence, harness_blend, harness_mix_blend), plus harness_slices
# on a tree that has WGPURenderer::set_submission_slicing.
BUILDS = {
    'pre369': (f'{BIN}/_logos_full_pre369', {}),    # master before the Canvas split (#369)
    'base': (f'{BIN}/_logos_full_base', {}),        # master
    'slices': (f'{BIN}/_logos_full_slices', {}),    # #368 before lazy passes, slicing on
    'noslices': (f'{BIN}/_logos_full_slices', {'NO_SLICES': '1'}),
    'lazy': (f'{BIN}/_logos_full_lazy', {'NO_SLICES': '1'}),  # the lazy-pass experiment build
    'lazy_slices': (f'{BIN}/_logos_full_lazy', {}),
    # reference only: the opt-in in-flight wait that was removed from #368 (commit 4353a15)
    'wait2': (f'{BIN}/_logos_full_wait', {'SLICE_WAIT_PAST': '2'}),
    # #368 as pushed: a pass begins with its first draw; slicing on and off
    'final': (f'{BIN}/_logos_full_final', {}),
    'final_noslices': (f'{BIN}/_logos_full_final', {'NO_SLICES': '1'}),
}
BUILDS['mm'] = (f'{BIN}/_logos_full_mm', {})  # #370, mipmaps on wgpu, on its own base
BUILDS['ab'] = (f'{BIN}/_logos_full_ab', {})  # #362 aniso-blur branch, --cfg harness_blur_xy
BUILDS['bd'] = (f'{BIN}/_logos_full_bd', {})  # #325 blur-downsample branch
BUILDS['pyr'] = (f'{BIN}/_logos_full_pyr', {})  # #325 pyramid, rebased on #372 (--cfg harness_blur_xy)
BUILDS['mo'] = (f'{BIN}/_logos_full_mo', {})  # feMorphology + feOffset, on the pyramid (--cfg harness_blur_xy --cfg harness_morph)
BUILDS['cp'] = (f'{BIN}/_logos_full_cp', {})  # chain-passes: no parity pass, fused matrices, on mo (same cfgs)
BUILDS['ca'] = (f'{BIN}/_logos_full_ca', {})  # #380: box and ellipse clips as fragment-shader coverage, a draw clipped only where the shape cuts it (clip-analytic, on master 9d574e0)
BUILDS['ca0'] = (f'{BIN}/_logos_full_ca0', {})  # #380 at f6c76d0, before the cover rule
BUILDS['cv'] = (f'{BIN}/_logos_full_cv', {})  # clip-coverage: the scissor meets a draw as a clip shape does (on #380)
BUILDS['cvf'] = (f'{BIN}/_logos_full_cvf', {'SINGLE_SHADOW_LAYER': '1'})  # #380 as extended on 2026-10-05 (ca9b192): cover rule, scissor rules, draws under a shape scissored to its reach
# filter-crop (on #375): ImageFilter::Crop after each primitive's pass (--cfg harness_crop). sr_nocrop is the same
# binary leaving the intermediate results whole, and cp_h is #375 with the same harness.
BUILDS['sr'] = (f'{BIN}/_logos_full_sr', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['sr_nocrop'] = (f'{BIN}/_logos_full_sr', {'SINGLE_SHADOW_LAYER': '1', 'NO_CROP': '1'})
BUILDS['cp_h'] = (f'{BIN}/_logos_full_cp_h', {'SINGLE_SHADOW_LAYER': '1'})
# Experiment: cvf with the flattening tolerance from FEMTOVG_TESS_TOL (0.25 is the library's): the sum of a cubic's
# control distances from its chord is kept under the tolerance's square root, in device pixels.
for _t in ('0.25', '0.0625', '0.015625'):
    BUILDS[f'tt_{_t}'] = (f'{BIN}/_logos_full_tt', {'SINGLE_SHADOW_LAYER': '1', 'FEMTOVG_TESS_TOL': _t})
# #380 with every clipped group drawn into a layer that the clip cuts once (CLIP_GROUP_LAYERS), sized to the group.
BUILDS['cgl'] = (f'{BIN}/_logos_full_cgl', {'SINGLE_SHADOW_LAYER': '1', 'CLIP_GROUP_LAYERS': '1', 'LAYER_BBOX_SCISSOR': '1'})
BUILDS['cgl_off'] = (f'{BIN}/_logos_full_cgl', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['cvh'] = (f'{BIN}/_logos_full_cvh', {'SINGLE_SHADOW_LAYER': '1'})  # experiment (branch clip-twins): #380 and a draw held by the points of its outline (a rounded or turned twin of the clip is not clipped)
BUILDS['cvg'] = (f'{BIN}/_logos_full_cvg', {'SINGLE_SHADOW_LAYER': '1'})  # experiment (branch clip-corner-area): #380 with a round corner's coverage as the area a slanted edge leaves of the pixel
BUILDS['all'] = (f'{BIN}/_logos_full_all', {'SINGLE_SHADOW_LAYER': '1'})  # the trial merge of clip-coverage (masks, on #380) and filter-crop (on #375), every cfg
# Builds with corpus_run/pass_count.py applied to the tree (--cfg harness_pass_count): `passes=` counts render passes.
BUILDS['pc_cp'] = (f'{BIN}/_logos_full_pc_cp', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['pc_sr'] = (f'{BIN}/_logos_full_pc_sr', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['pc_sr_nocrop'] = (f'{BIN}/_logos_full_pc_sr', {'SINGLE_SHADOW_LAYER': '1', 'NO_CROP': '1'})
BUILDS['cve'] = (f'{BIN}/_logos_full_cve', {'SINGLE_SHADOW_LAYER': '1'})  # #380 as pushed on 2026-10-05 (131597f); renders as cvf, whose frames stand for it
BUILDS['flat'] = (f'{BIN}/_logos_full_flat', {'SINGLE_SHADOW_LAYER': '1'})  # branch finer-flattening (on master 9d574e0): curves flattened four times finer. Not `ff`: that prefix is Firefox's frames
BUILDS['master_h'] = (f'{BIN}/_logos_full_master_h', {'SINGLE_SHADOW_LAYER': '1'})  # upstream master 9d574e0 with the harness the cv* builds of 2026-10-05 were made with
# clip-coverage with masks: path clips as CPU-rasterized coverage masks, clipPath children unioned (Canvas::clip_paths,
# --cfg harness_clip_paths). cm_stencil is the same binary with no mask budget and the children joined: the scissor
# rules alone. SINGLE_SHADOW_LAYER keeps the group-shadow mapping the earlier builds were made with.
BUILDS['cm'] = (f'{BIN}/_logos_full_cm', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['cm_stencil'] = (f'{BIN}/_logos_full_cm', {'SINGLE_SHADOW_LAYER': '1', 'CLIP_MASK_BUDGET_MB': '0', 'CLIP_JOINED': '1'})
BUILDS['cmn'] = (f'{BIN}/_logos_full_cmn', {'SINGLE_SHADOW_LAYER': '1'})  # masks without the scissor to a mask's bounds (e936fe0)
BUILDS['tf'] = (f'{BIN}/_logos_full_tf', {})  # #358 draft: exact-coverage fills on wgpu (thin-fills ec67485, on #356; clip/turbulence/blend cfgs)
BUILDS['master'] = (f'{BIN}/_logos_full_master', {})  # upstream master 9d574e0 (#372, #373, #374 merged), harness of 2026-10-04 (noise clamp fix)
BUILDS['master_128'] = (f'{BIN}/_logos_full_master', {'TRANSIENT_BUDGET_MB': '128'})  # master at the library's default transient-image budget
BUILDS['master_lsm'] = (f'{BIN}/_logos_full_master_lsm', {})  # upstream master 9d574e0, harness merging a group shadow in linearRGB (shadow-merge-2026-10-04.md)
BUILDS['master_lsm_single'] = (f'{BIN}/_logos_full_master_lsm', {'SINGLE_SHADOW_LAYER': '1'})  # the same binary with the previous shadow mapping, as 'master'
BUILDS['cp_128'] = (f'{BIN}/_logos_full_cp', {'TRANSIENT_BUDGET_MB': '128'})  # #375 at the default budget
BUILDS['moh'] = (f'{BIN}/_logos_full_moh', {})  # mo with the 2026-10-03 harness: filter parameters through the element transform, all-or-nothing chains, offset-first shadows
BUILDS['moh_partial'] = (f'{BIN}/_logos_full_moh', {'PARTIAL_CHAINS': '1'})  # the same binary with the partial-chain policy of before
# "build#n" repeats a build under its own label, for run-to-run spread.
# #368 with corpus_run/pass_report.patch applied: one PASSREPORT line per frame
BUILDS['report'] = (f'{BIN}/_logos_full_report', {'FEMTOVG_PASS_REPORT': '1', 'NO_SLICES': '1'})
# femtovg against a local wgpu checkout: trunk dd033bfb7, and gfx-rs/wgpu#10506 (aedebc002) merged with it
BUILDS['wgpu_trunk'] = (f'{BIN}/_logos_full_wt_master', {})           # femtovg master
BUILDS['wgpu_pr'] = (f'{BIN}/_logos_full_wp_master', {})              # femtovg master
BUILDS['wgpu_trunk_368'] = (f'{BIN}/_logos_full_wt_pr368', {})        # femtovg #368, slicing on
BUILDS['wgpu_pr_368'] = (f'{BIN}/_logos_full_wp_pr368', {})           # femtovg #368, slicing on
BUILDS['wgpu_pr_368_noslices'] = (f'{BIN}/_logos_full_wp_pr368', {'NO_SLICES': '1'})
# Experiment (harness FILL_MASKS, femtovg/femtovg#327): fills whose mean width on the target is under T pixels drawn as
# their bounds under the path as a clip, which clip-coverage takes as a coverage mask. cmx is clip-coverage with the
# harness that has the switch (renders as cm without it); cmf the same tree with curves flattened four times finer.
BUILDS['cmx'] = (f'{BIN}/_logos_full_cmx', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['cmf'] = (f'{BIN}/_logos_full_cmf', {'SINGLE_SHADOW_LAYER': '1'})
for _t in ('0.5', '1', '1.5', '2', '3'):
    BUILDS[f'fm{_t}'] = (f'{BIN}/_logos_full_cmx', {'SINGLE_SHADOW_LAYER': '1', 'FILL_MASKS': _t})
    BUILDS[f'fmf{_t}'] = (f'{BIN}/_logos_full_cmf', {'SINGLE_SHADOW_LAYER': '1', 'FILL_MASKS': _t})
# The same switch gating on size alone, as Skia Graphite's small-path atlas does (Device::chooseRenderer: "Small paths
# are rasterized on the CPU for higher quality"): every fill whose bounds span at most N x N pixels.
for _n in (32, 64, 128):
    BUILDS[f'fms{_n}'] = (f'{BIN}/_logos_full_cmx', {'SINGLE_SHADOW_LAYER': '1', 'FILL_MASKS': '1e9', 'FILL_MASKS_MAX': str(_n * _n)})
    BUILDS[f'fmfs{_n}'] = (f'{BIN}/_logos_full_cmf', {'SINGLE_SHADOW_LAYER': '1', 'FILL_MASKS': '1e9', 'FILL_MASKS_MAX': str(_n * _n)})

# The crop PR against the master it now sits on: mstr is upstream master 485c665 (#375 and #370 merged), crp the
# merged filter-crop branch (5b6e8e3, --cfg harness_crop); pc_* the same trees with pass_count.py applied.
BUILDS['mstr'] = (f'{BIN}/_logos_full_mstr', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['crp'] = (f'{BIN}/_logos_full_crp', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['crp_nocrop'] = (f'{BIN}/_logos_full_crp', {'SINGLE_SHADOW_LAYER': '1', 'NO_CROP': '1'})
BUILDS['pc_mstr'] = (f'{BIN}/_logos_full_pc_mstr', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['pc_crp'] = (f'{BIN}/_logos_full_pc_crp', {'SINGLE_SHADOW_LAYER': '1'})

# 2026-10-06: #380 at 74776e0 (master 485c665 merged in by Matt); m6 is master 6dd5543, whose library is 485c665's.
# Both built without debug info (CARGO_PROFILE_RELEASE_DEBUG=0), as a pair for timing.
BUILDS['c380'] = (f'{BIN}/_logos_full_c380', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['m6'] = (f'{BIN}/_logos_full_m6', {'SINGLE_SHADOW_LAYER': '1'})
BUILDS['m6f'] = (f'{BIN}/_logos_full_m6f', {'SINGLE_SHADOW_LAYER': '1'})  # finer-flattening (7f59edb, master 6dd5543 merged in)
BUILDS['c380f'] = (f'{BIN}/_logos_full_c380f', {'SINGLE_SHADOW_LAYER': '1'})  # c380 and the finer-flattening commit (e66f057)
BUILDS['c380x'] = (f'{BIN}/_logos_full_c380x', {'SINGLE_SHADOW_LAYER': '1'})  # experiment: c380 with cuts (a rect clip that cuts a rounded shape, and paths rounded on one side, clip beside it in the scissor's place)

# A build's frames are kept as TAG_KEY_FRAMING.png, the references as PREFIX_KEY_FRAMING.png: a tag must not be a prefix.
assert not set(BUILDS) & {'chr', 'chg', 'ff', 'wk', 'id'}, 'a build is named as a reference'
for _b in list(BUILDS):
    for _i in (2, 3):
        BUILDS[f'{_b}#{_i}'] = BUILDS[_b]
# TRANSIENT_BUDGET_MB lifts the library's 128 MiB default: a conformance run measures rendering, and at 1080p the
# layer-heavy portraits need up to 179 MiB (about 23 frames' worth at any size), so under the default seven frames
# lost layers. The *_128 builds below keep the default, for what it costs.
SWEEP_ENV = {'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'LAYER_STATS': '1', 'TRANSIENT_BUDGET_MB': '1024'}


def files():
    return json.load(open(f'{OUT}/files.json'))


def ref_png(browser, key, framing):
    return f'{REFS}/{browser}_{key}_{framing}.png'
