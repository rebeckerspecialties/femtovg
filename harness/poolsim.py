"""Transient-memory model of one frame from a LAYER_LOG: what the current
implementation requests (everything lives to the flush), what a pool that
frees a layer's images at end_layer would peak at, both with viewport-sized
and bounding-box-sized layers, and the bytes each layer moves.

Per layer: an opacity-only layer needs its capture image; a blurred layer needs
the capture, the filtered result and the chain's two scratches (the second
pass of the two-pass blur reuses one; the parity identity pass the other).
Blur padding is 3 sigma + 2 with sigma capped at 8, as the shadow/blur passes
do. Traffic: clear + composite read/write of the capture (3S), plus for a blur
the filtered target clear and three read+write passes (7S)."""
import re, sys
BOX = int(sys.argv[2]) if len(sys.argv) > 2 else 1080
MB = 1024 * 1024
layers = []
for line in open(sys.argv[1]):
    m = re.match(r'LAYER kind=\w+ depth=(\d+) bbox=(\d+)x(\d+) sigma=([\d.]+)', line)
    if m:
        d, w, h, s = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        layers.append((d, w, h, s))
    if line.startswith('END'):
        layers.append(('end',))
masks = sum(1 for line in open(sys.argv[1]) if line.startswith('MASK'))
def images(w, h, sigma):
    pad = 0 if sigma <= 0 else int(3 * min(sigma, 8.0) + 2)
    size = (w + 2 * pad) * (h + 2 * pad) * 4
    count = 4 if sigma > 0 else 1
    traffic = size * (10 if sigma > 0 else 3)
    return size, count, traffic
def run(sizer):
    total = peak = live = traffic = 0
    stack = []
    for l in layers:
        if l[0] == 'end':
            live -= stack.pop(); continue
        d, w, h, s = l
        size, count, tr = images(*sizer(w, h), s)
        bytes_ = size * count
        total += bytes_; traffic += tr
        live += bytes_; stack.append(bytes_); peak = max(peak, live)
    return total, peak, traffic
n = sum(1 for l in layers if l[0] != 'end'); blurred = sum(1 for l in layers if l[0] != 'end' and l[3] > 0)
print(f"layers {n} ({blurred} blurred, max depth {max((l[0] for l in layers if l[0] != 'end'), default=0)}), mask captures {masks} (canvas-sized RGBA8, 1920x1080 = {1920*1080*4/MB:.1f} MB each)")
for label, sizer in [("viewport-sized (today)", lambda w, h: (BOX, BOX)), ("bounding-box-sized", lambda w, h: (max(w, 1), max(h, 1)))]:
    total, peak, traffic = run(sizer)
    print(f"  {label:<24} requested per frame {total/MB:7.1f} MB | peak live with a pool {peak/MB:6.1f} MB | bytes moved per frame {traffic/MB:7.0f} MB")
print(f"  budget 256 MiB: viewport-sized layers that fit before degradation: ~{int(256*MB / (BOX*BOX*4))} opacity-only or ~{int(256*MB / ((BOX+52)*(BOX+52)*4*4))} blurred")
