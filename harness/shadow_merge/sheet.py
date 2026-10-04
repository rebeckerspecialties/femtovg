#!/usr/bin/env python3
"""Evidence sheet for shadow-merge-2026-10-04.md from run.py's output (SHADOW_MERGE_OUT):

  sheet.py BEFORE AFTER out.png

Top row: gpt-5-6-sol-pro at 4x, the background left of the face (frame columns 0-59, rows 150-259),
3x, beside its noise overlay there (frame minus the frame without the face's filter, green, 12
output levels per overlay level); the red box is the measured window. Bottom row:
corpus/shadow-merge/linear-merge-swatches.svg at 1x, opaque greys sRGB 3..64 above, rgb(200) at
fill-opacity .02..58 over their own shadow below, 2x. Columns: femtovg BEFORE and AFTER, Chromium,
Firefox."""
import os, sys
import numpy as np
from PIL import Image, ImageDraw

OUT = os.path.abspath(os.environ.get('SHADOW_MERGE_OUT', 'shadow-merge-run'))


def load(path):
    return np.asarray(Image.open(path).convert('RGB'), dtype=float)


def frame(sub, renderer, name):
    ext = 'png' if renderer in ('chr', 'ff') else 'ppm'
    return load(f'{OUT}/{sub}/{renderer}_{name}.{ext}') if name else load(f'{OUT}/{sub}/{renderer}.{ext}')


def image(a, size):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize(size, Image.NEAREST)


def main(before, after, out):
    columns = [(before, f'femtovg, {before}'), (after, f'femtovg, {after}'), ('chr', 'Chromium'), ('ff', 'Firefox')]
    crop = (slice(150, 260), slice(0, 60))
    width, top, bottom = 416, 330, 274
    sheet = Image.new('RGB', (16 + 4 * width, 28 + top + 8 + bottom + 44), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    for i, (renderer, label) in enumerate(columns):
        x = 16 + i * width
        full = frame('z4', renderer, 'sol')
        over = full - frame('z4', renderer, 'sol_nofilter')
        g = over[crop][..., 1] * 12
        panels = [image(full[crop], (180, top)), image(np.stack([g] * 3, -1), (180, top))]
        for p in panels:
            ImageDraw.Draw(p).rectangle([0, (185 - 150) * 3, 23 * 3 - 1, (256 - 150) * 3 - 1], outline=(255, 64, 64))
        draw.text((x, 8), f'{label}: window overlay {over[185:256, 0:23, 1].mean():.2f}', fill=(0, 0, 0))
        sheet.paste(panels[0], (x, 28))
        sheet.paste(panels[1], (x + 200, 28))
        probe = frame('probe', renderer, None)
        sheet.paste(image(probe[45:182, 130:330], (400, bottom)), (x, 28 + top + 8))
    draw.text((16, sheet.height - 34), 'Top: gpt-5-6-sol-pro 4x, frame columns 0-59 rows 150-259: the frame, and its noise overlay '
              '(green x12); red box: the window, rows 185-255 columns 0-22.', fill=(0, 0, 0))
    draw.text((16, sheet.height - 18), 'Bottom: corpus/shadow-merge/linear-merge-swatches.svg 1x: opaque greys sRGB 3..64, and '
              'rgb(200) at opacity .02..58 over their own shadow; 2x.', fill=(0, 0, 0))
    sheet.save(out)
    print(out, sheet.size)


if __name__ == '__main__':
    main(*sys.argv[1:4])
