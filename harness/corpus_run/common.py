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
# "build#n" repeats a build under its own label, for run-to-run spread.
for _b in list(BUILDS):
    for _i in (2, 3):
        BUILDS[f'{_b}#{_i}'] = BUILDS[_b]
SWEEP_ENV = {'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'LAYER_STATS': '1'}


def files():
    return json.load(open(f'{OUT}/files.json'))


def ref_png(browser, key, framing):
    return f'{REFS}/{browser}_{key}_{framing}.png'
