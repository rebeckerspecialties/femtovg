"""The reference feTurbulence (feturbulence_ref.c, the spec's C code) sampled on a frame's device
pixels, and the colour steps of the corpus's skin-texture chains.

frame_noise() maps device pixel (i + offset, j + offset) to user space through the inverse of the
root transform dev = s * u + (ox, oy) - for gpt-5-6-sol-pro at the 4x framing s = 0.78125,
(ox, oy) = (-170, -270) - and adds user_shift in user units. Fits on the face alone at 4x
(shadow-merge-2026-10-04.md): femtovg and Firefox sample at the pixel corner (offset 0), Chromium
about one pixel further along both axes."""
import os, subprocess, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = f'{HERE}/feturbulence_ref.c'
BIN = os.path.join(os.environ.get('SHADOW_MERGE_OUT', tempfile.gettempdir()), 'feturbulence_ref')


def _binary():
    if not os.path.exists(BIN) or os.path.getmtime(BIN) < os.path.getmtime(SRC):
        os.makedirs(os.path.dirname(BIN), exist_ok=True)
        subprocess.run(['cc', '-O2', '-o', BIN, SRC, '-lm'], check=True)
    return BIN


def turbulence(w, h, a, b, c, d, e, f, seed=19, fx=.018, fy=.09, octaves=3, fractal=1):
    """Raw sums per channel on a w x h grid, pixel (i, j) at (a i + c j + e, b i + d j + f)."""
    fd, path = tempfile.mkstemp(suffix='.f32')
    os.close(fd)
    try:
        subprocess.run([_binary(), str(w), str(h), *map(repr, (a, b, c, d, e, f)), str(seed), repr(fx), repr(fy),
                        str(octaves), str(fractal), path], check=True)
        return np.fromfile(path, dtype=np.float32).reshape(h, w, 4).astype(np.float64)
    finally:
        os.remove(path)


def frame_noise(offset=0.5, user_shift=(0.0, 0.0), s=0.78125, ox=-170.0, oy=-270.0, W=460, H=260, **kw):
    return turbulence(W, H, 1 / s, 0.0, 0.0, 1 / s, (offset - ox) / s + user_shift[0], (offset - oy) / s + user_shift[1], **kw)


def to_rgba(sums, fractal=True):
    return np.clip((sums + 1) / 2 if fractal else sums, 0, 1)


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def lin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def faint(rgba, slope=0.11):
    """feColorMatrix saturate 0, then feFuncA linear slope: (grey, alpha) unpremultiplied, grey in linearRGB."""
    grey = 0.213 * rgba[..., 0] + 0.715 * rgba[..., 1] + 0.072 * rgba[..., 2]
    return np.clip(grey, 0, 1), slope * rgba[..., 3]
