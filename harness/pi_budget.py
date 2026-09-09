"""Pi Zero framing at 1080p on the pooled build: for each budget, how many layers pass through,
what the frame holds, how many transient images it creates, and the diff vs Chromium."""
import json, os, re, subprocess, sys, glob
S=os.environ['S']; B=os.environ['BIN']
pat=re.compile(r"px>20 [\d.]+% frame / ([\d.]+)% box \| structural [\d.]+% frame / ([\d.]+)% box")
frame={"FRAME_W":"1920","FRAME_H":"1080","BOX":"1080","BOX_X":"420","BOX_Y":"0","SKIP_UNSUPPORTED_FILTERS":"1","VIEWPORT_CLIP":"1","LAYER_STATS":"1"}
budgets=[("default 256 MiB", None), ("48 MiB", "48"), ("32 MiB", "32"), ("16 MiB", "16")]
scales=[("1.0", {}), ("2.0 zoom", {})]
results={}
for label, mb in budgets:
    rows={}
    for svg in sorted(glob.glob(f"{S}/busey/*.svg")):
        n=os.path.basename(svg)[:-4]; ppm=f"{S}/b1080/pi_{n}.ppm"
        env={**os.environ, **frame}
        if mb: env["TRANSIENT_BUDGET_MB"]=mb
        r=subprocess.run([B,"1.0",ppm,svg],env=env,capture_output=True,text=True)
        held=int(re.search(r"transient bytes held at flush: (\d+)", r.stderr).group(1))/2**20
        pt=int(re.search(r"layers passed through: (\d+)", r.stderr).group(1))
        layers=int(re.search(r"layers begun: (\d+)", r.stderr).group(1))
        out=subprocess.run([sys.executable,f"{S}/harness/boxstats.py",ppm,f"{S}/b1080/chr_{n}.png"],env={**os.environ,"BOXRECT":"420,0,1080"},capture_output=True,text=True).stdout
        m=pat.search(out); rows[n]={"held":held,"pass_through":pt,"layers":layers,"px":float(m.group(1)),"struct":float(m.group(2))}
    results[label]=rows
    deg=[n for n,r in rows.items() if r["pass_through"]>0]
    print(f"{label:<16} mean {sum(r['px'] for r in rows.values())/27:5.2f}% / {sum(r['struct'] for r in rows.values())/27:6.3f}%  held max {max(r['held'] for r in rows.values()):5.1f} MB mean {sum(r['held'] for r in rows.values())/27:5.1f}  files with pass-through layers: {len(deg)}"+ (f" ({', '.join(f'{n}:{rows[n]['pass_through']}/{rows[n]['layers']}' for n in deg[:6])}{'...' if len(deg)>6 else ''})" if deg else ""), flush=True)
json.dump(results, open(f"{S}/b1080/pi_budget.json","w"), indent=1)
# DPR-style check: the same frame under a 2x zoom (the scissor is set under the zoom transform)
for zoom in ["1.0","2.0"]:
    r=subprocess.run([B,zoom,"/dev/null",f"{S}/busey/gpt-6-astra.svg"],env={**os.environ, **frame},capture_output=True,text=True)
    held=int(re.search(r"transient bytes held at flush: (\d+)", r.stderr).group(1))/2**20
    print(f"gpt-6-astra at zoom {zoom}: held {held:.1f} MB (scissor set under a scale of {zoom})")
