import os, subprocess, glob, sys
S=os.environ['S']; CHR=os.path.expanduser("~/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell")
def ref(svg, scale, out):
    html=out[:-4]+".html"
    with open(html,"w") as f: subprocess.run([sys.executable, f"{S}/da/harness/make_ref.py", svg, str(scale)], stdout=f, check=True)
    subprocess.run([CHR,"--headless","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=1","--window-size=460,260","--default-background-color=FFFFFFFF",f"--screenshot={out}",f"file://{html}"],capture_output=True)
for svg in sorted(glob.glob(f"{S}/da/corpus/buseybench/*.svg")):
    n=os.path.basename(svg)[:-4]; ref(svg, 1.0, f"{S}/refs/chr_{n}.png")
ladder=[0.6,0.75,0.9,1.0,1.15,1.3,1.6,1.9,2.35]
for z in ladder: ref(f"{S}/da/gws.svg", z, f"{S}/refs/chr_gws_{z}.png")
for z in [0.6,1.0,1.6,2.35]: ref(f"{S}/da/noodles.svg", z, f"{S}/refs/chr_noodles_{z}.png")
print("refs done", len(glob.glob(f"{S}/refs/*.png")))
