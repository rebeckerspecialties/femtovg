#!/usr/bin/env python3
"""Evidence sheet for shadow-merge-library-2026-10-05.md: the shadow colour each renderer gives
corpus/shadow-merge/drop-shadow-tint-rounding.svg at 1x.

  tint_sheet.py CHROMIUM.png FIREFOX.png BEFORE.ppm AFTER.ppm out.png [BEFORE_LABEL AFTER_LABEL]

The probe draws each shadow over black (left) and over white (right), so every pixel gives the
shadow's alpha, 1 - (white - black) / 255, and its colour, black / alpha. Each panel shows that
colour, eight times as bright, where the alpha is at least 0.03, over mid grey elsewhere: rows are
kimi-k3's #2b1712 at .42 as an feDropShadow, claude-opus-5's #0b0d10 at .6 as an feDropShadow, and
#2b1712 at .42 as the written-out chain. Columns: Chromium, Firefox, femtovg BEFORE and AFTER."""
import sys
import numpy as np
from PIL import Image, ImageDraw

BOX_X, BOX_Y = 130, 30  # the 200-unit box at 1x
# (label, svg x of the copy over black, svg x over white, svg y range): the shadow below each shape
ROWS = [
    ('feDropShadow #2b1712 .42', 4, 104, (29, 69)),
    ('feDropShadow #0b0d10 .6', 50, 150, (29, 69)),
    ('feFlood + feComposite #2b1712 .42', 4, 104, (121, 161)),
]
WIDTH = 46  # svg units across each shape's shadow
SCALE = 4


def load(path):
    return np.asarray(Image.open(path).convert('RGB'), dtype=float)


def panel(frame, xk, xw, ys):
    y0, y1 = BOX_Y + ys[0], BOX_Y + ys[1]
    black = frame[y0:y1, BOX_X + xk:BOX_X + xk + WIDTH]
    white = frame[y0:y1, BOX_X + xw:BOX_X + xw + WIDTH]
    alpha = 1.0 - (white - black).mean(axis=2, keepdims=True) / 255.0
    colour = np.where(alpha >= 0.03, black / np.maximum(alpha, 1e-6) * 8.0, 128.0)
    img = Image.fromarray(np.clip(colour, 0, 255).astype(np.uint8))
    return img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)


def main():
    chr_png, ff_png, before, after, out = sys.argv[1:6]
    labels = sys.argv[6:8] if len(sys.argv) > 7 else ['before', 'after']
    columns = [('Chromium', load(chr_png)), ('Firefox', load(ff_png)),
               (f'femtovg, {labels[0]}', load(before)), (f'femtovg, {labels[1]}', load(after))]
    pw, ph = WIDTH * SCALE, 40 * SCALE
    sheet = Image.new('RGB', (200 + len(columns) * (pw + 12), 30 + len(ROWS) * (ph + 12)), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    for c, (label, _) in enumerate(columns):
        draw.text((200 + c * (pw + 12), 8), label, fill=(0, 0, 0))
    for r, (label, xk, xw, ys) in enumerate(ROWS):
        y = 30 + r * (ph + 12)
        draw.text((8, y + ph // 2), label, fill=(0, 0, 0))
        for c, (_, frame) in enumerate(columns):
            sheet.paste(panel(frame, xk, xw, ys), (200 + c * (pw + 12), y))
    sheet.save(out)


if __name__ == '__main__':
    main()
