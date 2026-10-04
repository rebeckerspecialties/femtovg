#!/usr/bin/env python3
"""The skin-texture noise of gpt-5-6-sol-pro beside the face at 4x, and the group shadow it sits in
(shadow-merge-2026-10-04.md). Writes the ablation SVGs, renders them with the harness builds and both
browsers, and prints the tables.

  run.py all TAG...        variants, renders and report for the builds _logos_full_TAG
  run.py variants | render TAG... | report TAG... | probes TAG...

Environment: SHADOW_MERGE_OUT (default ./shadow-merge-run), HARNESS_BIN (the directory of the
_logos_full_TAG binaries, default ../bin beside the demo-assets worktree), CHROMIUM, FIREFOX
(the browsers, defaults as in corpus_run/common.py).

The window is rows 185-255, columns 0-22 of the 460x260 frame: the dark background left of the
face, below the ear, inside the skin filter's region and outside the face. The overlay is a frame
minus the frame of the same file with the face's filter attribute removed (on both sides; the
harness's NO_TURBULENCE=1 renders that file bit-identically)."""
import os, re, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HARN = os.path.dirname(HERE)
DA = os.path.dirname(HARN)
OUT = os.path.abspath(os.environ.get('SHADOW_MERGE_OUT', 'shadow-merge-run'))
BIN = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(DA), 'bin'))
CHR = os.environ.get('CHROMIUM', os.path.expanduser(
    '~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell'))
FF = os.environ.get('FIREFOX', '/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox')
SOURCE = f'{DA}/corpus/buseybench/gpt-5-6-sol-pro.svg'
DEFAULT = {'FRAME_W': '460', 'FRAME_H': '260', 'BOX': '200', 'BOX_X': '130', 'BOX_Y': '30'}
# The same root mapping shifted by (60, 60): the shadow's sources past the frame's edges are in view.
MARGIN = {'FRAME_W': '580', 'FRAME_H': '380', 'BOX': '200', 'BOX_X': '190', 'BOX_Y': '90', 'PIVOT': '290,190'}
SWEEP_ENV = {'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'TRANSIENT_BUDGET_MB': '1024'}
WINDOW = (slice(185, 256), slice(0, 23))
SHADOW_OPEN = '<filter id="shadow" x="-30%" y="-30%" width="160%" height="170%">'
FACE_FILTER = ' filter="url(#skinTexture)"'


def variants():
    os.makedirs(f'{OUT}/svg', exist_ok=True)
    s = open(SOURCE).read()
    face = re.search(r'<path d="M330 242C371 178[^>]*filter="url\(#skinTexture\)"/>', s).group(0)
    head = s[:s.find('</defs>') + len('</defs>')]
    group = s.find('<g filter="url(#shadow)">\n    <path d="M382 744')
    no_shadow = s[:group] + '<g>' + s[group + len('<g filter="url(#shadow)">'):]
    srgb_shadow = s.replace(SHADOW_OPEN, SHADOW_OPEN[:-1] + ' color-interpolation-filters="sRGB">')
    alone = lambda bg: f'{head}\n  <rect width="1024" height="1024" fill="{bg}"/>\n  {face}\n</svg>\n'
    in_group = f'{head}\n  <rect width="1024" height="1024" fill="#182b3b"/>\n  <g filter="url(#shadow)">\n    {face}\n  </g>\n</svg>\n'
    docs = {
        'sol': s,
        'sol_noshadow': no_shadow,
        'sol_shsrgb': srgb_shadow,
        'face_alone': alone('#182b3b'),
        'face_shadow': in_group,
        'face_shadow_shsrgb': in_group.replace(SHADOW_OPEN, SHADOW_OPEN[:-1] + ' color-interpolation-filters="sRGB">'),
    }
    for name, text in list(docs.items()):
        assert text.count(FACE_FILTER) == 1, name
        docs[name + '_nofilter'] = text.replace(FACE_FILTER, '', 1)
    docs['face_alone_bk'] = alone('#000')
    docs['face_alone_wh'] = alone('#fff')
    d = re.search(r'd="([^"]*)"', face).group(1)
    docs['face_mask'] = f'{head}\n  <rect width="1024" height="1024" fill="#000"/>\n  <path d="{d}" fill="#fff"/>\n</svg>\n'
    for name, text in docs.items():
        open(f'{OUT}/svg/{name}.svg', 'w').write(text)
    return sorted(docs)


MODEL_INPUTS = ['face_mask', 'face_alone_bk', 'face_alone_wh', 'face_alone', 'face_alone_nofilter', 'face_shadow',
                'face_shadow_nofilter']


def browser(kind, svg, png, frame):
    if os.path.exists(png):
        return
    r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', svg, '4'], capture_output=True, text=True, env={**os.environ, **frame})
    fd, html = tempfile.mkstemp(suffix='.html', dir=OUT)
    os.close(fd)
    open(html, 'w').write(r.stdout)
    size = f'--window-size={frame["FRAME_W"]},{frame["FRAME_H"]}'
    try:
        if kind == 'chr':
            sandbox = ['--no-sandbox'] if hasattr(os, 'geteuid') and os.geteuid() == 0 else []
            subprocess.run([CHR, *sandbox, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                            size, '--default-background-color=FFFFFFFF', f'--screenshot={png}', f'file://{html}'],
                           capture_output=True, timeout=300)
        else:
            prof = tempfile.mkdtemp(prefix='ffprof')
            subprocess.run([FF, '--headless', '--no-remote', '--profile', prof, size, '--screenshot', png, f'file://{html}'],
                           capture_output=True, timeout=300)
            shutil.rmtree(prof, ignore_errors=True)
    finally:
        os.remove(html)
    im = Image.open(png).convert('RGB')
    w, h = int(frame['FRAME_W']), int(frame['FRAME_H'])
    im.crop((0, 0, w, h)).save(png)


def render(tags):
    names = variants()
    for sub, frame, which in (('z4', DEFAULT, names), ('m60', MARGIN, MODEL_INPUTS)):
        os.makedirs(f'{OUT}/{sub}', exist_ok=True)
        for name in which:
            svg = f'{OUT}/svg/{name}.svg'
            for kind in ('chr', 'ff'):
                browser(kind, svg, f'{OUT}/{sub}/{kind}_{name}.png', frame)
            for tag in tags:
                ppm = f'{OUT}/{sub}/{tag}_{name}.ppm'
                if not os.path.exists(ppm):
                    subprocess.run([f'{BIN}/_logos_full_{tag}', '4', ppm, svg], check=True, capture_output=True,
                                   env={**os.environ, **frame, **SWEEP_ENV})


def load(sub, renderer, name):
    for ext in ('png', 'ppm'):
        p = f'{OUT}/{sub}/{renderer}_{name}.{ext}'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=float)
    raise FileNotFoundError(f'{OUT}/{sub}/{renderer}_{name}')


def overlay(renderer, name, sub='z4', window=WINDOW):
    return (load(sub, renderer, name) - load(sub, renderer, name + '_nofilter'))[window][..., 1]


def report(tags):
    sys.path.insert(0, HERE)
    from refnoise import faint, frame_noise, srgb, to_rgba
    import model
    grey, alpha = faint(to_rgba(frame_noise(offset=0.5)))
    colour = 255 * srgb(grey)
    renderers = list(tags) + ['chr', 'ff']
    print('Noise overlay in the window, green channel, mean. no-shadow ref: the spec arithmetic for the noise alone over\n'
          'the frame without it (no shadow modelled; it applies to the rows without the shadow group)')
    rows = [('full file', 'sol'), ('full file, no shadow filter', 'sol_noshadow'),
            ('full file, shadow filter in sRGB', 'sol_shsrgb'), ('face alone', 'face_alone'),
            ('face alone in the shadow group', 'face_shadow'), ('the same, shadow filter in sRGB', 'face_shadow_shsrgb')]
    print(f'{"variant":34s} ' + ' '.join(f'{r:>9s}' for r in renderers) + '  no-shadow ref')
    for label, name in rows:
        base = load('z4', 'chr', name + '_nofilter')[WINDOW][..., 1]
        ref = (alpha[WINDOW] * (colour[WINDOW] - base)).mean()
        print(f'{label:34s} ' + ' '.join(f'{overlay(r, name).mean():9.2f}' for r in renderers) + f'  {ref:9.2f}')
    c = overlay('chr', 'sol')
    for r in list(tags) + ['ff']:
        o = overlay(r, 'sol')
        print(f'pattern correlation with Chromium, full file: {r} {np.corrcoef(o.ravel(), c.ravel())[0, 1]:.3f}')
    print('\nThe face in the shadow group against the two merge models, each renderer with its own noise and coverage')
    print(f'{"renderer":9s} {"measured":>9s} {"sRGB merge":>11s} {"linearRGB":>10s}')
    for r in renderers:
        srgb_o, lin_o = model.predict(lambda name: load('m60', r, name))
        meas = (load('m60', r, 'face_shadow') - load('m60', r, 'face_shadow_nofilter'))[model.WINDOW][..., 1]
        print(f'{r:9s} {meas.mean():9.2f} {srgb_o[model.WINDOW][..., 1].mean():11.2f} {lin_o[model.WINDOW][..., 1].mean():10.2f}')


def probes(tags):
    """The swatches of corpus/shadow-merge/linear-merge-swatches.svg at 1x: opaque greys (sRGB 3..64) and
    rgb(200) at fill-opacity .02..58 over their own shadow, as each renderer draws them."""
    svg = f'{DA}/corpus/shadow-merge/linear-merge-swatches.svg'
    os.makedirs(f'{OUT}/probe', exist_ok=True)
    frames = {}
    for kind in ('chr', 'ff'):
        png = f'{OUT}/probe/{kind}.png'
        if not os.path.exists(png):
            r = subprocess.run([sys.executable, f'{HARN}/make_ref.py', svg, '1'], capture_output=True, text=True, env={**os.environ, **DEFAULT})
            open(f'{OUT}/probe/page.html', 'w').write(r.stdout)
            sandbox = ['--no-sandbox'] if hasattr(os, 'geteuid') and os.geteuid() == 0 else []
            if kind == 'chr':
                subprocess.run([CHR, *sandbox, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                                '--window-size=460,260', '--default-background-color=FFFFFFFF', f'--screenshot={png}',
                                f'file://{OUT}/probe/page.html'], capture_output=True, timeout=300)
            else:
                prof = tempfile.mkdtemp(prefix='ffprof')
                subprocess.run([FF, '--headless', '--no-remote', '--profile', prof, '--window-size=460,260', '--screenshot', png,
                                f'file://{OUT}/probe/page.html'], capture_output=True, timeout=300)
                shutil.rmtree(prof, ignore_errors=True)
        frames[kind] = np.asarray(Image.open(png).convert('RGB'), dtype=int)
    for tag in tags:
        ppm = f'{OUT}/probe/{tag}.ppm'
        subprocess.run([f'{BIN}/_logos_full_{tag}', '1', ppm, svg], check=True, capture_output=True, env={**os.environ, **DEFAULT, **SWEEP_ENV})
        frames[tag] = np.asarray(Image.open(ppm).convert('RGB'), dtype=int)
    cols = [int(130 + (50 + 60 * i) * 200 / 1024) for i in range(15)]
    for label, row in (('opaque greys 3..64', int(30 + 150 * 200 / 1024)), ('faint rgb(200) over its shadow', int(30 + 740 * 200 / 1024))):
        print(label)
        for name, im in frames.items():
            print(f'  {name:8s}', ' '.join(f'{im[row, c, 0]:3d}' for c in cols))


if __name__ == '__main__':
    cmd, tags = sys.argv[1], sys.argv[2:]
    if cmd in ('variants', 'all'):
        print(len(variants()), 'variants in', f'{OUT}/svg')
    if cmd in ('render', 'all'):
        render(tags)
    if cmd in ('report', 'all'):
        report(tags)
    if cmd in ('probes', 'all'):
        probes(tags)
