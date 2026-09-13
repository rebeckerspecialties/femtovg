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
    n=os.path.basename(svg)[:-4]; r=run(svg, 1.0, n); rows.append((n,r)); 
print("BuseyBench vs Chromium 131 @460x260: mean px>20 %.3f%%  mean structural %.3f%%  files>0.05%% structural: %s" % (
    sum(r[0] for _,r in rows)/len(rows), sum(r[1] for _,r in rows)/len(rows), [(n, r[1]) for n,r in rows if r[1]>0.05]))
for n,r in rows: print(f"  {n:45} {r[0]:6.2f}% / {r[1]:6.3f}%")
print("Google Workspace icon ladder:")
for z in [0.6,0.75,0.9,1.0,1.15,1.3,1.6,1.9,2.35]:
    r=run(f"{S}/da/gws.svg", z, f"gws_{z}"); print(f"  {z:<5} {r[0]:6.2f}% / {r[1]:6.3f}%")
print("noodles (luminance x alpha gradient mask):")
for z in [0.6,1.0,1.6,2.35]:
    r=run(f"{S}/da/noodles.svg", z, f"noodles_{z}"); print(f"  {z:<5} {r[0]:6.2f}% / {r[1]:6.3f}%")
