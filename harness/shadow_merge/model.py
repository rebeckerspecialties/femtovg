"""Per-pixel model of the face's noise overlay under gpt-5-6-sol-pro's shadow group, two ways:

  sRGB merge:      the shadow composited under the group's content in sRGB - the canvas shadow state
                   around the group's layer, the harness mapping before 2026-10-04;
  linearRGB merge: the shadow filter's feMerge in linearRGB (color-interpolation-filters' default),
                   the content converted into it and the merged result back to sRGB.

Inputs come from one renderer at the 60 px margin framing (run.py MARGIN): its noise, alpha a' and
premultiplied colour C a', from the face alone over black and over white; its face coverage from the
face filled white over black. The shadow is the filter's: SourceAlpha blurred by stdDeviation 15,
offset dy 17 (user units, 0.78125 px each at 4x), alpha times 0.6, black."""
import numpy as np
from scipy import ndimage

S = 0.78125
SIGMA, DY, K = 15 * S, 17 * S, 0.6
BG = np.array([0x18, 0x2b, 0x3b], float) / 255
WINDOW = (slice(245, 316), slice(60, 83))   # rows 185-255, columns 0-22 of the 460x260 frame


def lin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)


def shadow_of(alpha):
    blurred = ndimage.gaussian_filter(alpha, SIGMA, mode='constant', truncate=4.0)
    return K * ndimage.shift(blurred, (DY, 0), order=1, mode='constant')


def predict(load):
    """The overlay (frame minus the frame without the face's filter, 0..255 per channel) under both
    models, from load(name) -> the renderer's RGB frame of that variant as floats."""
    bk, wh, mask = load('face_alone_bk'), load('face_alone_wh'), load('face_mask')
    ca = bk / 255
    a = np.clip((255 - wh + bk) / 255, 0, 1).mean(-1)
    face = mask[..., 1] / 255
    noise = np.where(face > 0.999, 0, a)
    s, s0 = shadow_of(face + noise * (1 - face)), shadow_of(face)
    base = BG * (1 - s0[..., None])
    out_srgb = BG * (1 - s[..., None]) * (1 - a[..., None]) + ca
    colour = np.where(a[..., None] > 1e-6, ca / np.maximum(a[..., None], 1e-6), 0)
    merged = lin(colour) * a[..., None]
    alpha = a + s * (1 - a)
    out_lin = BG * (1 - alpha[..., None]) + srgb(merged / np.maximum(alpha[..., None], 1e-6)) * alpha[..., None]
    return 255 * (out_srgb - base), 255 * (out_lin - base)
