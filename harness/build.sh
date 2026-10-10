#!/usr/bin/env bash
# Builds the harness against femtovg checkouts.
#
#   harness/build.sh [--gl] TAG[:SRC] ...
#
# For each TAG, the corpus harness (_logos_full.rs) built against the femtovg checkout SRC with every harness cfg
# that checkout's API supports, into $HARNESS_BIN/_logos_full_TAG, which corpus_run/common.py runs as build TAG.
# With --gl, the OpenGL tools of clip-bench instead (gl_fill_bench, gl_clip_check, gl_svg_dump, or those named in
# GL_EXAMPLES), into $HARNESS_BIN/<tool>_TAG.
#
# Environment (each optional):
#   FEMTOVG_SRC       the checkout for a TAG without :SRC (default: the femtovg repository this demo-assets
#                     checkout is a worktree of)
#   HARNESS_BIN       where the binaries go (default: bin/ beside this checkout)
#   CARGO_TARGET_DIR  cargo's; one directory shared by several checkouts saves rebuilding the dependencies (the
#                     checkout's sources are touched first, so a library built from another one is never linked)
#   HARNESS_LOGS      build logs (default: $HARNESS_BIN/logs)
#   EXTRA_CFGS        more flags for rustc, e.g. "--cfg harness_slices"
#
# The example is copied into the checkout's examples/ for the build and removed after: left there, a wgpu-gated
# example breaks the featureless `cargo build --examples` CI job.
set -euo pipefail

HARN=$(cd "$(dirname "$0")" && pwd)
DA=$(dirname "$HARN")
HARNESS_BIN=${HARNESS_BIN:-$(dirname "$DA")/bin}
HARNESS_LOGS=${HARNESS_LOGS:-$HARNESS_BIN/logs}
mkdir -p "$HARNESS_BIN" "$HARNESS_LOGS"

gl=0
if [ "${1:-}" = "--gl" ]; then
  gl=1
  shift
fi
if [ $# -eq 0 ]; then
  sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

default_src() {
  local common
  common=$(git -C "$DA" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 0
  dirname "$common"
}

# The harness cfgs the checkout's API supports, found by what each one calls.
cfgs_for() {
  local src=$1/src flags=()
  has() { grep -rqF -- "$1" "$src"; }
  has 'pub fn clip_path(' && flags+=(--cfg harness_clip)
  has 'TurbulenceKind' && flags+=(--cfg harness_turbulence)
  has 'Blend {' && flags+=(--cfg harness_blend)
  has 'fn with_blend(' && flags+=(--cfg harness_mix_blend)
  has 'sigma_x' && flags+=(--cfg harness_blur_xy)
  has 'Morphology {' && flags+=(--cfg harness_morph)
  has 'Crop {' && flags+=(--cfg harness_crop)
  has 'pub fn clip_paths' && flags+=(--cfg harness_clip_paths)
  has 'fn set_submission_slicing' && flags+=(--cfg harness_slices)
  has 'fn debug_image_count' && flags+=(--cfg harness_image_count)
  echo "${flags[@]}"
}

for spec in "$@"; do
  tag=${spec%%:*}
  src=${FEMTOVG_SRC:-$(default_src)}
  [ "$spec" != "$tag" ] && src=${spec#*:}
  if [ -z "$src" ] || ! grep -qs '^name = "femtovg"' "$src/Cargo.toml"; then
    echo "$tag: '$src' is no femtovg checkout; pass TAG:SRC or set FEMTOVG_SRC" >&2
    exit 1
  fi
  src=$(cd "$src" && pwd)
  rev=$(git -C "$src" rev-parse --short HEAD 2>/dev/null || echo '?')
  find "$src/src" -name '*.rs' -exec touch {} +

  if [ $gl -eq 0 ]; then
    cfgs=$(cfgs_for "$src")
    cp "$HARN/_logos_full.rs" "$src/examples/_logos_full.rs"
    log=$HARNESS_LOGS/build_$tag.log
    # shellcheck disable=SC2086
    if (cd "$src" && cargo rustc --release --example _logos_full --features wgpu -- $cfgs ${EXTRA_CFGS:-}) > "$log" 2>&1; then
      out=${CARGO_TARGET_DIR:-$src/target}/release/examples/_logos_full
      cp "$out" "$HARNESS_BIN/_logos_full_$tag"
      ppm=$(mktemp -t harness_cfgs).ppm
      line=$(LAYER_STATS=1 "$HARNESS_BIN/_logos_full_$tag" 1 "$ppm" "$HARN/subpx.svg" 2>&1 | grep 'harness cfgs' || true)
      rm -f "$ppm"
      echo "built _logos_full_$tag from $src ($rev): ${line:-no harness cfgs line}"
    else
      echo "_logos_full_$tag FAILED (log: $log)" >&2
      grep -A12 '^error' "$log" | head -30 >&2
    fi
    rm -f "$src/examples/_logos_full.rs"
  else
    for ex in ${GL_EXAMPLES:-gl_fill_bench gl_clip_check gl_svg_dump}; do
      cp "$HARN/clip-bench/$ex.rs" "$src/examples/$ex.rs"
      log=$HARNESS_LOGS/build_${ex}_$tag.log
      if (cd "$src" && cargo build --release --example "$ex") > "$log" 2>&1; then
        cp "${CARGO_TARGET_DIR:-$src/target}/release/examples/$ex" "$HARNESS_BIN/${ex}_$tag"
        echo "built ${ex}_$tag from $src ($rev)"
      else
        echo "${ex}_$tag FAILED (log: $log)" >&2
        grep -A12 '^error' "$log" | head -30 >&2
      fi
      rm -f "$src/examples/$ex.rs"
    done
  fi
done
