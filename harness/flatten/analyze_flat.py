#!/usr/bin/env python3
"""Offline flattening analysis over device-space cubics dumped by the experiment build (FEMTOVG_DUMP):
segments made by femtovg's bisection at a tolerance, the theoretical optimum for a deviation, and candidates;
each segment's deviation measured against the true curve."""
import sys, glob, math
import numpy as np

def load(paths):
    cs = []
    for p in paths:
        for l in open(p):
            v = [float(x) for x in l.split()]
            if len(v) == 8 and all(math.isfinite(x) for x in v):
                cs.append(np.array(v).reshape(4, 2))
    return cs

def split(c, t):
    p0, p1, p2, p3 = c
    a, b, cc = p0 + (p1 - p0) * t, p1 + (p2 - p1) * t, p2 + (p3 - p2) * t
    d, e = a + (b - a) * t, b + (cc - b) * t
    m = d + (e - d) * t
    return np.array([p0, a, d, m]), np.array([m, e, cc, p3])

TS = np.linspace(0, 1, 33)
B = np.stack([(1 - TS) ** 3, 3 * (1 - TS) ** 2 * TS, 3 * (1 - TS) * TS ** 2, TS ** 3], 1)

def deviation(c):
    """max distance of the curve from its chord segment, and the area between them (per the chord)."""
    pts = B @ c
    a, b = c[0], c[3]
    d = b - a; L = math.hypot(*d)
    if L < 1e-6:
        dist = np.hypot(*(pts - a).T)
    else:
        dist = np.abs((pts[:, 0] - a[0]) * d[1] - (pts[:, 1] - a[1]) * d[0]) / L
    return dist.max(), np.trapezoid(dist, dx=1 / 32) * L

def bisect(c, tol, level=0, out=None):
    """femtovg's tesselate_bezier: accept when (d2 + d3)^2 < tol * |chord|^2."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = c
    dx, dy = x4 - x1, y4 - y1
    d2 = abs((x2 - x4) * dy - (y2 - y4) * dx); d3 = abs((x3 - x4) * dy - (y3 - y4) * dx)
    if level > 10:
        return out
    if (d2 + d3) ** 2 < tol * (dx * dx + dy * dy):
        out.append(c); return out
    l, r = split(c, 0.5)
    bisect(l, tol, level + 1, out); bisect(r, tol, level + 1, out)
    return out

def optimum(c, dev):
    """segments an optimal flattener needs for a deviation: integral of sqrt(curvature / (8 dev)) ds."""
    t = np.linspace(0, 1, 257)
    p0, p1, p2, p3 = c
    d1 = (3 * np.outer((1 - t) ** 2, p1 - p0) + 6 * np.outer((1 - t) * t, p2 - p1) + 3 * np.outer(t ** 2, p3 - p2))
    d2 = 6 * np.outer(1 - t, p2 - 2 * p1 + p0) + 6 * np.outer(t, p3 - 2 * p2 + p1)
    speed = np.hypot(d1[:, 0], d1[:, 1])
    cross = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    k = np.where(speed > 1e-9, cross / np.maximum(speed, 1e-9) ** 3, 0)
    return np.trapezoid(np.sqrt(k / (8 * dev)) * speed, t)

def report(name, segs, n_curves):
    devs = np.array([deviation(s) for s in segs])
    md, area = devs[:, 0], devs[:, 1]
    print(f"{name:28s} segments {len(segs):7d} ({len(segs) / n_curves:5.2f}/curve)  max dev: mean {md.mean():.4f} p90 {np.percentile(md, 90):.4f} max {md.max():.4f}  area {area.sum():9.2f}")
    return len(segs), area.sum()

if __name__ == '__main__':
    cs = load(sys.argv[1:])
    print(len(cs), 'cubics')
    for tol in (0.25, 0.0625, 0.03125):
        report(f'bisection {tol}', [s for c in cs for s in bisect(c, tol, 0, [])], len(cs))
    for dev in (0.15, 0.1, 0.08, 0.06):
        print(f'optimum for deviation {dev}: {sum(optimum(c, dev) for c in cs):9.0f} segments (no rounding)')

# Levien's flattening (kurbo / Vello): a cubic as quadratics, each quadratic's subdivisions from the integral of a
# parabola's arc-length-like measure, the cubic's total spread over its quads.
def api(x):
    D = 0.67
    return x / (1.0 - D + math.sqrt(math.sqrt(D ** 4 + 0.25 * x * x)))

def apii(x):
    Bc = 0.39
    return x * (1.0 - Bc + math.sqrt(Bc * Bc + 0.25 * x * x))

def quad_params(q, sqrt_tol):
    p0, p1, p2 = q
    d01, d12 = p1 - p0, p2 - p1
    dd = d01 - d12
    cross = (p2 - p0)[0] * dd[1] - (p2 - p0)[1] * dd[0]
    if abs(cross) < 1e-12:
        return None  # a straight line: one segment's worth, nothing to spread
    x0 = (d01 @ dd) / cross
    x2 = (d12 @ dd) / cross
    scale = abs(cross / (math.hypot(*dd) * (x2 - x0))) if x2 != x0 else float('inf')
    a0, a2 = api(x0), api(x2)
    if math.isfinite(scale):
        da = abs(a2 - a0)
        ss = math.sqrt(scale)
        if (x0 >= 0) == (x2 >= 0):
            val = da * ss
        else:
            xmin = sqrt_tol / ss
            val = sqrt_tol * da / api(xmin)
    else:
        val = 0.0
    u0, u2 = apii(a0), apii(a2)
    return (a0, a2, u0, 1.0 / (u2 - u0) if u2 != u0 else 0.0, val)

def to_quads(c, accuracy):
    p0, p1, p2, p3 = c
    err = np.sum(((3 * p2 - p3) - (3 * p1 - p0)) ** 2)
    n = max(1, math.ceil((err / (432.0 * accuracy * accuracy)) ** (1 / 6)))
    out, rest = [], c
    for i in range(n):
        if i + 1 < n:
            piece, rest = split(rest, 1.0 / (n - i))
        else:
            piece = rest
        q1 = (3 * (piece[1] + piece[2]) - (piece[0] + piece[3])) / 4
        out.append(np.array([piece[0], q1, piece[3]]))
    return out

def quad_eval(q, t):
    return (1 - t) ** 2 * q[0] + 2 * (1 - t) * t * q[1] + t * t * q[2]

def levien(c, tol, quad_accuracy):
    sqrt_tol = math.sqrt(tol)
    quads = to_quads(c, quad_accuracy)
    params = [quad_params(q, sqrt_tol) for q in quads]
    vals = [p[4] if p else 0.0 for p in params]
    total = sum(vals)
    n = max(1, math.ceil(0.5 * total / sqrt_tol))
    # points along the cubic at each step of the integral; returns the polyline's vertices (curve points)
    pts = [c[0]]
    step = total / n
    cum, qi = 0.0, 0
    for i in range(1, n):
        target = i * step
        while qi < len(quads) - 1 and cum + vals[qi] < target:
            cum += vals[qi]; qi += 1
        p = params[qi]
        if p and vals[qi] > 0:
            a = p[0] + (p[1] - p[0]) * (target - cum) / vals[qi]
            u = apii(a)
            t = (u - p[2]) * p[3]
        else:
            t = 0.5
        pts.append(quad_eval(quads[qi], t))
    pts.append(c[3])
    return pts

def polyline_dev(c, pts):
    """deviation of the true cubic from a polyline whose vertices lie on it: sample the cubic densely, measure each
    sample's distance to the nearest segment."""
    t = np.linspace(0, 1, 513)
    curve = np.stack([(1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3], 1) @ c
    P = np.array(pts)
    A, Bp = P[:-1], P[1:]
    AB = Bp - A
    L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    # distance of every curve sample to every segment (vectorised), min over segments
    ap = curve[:, None, :] - A[None, :, :]
    u = np.clip((ap * AB[None]).sum(2) / L2[None], 0, 1)
    proj = A[None] + u[..., None] * AB[None]
    d = np.hypot(*(curve[:, None, :] - proj).transpose(2, 0, 1)).min(1)
    length = np.hypot(*np.diff(curve, axis=0).T)
    return d.max(), float((0.5 * (d[1:] + d[:-1]) * length).sum())

def report_poly(name, polys, cs):
    segs = sum(len(p) - 1 for p in polys)
    r = np.array([polyline_dev(c, p) for c, p in zip(cs, polys)])
    print(f"{name:28s} segments {segs:7d} ({segs / len(cs):5.2f}/curve)  per-curve max dev: mean {r[:, 0].mean():.4f} p90 {np.percentile(r[:, 0], 90):.4f} max {r[:, 0].max():.4f}  area {r[:, 1].sum():9.2f}")

def bisect_poly(c, tol):
    return [c[0]] + [s[3] for s in bisect(c, tol, 0, [])]

def bisect_straddle(c, tol, k):
    """bisection at tol, then every vertex inside the curve moved by the mean of its two chords' shifts: a chord
    whose control points lie a, b off it (signed) is shifted k * (a + b) / 2 along its left normal (k = 1/2 gives
    the chord the curve's area)."""
    segs = bisect(c, tol, 0, [])
    shifts = []
    for s in segs:
        p1, p2, p3, p4 = s
        d = p4 - p1; L = math.hypot(*d)
        if L < 1e-9:
            shifts.append(np.zeros(2)); continue
        n = np.array([-d[1], d[0]]) / L
        a = (p2 - p1) @ n; b = (p3 - p1) @ n
        shifts.append(k * (a + b) / 2 * n)
    pts = [c[0]]
    for i in range(len(segs) - 1):
        pts.append(segs[i][3] + (shifts[i] + shifts[i + 1]) / 2)
    pts.append(c[3])
    return pts

def signed_area(c, pts):
    """area of curve minus polygon (shoelace over the closed loop curve forward, polyline back)."""
    t = np.linspace(0, 1, 513)
    curve = np.stack([(1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3], 1) @ c
    loop = np.concatenate([curve, np.array(pts)[::-1]])
    x, y = loop[:, 0], loop[:, 1]
    return 0.5 * (x @ np.roll(y, -1) - y @ np.roll(x, -1))

def chains(cs, smooth_cos=0.999):
    """consecutive cubics joined end to start with continuous tangents, as lists of indices."""
    out, cur = [], [0]
    for i in range(1, len(cs)):
        a, b = cs[i - 1], cs[i]
        joined = np.allclose(a[3], b[0], atol=1e-3)
        ta = a[3] - a[2] if np.hypot(*(a[3] - a[2])) > 1e-6 else a[3] - a[1]
        tb = b[1] - b[0] if np.hypot(*(b[1] - b[0])) > 1e-6 else b[2] - b[0]
        na, nb = np.hypot(*ta), np.hypot(*tb)
        smooth = na > 1e-9 and nb > 1e-9 and (ta @ tb) / (na * nb) > smooth_cos
        if joined and smooth:
            cur.append(i)
        else:
            out.append(cur); cur = [i]
    out.append(cur)
    return out

def chain_straddle(cs, chain, tol, k, flatten=None):
    """straddle across a chain: segments of every curve in the chain, interior vertices AND smooth joints moved by the
    mean of their two chords' shifts; the chain's two ends stay put. Returns a polyline per curve (sharing joints)."""
    flatten = flatten or (lambda c: bisect(c, tol, 0, []))
    segs, owner = [], []
    for ci in chain:
        for s in flatten(cs[ci]):
            segs.append(s); owner.append(ci)
    shifts = []
    for s in segs:
        p1, p2, p3, p4 = s
        d = p4 - p1; L = math.hypot(*d)
        if L < 1e-9:
            shifts.append(np.zeros(2)); continue
        n = np.array([-d[1], d[0]]) / L
        a = (p2 - p1) @ n; b = (p3 - p1) @ n
        shifts.append(k * (a + b) / 2 * n)
    verts = [segs[0][0]] + [segs[i][3] + (shifts[i] + shifts[i + 1]) / 2 for i in range(len(segs) - 1)] + [segs[-1][3]]
    polys = {}
    for i, ci in enumerate(owner):
        polys.setdefault(ci, [verts[i]]).append(verts[i + 1])
    return polys
