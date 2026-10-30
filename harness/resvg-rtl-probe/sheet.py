#!/usr/bin/env python3
"""Contact sheet: one row per case, resvg main | resvg #1184 | Chromium 131 | Firefox 158, with the share of pixels
beyond 20/255 of Firefox and of Chromium in the label."""
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
names = sys.argv[2:]
cols = [('main', 'resvg main'), ('pr', 'resvg #1184'), ('chr', 'Chromium 131'), ('ff', 'Firefox 158')]
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 15)
W, H, T = 600, 70, 20
sheet = Image.new('RGB', (len(cols) * (W + 8), len(names) * (H + T + 6)), 'white')
g = ImageDraw.Draw(sheet)
load = lambda p: np.asarray(Image.open(p).convert('RGB').crop((0, 0, W, H))).astype(int)
for r, n in enumerate(names):
    ims = {k: load(f'out/{k}_{n}.png') for k, _ in cols}
    y = r * (H + T + 6)
    for c, (k, label) in enumerate(cols):
        x = c * (W + 8)
        d = lambda ref: 100 * (np.abs(ims[k] - ims[ref]).max(2) > 20).mean()
        note = f'{n}  {label}' + ('' if k == 'ff' else f'  ff {d("ff"):.1f} %') + ('' if k in ('chr', 'ff') else f' chr {d("chr"):.1f} %')
        g.text((x, y + 2), note, fill=(40, 40, 40), font=font)
        sheet.paste(Image.fromarray(ims[k].astype(np.uint8)), (x, y + T))
        g.rectangle([x, y + T, x + W - 1, y + T + H - 1], outline=(200, 200, 200))
sheet.save(sys.argv[1])
