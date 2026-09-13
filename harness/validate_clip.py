import os, re, subprocess, sys, glob
S=os.environ['S']; BIN=os.environ['BIN']; OUT=os.environ['OUT']; os.makedirs(OUT, exist_ok=True)
env={**os.environ, "SKIP_UNSUPPORTED_FILTERS":"1", "VIEWPORT_CLIP":"1"}
pat=re.compile(r"px>20: ([\d.]+)%\s+structural \(2px erosion\): ([\d.]+)%")
def run(svg, scale, name):
    ppm=f"{OUT}/{name}.ppm"
    r=subprocess.run([BIN, str(scale), ppm, svg], env=env, capture_output=True, text=True)
    if r.returncode: print("HARNESS FAILED", name, r.stderr[-300:]); return None
    c=subprocess.run([sys.executable, f"{S}/da/harness/compare.py", ppm, f"{S}/refs/chr_{name}.png"], capture_output=True, text=True).stdout
    m=pat.search(c); return (float(m.group(1)), float(m.group(2)))
rows=[]
for svg in sorted(glob.glob(f"{S}/da/corpus/buseybench/*.svg")):
    n=os.path.basename(svg)[:-4]; rows.append((n, run(svg, 1.0, n)))
print("BuseyBench vs Chromium 131 @460x260: mean px>20 %.3f%%  mean structural %.3f%%  files>0.05%%: %s" % (
    sum(r[0] for _,r in rows)/len(rows), sum(r[1] for _,r in rows)/len(rows), [(n, r[1]) for n,r in rows if r[1]>0.05]))
print("clip scene (nonzero star + evenodd donut clips) ladder:")
for z in [0.5,1.0,1.1,1.7,2.5]:
    r=run(f"{S}/da/clipdemo.svg", z, f"clipdemo_{z}"); print(f"  {z:<4} {r[0]:6.2f}% / {r[1]:6.3f}%")
