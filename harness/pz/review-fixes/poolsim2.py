"""Exact-class transient pool simulator for one frame from a LAYER_LOG, under the two layer
image policies:

  orig  (corpus-all3 before the #323 review fixes): begin_layer takes the capture and, for a
        masked layer, its coverage images; end_layer takes the filter chain's result and its
        scratches lazily (scratch i at pass i), releases the scratches after the chain and the
        rest after the composite.
  fixed (dc0f9a9): begin_layer takes the capture, the coverage images, the chain's result and
        min(2, passes - 1) scratches; end_layer releases the scratches after the chain and the
        rest after the composite.

The pool (src/transient.rs) reuses a free image only of exactly the same width, height and
flags and never frees within a frame, so the bytes held at the flush are the sum over
(size, flags) classes of the peak number of images live at once in that class. The store size
follows begin_layer (src/lib.rs): the scissor rect (the viewport box for a depth-0 layer, the
enclosing store for a nested one, whose scissor was reset) padded by ceil(3 * min(sigma, 8)) + 2
per side when the chain has a Gaussian blur, rounded up to 64. A lone blur is two passes (blur +
parity identity), so one scratch. Flags: capture and mask-normalized are PREMULTIPLIED|FLIP_Y
("F"), result, scratches and mask-converted are PREMULTIPLIED ("P").

Masks are not in the LAYER_LOG; pass --masks 'depth0-index:kind,...' is not supported, instead
the simulator takes --mask-layers N:luminance|alpha for the Nth LAYER line (0-based) when
needed. Shadows are ignored (their 8-px classes do not coincide with the 64-px layer classes).

Usage: poolsim2.py LAYER_LOG_FILE --box 1080 [--mask-layers 3:luminance 7:alpha]
"""
import argparse, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("log")
ap.add_argument("--box", type=int, default=1080)
ap.add_argument("--mask-layers", nargs="*", default=[])
ap.add_argument("--verbose", action="store_true")
args = ap.parse_args()

masks = {}
for spec in args.mask_layers:
    i, kind = spec.split(":")
    masks[int(i)] = kind


def round64(n):
    return -(-n // 64) * 64


events = []  # ("begin", idx, depth, sigma) / ("end", depth)
for line in open(args.log):
    m = re.match(r"LAYER kind=\w+ depth=(\d+) bbox=(\d+)x(\d+) sigma=([\d.]+)", line)
    if m:
        events.append(("begin", int(m.group(1)), float(m.group(4))))
    elif line.startswith("END depth="):
        events.append(("end", int(line.split("=")[1])))


def pad(sigma):
    return int(-(-(3.0 * min(sigma, 8.0)) // 1)) + 2 if sigma > 0 else 0


class Pool:
    def __init__(self):
        self.free = {}    # class -> count free
        self.live = {}    # class -> count allocated (peak tracked)
        self.peak = {}

    def acquire(self, cls):
        if self.free.get(cls, 0) > 0:
            self.free[cls] -= 1
        else:
            self.live[cls] = self.live.get(cls, 0) + 1
        self.peak[cls] = max(self.peak.get(cls, 0), self.live[cls] - self.free.get(cls, 0))
        return cls

    def release(self, cls):
        self.free[cls] = self.free.get(cls, 0) + 1

    def bytes(self):
        return sum(w * h * 4 * n for (w, h, _), n in self.live.items())


def simulate(policy):
    pool = Pool()
    stack = []  # per open layer: dict(size, held classes list, chain classes list)
    idx = 0
    for ev in events:
        if ev[0] == "begin":
            _, depth, sigma = ev
            # Scissor rect: the viewport box at depth 0; the enclosing store when nested.
            base = args.box if not stack else stack[-1]["size"]
            p = pad(sigma)
            size = round64(base + 2 * p)
            F = (size, size, "F")
            P = (size, size, "P")
            held = [pool.acquire(F)]  # capture
            kind = masks.get(idx)
            if kind:
                held.append(pool.acquire(F))       # normalized
                if kind == "luminance":
                    held.append(pool.acquire(P))   # converted
            passes = 2 if sigma > 0 else 0          # blur + parity identity
            chain = []
            if policy == "fixed" and passes:
                chain.append(pool.acquire(P))                          # result
                chain += [pool.acquire(P) for _ in range(min(2, passes - 1))]  # scratches
            stack.append({"size": size, "held": held, "chain": chain, "passes": passes, "P": P})
            idx += 1
        else:
            rec = stack.pop()
            if rec["passes"]:
                if policy == "orig":
                    result = pool.acquire(rec["P"])
                    scratches = [pool.acquire(rec["P"]) for _ in range(min(2, rec["passes"] - 1))]
                else:
                    result, scratches = rec["chain"][0], rec["chain"][1:]
                for s in scratches:
                    pool.release(s)
                pool.release(result)
            for h in rec["held"]:
                pool.release(h)
    return pool


for policy in ("orig", "fixed"):
    pool = simulate(policy)
    print(f"{policy:5s} held at flush {pool.bytes():>10d} B = {pool.bytes()/2**20:6.2f} MiB; classes: "
          + ", ".join(f"{w}{f}x{n}" for (w, h, f), n in sorted(pool.live.items())))
n_layers = sum(1 for e in events if e[0] == "begin")
maxd = max((e[1] for e in events if e[0] == "begin"), default=0)
nested_in_blur = 0
stack = []
for e in events:
    if e[0] == "begin":
        if stack and stack[-1] > 0:
            nested_in_blur += 1
        stack.append(e[2])
    else:
        stack.pop()
print(f"layers {n_layers}, max depth {maxd}, layers opened inside a blurred layer: {nested_in_blur}")
