#!/bin/zsh
# Render every case in manifest.json: femtovg (wt-all3 harness) at 1x and 2x,
# Chromium 131 test+ref at 1x and 2x, Firefox test+ref at 1x.
# Usage: render.sh [case-name ...]   (default: all)
set -u
W=${W:-$(cd "$(dirname "$0")" && pwd)}
BIN=/private/tmp/wt-all3/target/debug/examples/_logos_full
MK=/private/tmp/wt-da/harness/make_ref.py
CHROME=$HOME/.cache/puppeteer/chrome-headless-shell/mac_arm-131.0.6778.204/chrome-headless-shell-mac-arm64/chrome-headless-shell
FF="/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox"
mkdir -p $W/out $W/pages
cases=("$@")
if [ ${#cases[@]} -eq 0 ]; then
  cases=($(python3 -c "import json;print(' '.join(json.load(open('$W/manifest.json')).keys()))"))
fi
for name in $cases; do
  eval $(python3 - "$name" <<'EOF'
import json, sys
m = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")))[sys.argv[1]]
print(f"FW={m['frame_w']} FH={m['frame_h']} B={m['box']} BX={m['box_x']} BY={m['box_y']} REF={m['ref']}")
EOF
)
  export FRAME_W=$FW FRAME_H=$FH BOX=$B BOX_X=$BX BOX_Y=$BY
  for z in 1.0 2.0; do
    # femtovg
    SKIP_UNSUPPORTED_FILTERS=1 VIEWPORT_CLIP=1 $BIN $z $W/out/fvg_${name}_$z.ppm $W/framed/$name.svg 2>$W/out/fvg_${name}_$z.log
    # Chromium: test and ref pages
    for kind in test ref; do
      if [ $kind = test ]; then src=$W/framed/$name.svg; else src=$W/framed/$REF.svg; fi
      page=$W/pages/${name}_${kind}_$z.html
      python3 $MK $src $z > $page
      $CHROME --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
        --window-size=$FW,$FH --default-background-color=FFFFFFFF \
        --screenshot=$W/out/chr_${name}_${kind}_$z.png file://$page >/dev/null 2>&1
    done
  done
  # Firefox at 1x, test and ref
  for kind in test ref; do
    prof=$(mktemp -d)
    "$FF" --headless --no-remote --profile $prof --window-size=$FW,$FH \
      --screenshot $W/out/ff_${name}_${kind}_1.0.png file://$W/pages/${name}_${kind}_1.0.html >/dev/null 2>&1
    rm -rf $prof
  done
  echo "rendered $name (frame ${FW}x${FH} box $B at $BX,$BY ref $REF)"
done
