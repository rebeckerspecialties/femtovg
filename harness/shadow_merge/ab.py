#!/usr/bin/env python3
"""A/B of two harness builds on the corpus files that use feTurbulence (or a list of files), at the
corpus-run framings, against Chromium (software raster) and Firefox references made with make_ref.py.

  ab.py OUT_JSON [builds=BEFORE,AFTER] [framings=z1,z2,z4,hd] [list=FILES.json] [files=name,name]
  ab.py --summary OUT_JSON [BEFORE AFTER]

Metrics per frame, as harness/compare.py computes them: % of pixels with max-channel delta > 20,
the same after a 2-px erosion (structural), % > 8, and the mean max-channel delta; plus the share of
pixels the two builds differ on. Environment: SHADOW_MERGE_OUT (references and frames, default
./shadow-merge-run/corpus), HARNESS_BIN, CHROMIUM, FIREFOX as for run.py."""
import glob, json, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DA = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.path.abspath(os.environ.get('SHADOW_MERGE_OUT', 'shadow-merge-run')), 'corpus')
REFS = f'{OUT}/refs'
BIN = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(DA), 'bin'))
CHR = os.environ.get('CHROMIUM', os.path.expanduser(
    '~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell'))
FF = os.environ.get('FIREFOX', '/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox')
SANDBOX = ['--no-sandbox'] if hasattr(os, 'geteuid') and os.geteuid() == 0 else []
DEFAULT = {'FRAME_W': '460', 'FRAME_H': '260', 'BOX': '200', 'BOX_X': '130', 'BOX_Y': '30'}
HD = {'FRAME_W': '1920', 'FRAME_H': '1080', 'BOX': '1080', 'BOX_X': '420', 'BOX_Y': '0'}
FRAMINGS = {'z1': (DEFAULT, 1.0), 'z2': (DEFAULT, 2.0), 'z4': (DEFAULT, 4.0), 'hd': (HD, 1.0)}
SWEEP_ENV = {'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'TRANSIENT_BUDGET_MB': '1024'}


def turbulence_files():
    out = []
    for p in sorted(glob.glob(f'{DA}/corpus/**/*.svg', recursive=True)):
        if '<feTurbulence' in open(p, errors='replace').read():
            out.append(p)
    return out


def key(path):
    return os.path.relpath(path, DA)[:-4].replace('/', '__')


def page(path, framing):
    fr, z = FRAMINGS[framing]
    r = subprocess.run([sys.executable, f'{DA}/harness/make_ref.py', path, str(z)], capture_output=True, text=True,
                       env={**os.environ, **fr})
    fd, html = tempfile.mkstemp(suffix='.html', dir=REFS)
    os.close(fd)
    open(html, 'w').write(r.stdout)
    return html


def crop(png, fr):
    w, h = int(fr['FRAME_W']), int(fr['FRAME_H'])
    im = Image.open(png).convert('RGB')
    if im.size != (w, h):
        im.crop((0, 0, w, h)).save(png)


def chromium(job):
    path, framing = job
    png = f'{REFS}/chr_{key(path)}_{framing}.png'
    if os.path.exists(png):
        return png
    fr, _ = FRAMINGS[framing]
    html = page(path, framing)
    subprocess.run([CHR, *SANDBOX, '--headless', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                    f'--window-size={fr["FRAME_W"]},{fr["FRAME_H"]}', '--default-background-color=FFFFFFFF',
                    f'--screenshot={png}', f'file://{html}'], capture_output=True, timeout=300)
    os.remove(html)
    crop(png, fr)
    return png


def firefox(job):
    path, framing = job
    png = f'{REFS}/ff_{key(path)}_{framing}.png'
    if os.path.exists(png):
        return png
    fr, _ = FRAMINGS[framing]
    html = page(path, framing)
    prof = tempfile.mkdtemp(prefix='ffprof')
    try:
        for _ in range(2):
            try:
                subprocess.run([FF, '--headless', '--no-remote', '--profile', prof, f'--window-size={fr["FRAME_W"]},{fr["FRAME_H"]}',
                                '--screenshot', png, f'file://{html}'], capture_output=True, timeout=300)
            except subprocess.TimeoutExpired:
                pass
            if os.path.exists(png):
                break
    finally:
        shutil.rmtree(prof, ignore_errors=True)
        os.remove(html)
    crop(png, fr)
    return png


def femtovg(job):
    build, path, framing = job
    out = f'{OUT}/{build}/{key(path)}_{framing}.ppm'
    if os.path.exists(out):
        return out
    fr, z = FRAMINGS[framing]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([f'{BIN}/_logos_full_{build}', str(z), out, path], capture_output=True, timeout=600,
                   env={**os.environ, **fr, **SWEEP_ENV})
    return out


def erode(m, it=2):
    for _ in range(it):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def metrics(a_path, b_path):
    a = np.asarray(Image.open(a_path).convert('RGB'), dtype=int)
    b = np.asarray(Image.open(b_path).convert('RGB'), dtype=int)
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    d = np.abs(a[:h, :w] - b[:h, :w]).max(axis=2)
    m = d > 20
    return {'px20': 100 * m.mean(), 'struct': 100 * erode(m).mean(), 'px8': 100 * (d > 8).mean(), 'mean': float(d.mean())}


def summary(path, b0, b1):
    rows = json.load(open(path))
    print(f'{"file":36s} {"fr":3s} {"chg%":>6s} | vs Chromium px>20, structural, px>8, mean | vs Firefox px>8, mean | Chromium-Firefox px>8, mean')
    for r in rows:
        c0, c1, f0, f1, e = r[b0]['chr'], r[b1]['chr'], r[b0]['ff'], r[b1]['ff'], r['chr_vs_ff']
        print(f"{r['file']:36s} {r['framing']:3s} {r['changed_px']:6.2f} | {c0['px20']:5.2f}->{c1['px20']:5.2f} "
              f"{c0['struct']:5.3f}->{c1['struct']:5.3f} {c0['px8']:5.2f}->{c1['px8']:5.2f} {c0['mean']:4.2f}->{c1['mean']:4.2f} | "
              f"{f0['px8']:5.2f}->{f1['px8']:5.2f} {f0['mean']:4.2f}->{f1['mean']:4.2f} | {e['px8']:5.2f} {e['mean']:4.2f}")
    for fr in ('z1', 'z2', 'z4', 'hd'):
        sel = [r for r in rows if r['framing'] == fr]
        if not sel:
            continue
        m = lambda b, ref, k: sum(r[b][ref][k] for r in sel) / len(sel)
        print(f"mean {fr} ({len(sel)} frames): Chromium px>20 {m(b0, 'chr', 'px20'):.2f}->{m(b1, 'chr', 'px20'):.2f}, "
              f"structural {m(b0, 'chr', 'struct'):.3f}->{m(b1, 'chr', 'struct'):.3f}, px>8 {m(b0, 'chr', 'px8'):.2f}->{m(b1, 'chr', 'px8'):.2f}, "
              f"mean {m(b0, 'chr', 'mean'):.3f}->{m(b1, 'chr', 'mean'):.3f} | Firefox px>8 {m(b0, 'ff', 'px8'):.2f}->{m(b1, 'ff', 'px8'):.2f}, "
              f"mean {m(b0, 'ff', 'mean'):.3f}->{m(b1, 'ff', 'mean'):.3f} | Chromium-Firefox px>8 "
              f"{sum(r['chr_vs_ff']['px8'] for r in sel) / len(sel):.2f}")


def main():
    if sys.argv[1] == '--summary':
        summary(sys.argv[2], *(sys.argv[3:5] if len(sys.argv) > 4 else ('master', 'master_lsm')))
        return
    out_json = sys.argv[1]
    opts = dict(a.split('=', 1) for a in sys.argv[2:])
    framings = opts.get('framings', 'z1,z2,z4,hd').split(',')
    builds = opts.get('builds', 'master,master_lsm').split(',')
    files = turbulence_files()
    if 'list' in opts:
        files = [p if p.startswith('/') else f'{DA}/{p}' for p in json.load(open(opts['list']))]
    if 'files' in opts:
        want = opts['files'].split(',')
        files = [f for f in files if os.path.basename(f)[:-4] in want]
    os.makedirs(REFS, exist_ok=True)
    jobs = [(f, fr) for f in files for fr in framings]
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(chromium, jobs))
    with ThreadPoolExecutor(2) as ex:
        list(ex.map(firefox, jobs))
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(femtovg, [(b, f, fr) for b in builds for f in files for fr in framings]))
    rows = []
    for f in files:
        for fr in framings:
            row = {'file': os.path.basename(f)[:-4], 'framing': fr}
            c = f'{REFS}/chr_{key(f)}_{fr}.png'
            x = f'{REFS}/ff_{key(f)}_{fr}.png'
            row['chr_vs_ff'] = metrics(c, x)
            for b in builds:
                p = f'{OUT}/{b}/{key(f)}_{fr}.ppm'
                row[b] = {'chr': metrics(p, c), 'ff': metrics(p, x)}
            p0, p1 = (f'{OUT}/{b}/{key(f)}_{fr}.ppm' for b in builds[:2])
            row['changed_px'] = 100 * float((np.asarray(Image.open(p0)) != np.asarray(Image.open(p1))).any(-1).mean())
            rows.append(row)
    json.dump(rows, open(out_json, 'w'), indent=1)
    print(f'{len(rows)} frames -> {out_json}')


if __name__ == '__main__':
    main()
