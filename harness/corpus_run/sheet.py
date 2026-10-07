#!/usr/bin/env python3
"""Evidence sheet from a corpus run (CORPUS_RUN_OUT; frames kept with accuracy.py png=DIR, others rendered): one row per frame with
before | after | Chromium | before vs Chromium | after vs Chromium, and with --firefox the same three for Firefox.
A difference panel is white where the frame is within 8/255 of the reference, orange from 9 to 20 and red beyond.

  sheet.py OUT.png BEFORE[=label] AFTER[=label] [--firefox] [--refs=chr,chg,ff] [--diffs-only] [--others=chg,wk]
           [--range=chr,chg,ff] [--bold] ROW...

--refs names the references (refs/PREFIX_*.png): chr Chromium rasterizing in software, chg Chromium rasterizing on
the GPU (refs_gpu.py), ff Firefox, wk WebKit (refs_webkit.py), id the area reference (refs_ideal.py). --diffs-only
leaves the reference pictures out, for three references in a row. --others=chg,wk adds a panel for each of those
renderers against the first reference: what a browser at one device pixel is itself off by.
--range=chr,chg,ff adds a pair of panels for how far each build lies outside the range those references span:
where the browsers disagree among themselves a build between them is white. --bold marks a deviating pixel's eight
neighbours with it in the difference panels, so that an edge one pixel wide still shows when a whole frame is
scaled down to fit a page.

ROW is NAME:FRAMING followed by options, each after a colon:
  box=X,Y,W,H   the window, in frame pixels (default: the whole frame)
  at=CX,CY      or its center, with size=WxH (default 40x30); without either, the window sits on the pixel where
                the two builds differ furthest toward the upper right - a clip's edge
  zoom=N        magnify N times, nearest neighbour (to read an edge)
  shrink=N      or reduce N times: images box-filtered, difference panels by the block maximum, so one deviating
                pixel still shows
  after=BUILD   another build for this row's after frame (and before=BUILD), e.g. one with a budget lifted
and, after a semicolon, a note for the caption. The caption has the share of the whole frame beyond 20/255 for both
builds against each reference."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import BUILDS, FRAMINGS, SWEEP_ENV, OUT as R

NAMES = {'chr': 'Chromium 131', 'chg': 'Chromium 131 on the GPU', 'ff': 'Firefox 158', 'wk': 'WebKit (Safari 27)',
         'id': 'area reference: Chromium at 8x, averaged'}
SHORT = {'chr': 'Chromium', 'chg': 'Chromium GPU', 'ff': 'Firefox', 'wk': 'WebKit', 'id': 'the area'}
args = sys.argv[1:]
browsers = ['chr', 'ff'] if '--firefox' in args else ['chr']
for a in args:
    if a.startswith('--refs='):
        browsers = a.split('=', 1)[1].split(',')
if len(browsers) > 1 and 'chg' in browsers:
    NAMES['chr'], SHORT['chr'] = 'Chromium 131 in software', 'Chromium software'
diffs_only = '--diffs-only' in args
bold = '--bold' in args
span = next((a.split('=', 1)[1].split(',') for a in args if a.startswith('--range=')), [])
others = next((a.split('=', 1)[1].split(',') for a in args if a.startswith('--others=')), [])
args = [a for a in args if not a.startswith('--')]
out = args.pop(0)
(before, before_label), (after, after_label) = ((a.split('=', 1) + [a])[:2] for a in args[:2])
files = {f['key']: f for f in json.load(open(f'{R}/files.json'))}


def font(size, text=''):
    # Helvetica has no CJK glyphs: a caption naming such a file is set in a face that has them.
    if any(ord(c) > 0x2e7f for c in text):
        return ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', size)
    return ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size)


def frame(build, key, framing):
    # The directories accuracy.py png= was given, then the frames rendered here and by ab_refs.py.
    for d in ('png_wpt', 'png_nyt', 'png', 'png_changed'):
        p = f'{R}/{d}/{build}_{key}_{framing}.png'
        if os.path.exists(p):
            return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)
    binary, extra = BUILDS[build]
    fr, z = FRAMINGS[framing]
    os.makedirs(f'{R}/png_changed', exist_ok=True)
    ppm = p[:-4] + '.ppm'
    r = subprocess.run([binary, f'{z:g}', ppm, files[key]['path']], env={**os.environ, **fr, **SWEEP_ENV, **extra},
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not os.path.exists(ppm):
        raise SystemExit(f'no frame {build} {key} {framing}: {r.stderr[-300:]}')
    Image.open(ppm).save(p)
    os.remove(ppm)
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.int16)


def reference(browser, key, framing):
    return np.asarray(Image.open(f'{R}/refs/{browser}_{key}_{framing}.png').convert('RGB'), dtype=np.int16)


def beyond(a, b):
    return 100 * (np.abs(a - b).max(axis=2) > 20).mean()


def picture(im, box, zoom, shrink):
    x, y, w, h = box
    im = Image.fromarray(im[y:y + h, x:x + w].astype(np.uint8))
    if shrink > 1:
        return im.resize((w // shrink, h // shrink), Image.BOX)
    return im.resize((w * zoom, h * zoom), Image.NEAREST)


def outside(a, refs):
    """How far a frame lies outside the range the references span, per pixel: 0 where it is between them."""
    low, high = np.minimum.reduce(refs), np.maximum.reduce(refs)
    return np.maximum(np.maximum(low - a, a - high), 0).max(axis=2)


def difference(a, b, box, zoom, shrink):
    x, y, w, h = box
    d = (b if b.ndim == 2 else np.abs(a - b).max(axis=2))[y:y + h, x:x + w]
    if bold:
        padded = np.pad(d, 1)
        d = np.maximum.reduce([padded[1 + dy:1 + dy + d.shape[0], 1 + dx:1 + dx + d.shape[1]]
                               for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    if shrink > 1:
        hh, ww = h // shrink * shrink, w // shrink * shrink
        d = d[:hh, :ww].reshape(hh // shrink, shrink, ww // shrink, shrink).max(axis=(1, 3))
    heat = np.full(d.shape + (3,), 255, np.uint8)
    heat[d > 8] = [255, 160, 0]
    heat[d > 20] = [255, 0, 0]
    im = Image.fromarray(heat)
    return im if shrink > 1 else im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)


rows = []
for spec in args[2:]:
    spec, _, note = spec.partition(';')
    name, framing, *options = spec.split(':')
    opt = dict(o.split('=', 1) for o in options)
    key = [k for k in files if k == name or k.endswith('__' + name)][0]
    b, a = frame(opt.get('before', before), key, framing), frame(opt.get('after', after), key, framing)
    refs = [(b, reference(b, key, framing)) for b in browsers]
    H, W = b.shape[:2]
    zoom, shrink = int(opt.get('zoom', 1)), int(opt.get('shrink', 1))
    if 'box' in opt:
        box = tuple(int(v) for v in opt['box'].split(','))
    else:
        w, h = (int(v) for v in opt.get('size', '40x30').split('x')) if ('at' in opt or 'size' in opt) else (W, H)
        if 'at' in opt:
            cx, cy = (int(v) for v in opt['at'].split(','))
        elif 'size' in opt:
            ys, xs = np.nonzero(np.abs(b - a).max(axis=2) > 0)
            if len(xs) == 0:
                raise SystemExit(f'{name} {framing}: the builds do not differ; give at= or box=')
            i = np.argmax(xs - ys)
            cx, cy = int(xs[i]), int(ys[i])
        else:
            cx, cy = W // 2, H // 2
        box = (min(max(cx - w // 2, 0), W - w), min(max(cy - h // 2, 0), H - h), w, h)
    panels = [(before_label, picture(b, box, zoom, shrink)), (after_label, picture(a, box, zoom, shrink))]
    caption = f'{name} at {framing}: beyond 20/255'
    for browser, ref in refs:
        short = SHORT[browser]
        if not diffs_only:
            panels.append((NAMES[browser], picture(ref, box, zoom, shrink)))
        panels += [(f'{before_label} vs {short}', difference(b, ref, box, zoom, shrink)),
                   (f'{after_label} vs {short}', difference(a, ref, box, zoom, shrink))]
        caption += f', vs {short} {beyond(b, ref):.2f} % -> {beyond(a, ref):.2f} %'
    for other in others:
        # Another renderer against the first reference: what a browser at one device pixel is off by itself.
        first, theirs = refs[0][1], reference(other, key, framing)
        panels.append((f'{SHORT[other]} vs {SHORT[browsers[0]]}', difference(theirs, first, box, zoom, shrink)))
        caption += f'; {SHORT[other]} {beyond(theirs, first):.2f} %'
    if span:
        among = [reference(r, key, framing) for r in span]
        ob, oa = outside(b, among), outside(a, among)
        panels += [(f'{before_label} outside the browsers', difference(b, ob, box, zoom, shrink)),
                   (f'{after_label} outside the browsers', difference(a, oa, box, zoom, shrink))]
        caption += f', outside all {len(span)} {100 * (ob > 20).mean():.2f} % -> {100 * (oa > 20).mean():.2f} %'
    caption += f'. {note}' if note else ''
    rows.append((caption, panels))
    print(caption)

gap, cap = 8, 36
width = max(sum(p.width + gap for _, p in panels) for _, panels in rows) + gap
column = max(p.width for _, panels in rows for _, p in panels) + gap
sheet = Image.new('RGB', (max(width, len(rows[0][1]) * column + gap), sum(max(p.height for _, p in panels) + cap + gap for _, panels in rows) + gap), 'white')
draw = ImageDraw.Draw(sheet)
y = gap
for caption, panels in rows:
    draw.text((gap, y), caption, fill=(0, 0, 0), font=font(13, caption))
    for i, (label, p) in enumerate(panels):
        x = gap + i * column
        draw.text((x, y + 19), label, fill=(90, 90, 90), font=font(11))
        sheet.paste(p, (x, y + cap))
        draw.rectangle([x - 1, y + cap - 1, x + p.width, y + cap + p.height], outline=(200, 200, 200))
    y += max(p.height for _, p in panels) + cap + gap
sheet.save(out)
print(out, sheet.size)
