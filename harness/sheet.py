#!/usr/bin/env python3
"""Evidence crops: sheet.py OUT.png 'label=path' ... [--crop x0,y0,x1,y1] [--zoom N]"""
import sys
from PIL import Image, ImageDraw
args = sys.argv[1:]; out = args.pop(0); crop = None; zoom = 1
while '--crop' in args:
    i = args.index('--crop'); crop = tuple(int(v) for v in args[i + 1].split(',')); del args[i:i + 2]
while '--zoom' in args:
    i = args.index('--zoom'); zoom = int(args[i + 1]); del args[i:i + 2]
cells = []
for spec in args:
    label, path = spec.split('=', 1)
    im = Image.open(path).convert('RGB')
    if crop: im = im.crop(crop)
    if zoom > 1: im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
    cells.append((label, im))
w, h = cells[0][1].size
sheet = Image.new('RGB', (len(cells) * (w + 10) - 10, h + 18), 'white'); d = ImageDraw.Draw(sheet)
for i, (label, im) in enumerate(cells):
    d.text((i * (w + 10) + 2, 2), label, fill='black'); sheet.paste(im, (i * (w + 10), 18))
sheet.save(out); print(out, sheet.size)
