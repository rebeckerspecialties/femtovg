#!/usr/bin/env python3
"""What a build's layers cost against another's on the files that merge a shadow in linearRGB: frame time,
the transient pool's bytes at flush, and whether the library's default transient budget (128 MiB) still
renders each frame as the lifted budget of the corpus runs does.

  cost.py OUT_JSON [builds=BEFORE,AFTER] [framings=z1,z2,z4,hd] [list=FILES.json] [frames=3] [repeat=2]
  cost.py --summary OUT_JSON [BEFORE AFTER]

The files are those whose LAYER_LOG shows a merge layer (rule 4a of the README) under the AFTER build, from
the corpus files that draw a shadow, unless list= names them. Every run is sequential, so no two renders
share the CPU or GPU; builds alternate within each repeat and the fastest repeat counts. frame_ms is the
harness's mean over FRAMES (the first frame compiles the pipelines). 'held' is the pool's charged bytes at
flush, which the budget bounds; 'kept' says the default budget renders the frame byte for byte as the
lifted one, and a frame that is not kept lost a layer, a filter or a shadow to the budget. On macOS,
MEM_PEAKS also gives the peak graphics footprint. Environment: SHADOW_MERGE_OUT (default
./shadow-merge-run/cost), HARNESS_BIN as for ab.py."""
import glob, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DA = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.path.abspath(os.environ.get('SHADOW_MERGE_OUT', 'shadow-merge-run')), 'cost')
BIN = os.environ.get('HARNESS_BIN', os.path.join(os.path.dirname(DA), 'bin'))
DEFAULT = {'FRAME_W': '460', 'FRAME_H': '260', 'BOX': '200', 'BOX_X': '130', 'BOX_Y': '30'}
HD = {'FRAME_W': '1920', 'FRAME_H': '1080', 'BOX': '1080', 'BOX_X': '420', 'BOX_Y': '0'}
FRAMINGS = {'z1': (DEFAULT, 1.0), 'z2': (DEFAULT, 2.0), 'z4': (DEFAULT, 4.0), 'hd': (HD, 1.0)}
BASE_ENV = {'SKIP_UNSUPPORTED_FILTERS': '1', 'VIEWPORT_CLIP': '1', 'LAYER_STATS': '1', 'MEM_PEAKS': '1'}
BUDGETS = {'lifted': {'TRANSIENT_BUDGET_MB': '1024'}, 'default': {}}
SHADOW = ('<feDropShadow', '<feOffset', '<feMerge')


def run(build, path, framing, env, out):
    fr, z = FRAMINGS[framing]
    r = subprocess.run([f'{BIN}/_logos_full_{build}', str(z), out, path], capture_output=True, text=True,
                       timeout=1200, env={**os.environ, **fr, **BASE_ENV, **env})
    return r.stderr


def merged_files(build):
    out = []
    for p in sorted(glob.glob(f'{DA}/corpus/**/*.svg', recursive=True)):
        src = open(p, errors='replace').read()
        if '<feGaussianBlur' not in src and '<feDropShadow' not in src:
            continue
        if not any(s in src for s in SHADOW):
            continue
        log = run(build, p, 'z1', {'LAYER_LOG': '1', 'MEM_PEAKS': ''}, os.devnull)
        if 'LAYER kind=merge' in log:
            out.append(p)
    return out


def parse(log, ppm):
    num = lambda pat: int(m.group(1)) if (m := re.search(pat, log)) else None
    ms = re.search(r'frame_ms=([0-9.]+)', log)
    return {'frame_ms': float(ms.group(1)) if ms else None,
            'held': num(r'transient bytes held at flush: (\d+)'),
            'layers': num(r'layers begun: (\d+)'),
            'passed_through': num(r'layers passed through: (\d+)'),
            'peak_graphics': num(r'peak_graphics=(\d+)'),
            'hash': hashlib.md5(open(ppm, 'rb').read()).hexdigest() if os.path.exists(ppm) else None}


def measure(builds, files, framings, frames, repeat):
    rows = []
    ppm = f'{OUT}/frame.ppm'
    for path in files:
        for framing in framings:
            row = {'file': os.path.relpath(path, DA), 'framing': framing}
            for budget, benv in BUDGETS.items():
                for b in builds:
                    row.setdefault(b, {})[budget] = []
                for _ in range(repeat if budget == 'lifted' else 1):
                    for b in builds:
                        if os.path.exists(ppm):
                            os.remove(ppm)
                        log = run(b, path, framing, {**benv, 'FRAMES': str(frames)}, ppm)
                        row[b][budget].append(parse(log, ppm))
            for b in builds:
                runs = row[b]['lifted']
                best = min(runs, key=lambda r: r['frame_ms'] or float('inf'))
                default = row[b]['default'][0]
                row[b] = {'frame_ms': best['frame_ms'], 'held': best['held'], 'layers': best['layers'],
                          'peak_graphics': best['peak_graphics'], 'held_default': default['held'],
                          'passed_default': default['passed_through'], 'kept': default['hash'] == best['hash']}
            rows.append(row)
            print(row['file'], framing, *(f"{b}: {row[b]['frame_ms']:.1f} ms held {row[b]['held'] / 2**20:.1f} MiB"
                                          f"{'' if row[b]['kept'] else ' LOST at default'}" for b in builds),
                  flush=True)
    return rows


def summary(path, b0, b1):
    rows = json.load(open(path))
    mib = 2 ** 20
    print(f'{"framing":7s} {"frames":>6s} | frame ms (sum) {b0:>8s} {b1:>8s} ratio | held MiB mean / max '
          f'{b0:>13s} {b1:>13s} | over 128 MiB {b0}/{b1} | lost at default {b0}/{b1} | passed through at default')
    for fr in ('z1', 'z2', 'z4', 'hd'):
        sel = [r for r in rows if r['framing'] == fr]
        if not sel:
            continue
        t0, t1 = (sum(r[b]['frame_ms'] for r in sel) for b in (b0, b1))
        h = {b: [r[b]['held'] / mib for r in sel] for b in (b0, b1)}
        over = {b: sum(x > 128 for x in h[b]) for b in (b0, b1)}
        lost = {b: sum(not r[b]['kept'] for r in sel) for b in (b0, b1)}
        passed = {b: sum(r[b].get('passed_default') or 0 for r in sel) for b in (b0, b1)}
        print(f'{fr:7s} {len(sel):6d} | {"":14s} {t0:8.0f} {t1:8.0f} {t1 / t0:5.3f} | {"":19s} '
              f'{sum(h[b0]) / len(sel):6.1f} / {max(h[b0]):5.1f} {sum(h[b1]) / len(sel):6.1f} / {max(h[b1]):5.1f} | '
              f'{over[b0]:5d}/{over[b1]:<5d} | {lost[b0]:5d}/{lost[b1]:<5d} | {passed[b0]} -> {passed[b1]}')
    for r in rows:
        if not r[b0]['kept'] or not r[b1]['kept']:
            pt = lambda b: r[b].get('passed_default')
            print(f"  lost at default: {r['file']} {r['framing']}: {b0} {'kept' if r[b0]['kept'] else 'LOST'}, "
                  f"{b1} {'kept' if r[b1]['kept'] else 'LOST'} (held {r[b0]['held'] / mib:.1f} / {r[b1]['held'] / mib:.1f} MiB, "
                  f"passed through {pt(b0)} / {pt(b1)})")


def main():
    if sys.argv[1] == '--summary':
        summary(sys.argv[2], *(sys.argv[3:5] if len(sys.argv) > 4 else ('master_lsm', 'lsm')))
        return
    out_json = sys.argv[1]
    opts = dict(a.split('=', 1) for a in sys.argv[2:])
    builds = opts.get('builds', 'master_lsm,lsm').split(',')
    framings = opts.get('framings', 'z1,z2,z4,hd').split(',')
    os.makedirs(OUT, exist_ok=True)
    if 'list' in opts:
        files = [p if p.startswith('/') else f'{DA}/{p}' for p in json.load(open(opts['list']))]
    else:
        files = merged_files(builds[-1])
        json.dump([os.path.relpath(p, DA) for p in files], open(f'{OUT}/merged_files.json', 'w'), indent=1)
    rows = measure(builds, files, framings, int(opts.get('frames', 3)), int(opts.get('repeat', 2)))
    json.dump(rows, open(out_json, 'w'), indent=1)
    summary(out_json, builds[0], builds[-1])


if __name__ == '__main__':
    main()
