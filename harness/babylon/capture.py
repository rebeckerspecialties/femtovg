#!/usr/bin/env python3
"""The Babylon.js visual tests that draw with a 2D canvas, as SVG: what each one draws on the canvases it turns into
textures (a DynamicTexture's context, a GUI AdvancedDynamicTexture), recorded call by call (recorder.js) while the
test's playground runs in headless Chromium on Babylon's NullEngine.

  capture.py [--config CONFIG.json ...] [--only ID,ID] [--frames N] [--width W --height H] OUT_DIR

For each test whose playground uses a 2D canvas, OUT_DIR gets <test>[__<n>].svg per canvas drawn on, <...>.png with
the canvas's own pixels, and manifest.json: the playground, the suites it is in, the canvas size, what the recording
left out, and how far Chromium's rendering of the SVG lands from the canvas pixels (the recording's own check).

Environment:
  BABYLON_DIST      directory holding babylon.max.js (or babylon.js) and babylon.gui.js (or .min.js), e.g. the
                    babylonjs and babylonjs-gui npm packages side by side (node_modules)
  BABYLON_CONFIGS   the suites' config.json files, separated by ':' (Babylon.js packages/tools/tests/test/
                    visualization/config.json, BabylonNative Apps/Playground/Scripts/config.json); --config adds
  SNIPPETS          the playground snippet cache (default OUT_DIR/../snippets); missing ones come from
                    https://snippet.babylonjs.com
  CHROMIUM          headless Chromium (as in corpus_run/common.py)
"""
import argparse, base64, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'corpus_run'))
from common import CHR  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--config', action='append', default=[])
ap.add_argument('--only', default='')
ap.add_argument('--frames', type=int, default=8)
ap.add_argument('--width', type=int, default=1024)
ap.add_argument('--height', type=int, default=768)
ap.add_argument('--budget', type=int, default=60000, help='virtual-time budget per test, ms')
ap.add_argument('--console', action='store_true', help="print each page's console")
args = ap.parse_args()
OUT = os.path.abspath(args.out)
os.makedirs(OUT, exist_ok=True)
SNIPPETS = os.environ.get('SNIPPETS', os.path.join(os.path.dirname(OUT), 'snippets'))
os.makedirs(SNIPPETS, exist_ok=True)
dist = os.environ.get('BABYLON_DIST')
if not dist:
    sys.exit('set BABYLON_DIST to the directory holding the babylonjs and babylonjs-gui packages')


def bundle(*names):
    for n in names:
        for sub in ('', 'babylonjs', 'babylonjs-gui'):
            p = os.path.join(dist, sub, n)
            if os.path.exists(p):
                return p
    sys.exit(f'none of {names} under {dist}')


BABYLON = bundle('babylon.max.js', 'babylon.js')
GUI = bundle('babylon.gui.js', 'babylon.gui.min.js')
# The extensions a playground may use, where the distribution has them.
EXTRAS = [p for p in (os.path.join(dist, d, f) for d, f in (
    ('babylonjs-loaders', 'babylonjs.loaders.js'), ('babylonjs-materials', 'babylonjs.materials.js'),
    ('babylonjs-serializers', 'babylonjs.serializers.js'), ('babylonjs-procedural-textures', 'babylonjs.proceduralTextures.js'),
    ('babylonjs-addons', 'babylonjs.addons.js'))) if os.path.exists(p)]
configs = [c for c in os.environ.get('BABYLON_CONFIGS', '').split(':') if c] + args.config


def snippet(pid):
    name, *ver = pid.strip('#').split('#')
    path = f'{SNIPPETS}/{name}_{ver[0] if ver else "0"}.json'
    if not os.path.exists(path):
        url = f'https://snippet.babylonjs.com/{name}/{ver[0] if ver else "0"}'
        data = urllib.request.urlopen(url, timeout=30).read()
        open(path, 'wb').write(data)
        time.sleep(0.2)
    payload = json.loads(json.load(open(path))['jsonPayload'])
    code = payload.get('code', '')
    if code.startswith('{"v":'):
        v2 = json.loads(code)
        if v2.get('language', 'JS') != 'JS':
            return None
        code = '\n'.join(v2.get('files', {}).values())
    return code


def uses_canvas(code):
    return bool(re.search(r'AdvancedDynamicTexture', code)
                or (re.search(r'DynamicTexture\b', code) and re.search(r'getContext\s*\(', code))
                or re.search(r'createElement\s*\(\s*["\']canvas', code))


tests = {}
for cfg in configs:
    suite = 'babylonnative' if 'Playground' in cfg else 'babylonjs'
    for t in json.load(open(cfg, encoding='utf-8-sig')).get('tests', []):
        pid = t.get('playgroundId')
        if pid:
            e = tests.setdefault(pid, {'titles': set(), 'suites': set(), 'references': set()})
            e['titles'].add(t.get('title', pid))
            e['suites'].add(suite)
            if t.get('referenceImage'):
                e['references'].add(t['referenceImage'])
only = {p if p.startswith('#') else '#' + p for p in args.only.split(',') if p}

PAGE = '''<!doctype html><html><head><meta charset="utf-8"><base href="https://playground.babylonjs.com/">
<style>html,body{margin:0}</style>
<script>
// Headless Chromium has no display to pace animation frames under virtual time: a timer stands in, for the
// playgrounds that run their own render loop.
window.requestAnimationFrame = function (cb) { return setTimeout(function () { cb(performance.now()); }, 16); };
window.cancelAnimationFrame = function (id) { clearTimeout(id); };
</script>
<script src="file://@@RECORDER@@"></script>
<script src="file://@@BABYLON@@"></script>
<script src="file://@@GUI@@"></script>
@@EXTRAS@@
</head><body><script>
var canvas = document.createElement('canvas');
canvas.width = @@WIDTH@@; canvas.height = @@HEIGHT@@;
var engine;
if ('@@ENGINE@@' === 'webgl') {
  document.body.appendChild(canvas);
  engine = new BABYLON.Engine(canvas, true, {preserveDrawingBuffer: true, stencil: true});
} else {
  engine = new BABYLON.NullEngine({renderWidth: @@WIDTH@@, renderHeight: @@HEIGHT@@, textureSize: 1024,
                                   deterministicLockstep: false, lockstepMaxSteps: 1});
  engine.getRenderingCanvas = function () { return canvas; };
}
var _native = undefined;
function finish(error) {
  var out = {error: error || null, canvases: []};
  try {
    CanvasRecorder.canvases().forEach(function (c) {
      var r = CanvasRecorder.svg(c);
      var png = null;
      try { png = c.toDataURL('image/png'); } catch (e) { r.warnings.push('pixels unreadable: ' + e.message); }
      out.canvases.push({width: c.width, height: c.height, svg: r.svg, warnings: r.warnings, ops: r.ops, png: png});
    });
  } catch (e) { out.error = (out.error || '') + ' ' + e.message; }
  document.body.setAttribute('data-capture', btoa(unescape(encodeURIComponent(JSON.stringify(out)))));
}
async function main() {
@@CODE@@
  var scene;
  if (typeof delayCreateScene === 'function') scene = await delayCreateScene(engine, canvas);
  else if (typeof createScene === 'function') scene = await createScene(engine, canvas);
  else if (typeof Playground !== 'undefined') scene = await Playground.CreateScene(engine, canvas);
  if (!scene) throw new Error('no scene');
  // A NullEngine may never call a material ready: wait for the scene a while at most.
  try { await Promise.race([scene.whenReadyAsync(), new Promise(function (r) { setTimeout(r, 3000); })]); } catch (e) {}
  for (var i = 0; i < @@FRAMES@@; i++) { scene.render(); await new Promise(function (r) { setTimeout(r, 16); }); }
  // One full redraw of every GUI texture, recorded from a clear canvas.
  var guis = scene.textures.filter(function (t) { return BABYLON.GUI && t instanceof BABYLON.GUI.AdvancedDynamicTexture; });
  guis.forEach(function (t) {
    t.useInvalidateRectOptimization = false;
    var c = t.getContext && t.getContext().canvas;
    if (c) CanvasRecorder.restart(c);
    t.markAsDirty();
  });
  if (guis.length) scene.render();
}
window.addEventListener('load', function () {
  main().then(function () { finish(); }, function (e) { finish(String(e && e.stack || e)); });
});
</script></body></html>
'''


def run(pid, code, tmp, engine='null'):
    code = re.sub(r'^(\s*)export\s+(default\s+)?', r'\1', code, flags=re.M).replace('</script', '<\\/script')
    page = (PAGE.replace('@@RECORDER@@', os.path.join(HERE, 'recorder.js')).replace('@@BABYLON@@', BABYLON)
            .replace('@@GUI@@', GUI).replace('@@WIDTH@@', str(args.width)).replace('@@HEIGHT@@', str(args.height))
            .replace('@@FRAMES@@', str(args.frames)).replace('@@ENGINE@@', engine)
            .replace('@@EXTRAS@@', '\n'.join(f'<script src="file://{x}"></script>' for x in EXTRAS))
            .replace('@@CODE@@', code))
    html = os.path.join(tmp, 'test.html')
    open(html, 'w').write(page)
    gpu = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] if engine == 'webgl' else ['--disable-gpu']
    log = ['--enable-logging=stderr', '--v=0'] if args.console else []
    r = subprocess.run([CHR, '--headless', *gpu, *log, '--allow-file-access-from-files', '--hide-scrollbars',
                        f'--window-size={args.width},{args.height}', f'--user-data-dir={tmp}/profile-{engine}',
                        f'--virtual-time-budget={args.budget}', '--dump-dom', f'file://{html}'],
                       capture_output=True, text=True, timeout=300)
    if args.console:
        for line in r.stderr.splitlines():
            if 'CONSOLE' in line or 'Uncaught' in line:
                print('   ', line[:300], flush=True)
    m = re.search(r'data-capture="([^"]*)"', r.stdout)
    if not m:
        return {'error': 'the page never finished (budget, a hang, or a load error)', 'canvases': []}
    return json.loads(base64.b64decode(m.group(1)).decode('utf-8'))


def check(svg_path, png_path, w, h, tmp):
    """Chromium's rendering of the SVG against the canvas's own pixels, both over white."""
    html = os.path.join(tmp, 'check.html')
    open(html, 'w').write(f'<!doctype html><html><body style="margin:0;background:#fff">'
                          f'<img src="file://{svg_path}" width="{w}" height="{h}" style="display:block"></body></html>')
    shot = os.path.join(tmp, 'check.png')
    subprocess.run([CHR, '--headless', '--disable-gpu', '--allow-file-access-from-files', '--hide-scrollbars',
                    f'--user-data-dir={tmp}/profile2', '--force-device-scale-factor=1', f'--window-size={w},{h}',
                    '--default-background-color=FFFFFFFF', f'--screenshot={shot}', f'file://{html}'],
                   capture_output=True, timeout=120)
    a = Image.open(shot).convert('RGB')
    canvas = Image.open(png_path).convert('RGBA')
    white = Image.new('RGBA', canvas.size, (255, 255, 255, 255))
    b = Image.alpha_composite(white, canvas).convert('RGB')
    A = np.asarray(a, dtype=np.int16)[:h, :w]
    B = np.asarray(b, dtype=np.int16)[:A.shape[0], :A.shape[1]]
    diff = np.abs(A - B).max(axis=2)
    return {'px20': round(100 * float((diff > 20).mean()), 3), 'px8': round(100 * float((diff > 8).mean()), 3),
            'max': int(diff.max())}


def slug(title):
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:60]


manifest = []
used = set()
for pid, e in sorted(tests.items(), key=lambda kv: sorted(kv[1]['titles'])[0].lower()):
    if only and pid not in only:
        continue
    try:
        code = snippet(pid)
    except Exception as ex:
        print(f'{pid}: no snippet ({ex})', flush=True)
        continue
    if code is None or not uses_canvas(code):
        continue
    title = sorted(e['titles'])[0]
    # A title two playgrounds share gets the playground's ID too.
    stem = slug(title)
    if stem in used:
        stem += '--' + slug(pid)
    used.add(stem)
    with tempfile.TemporaryDirectory() as tmp:
        got = run(pid, code, tmp)
        if got.get('error') and not got['canvases']:
            # What needs a real GPU context: a WebGL engine on SwiftShader.
            retry = run(pid, code, tmp, 'webgl')
            if retry['canvases'] or not retry.get('error'):
                got = dict(retry, engine='webgl')
        entry = {'playgroundId': pid, 'title': title, 'titles': sorted(e['titles']), 'suites': sorted(e['suites']),
                 'referenceImages': sorted(e['references']), 'engine': got.get('engine', 'null'),
                 'error': got.get('error'), 'canvases': []}
        for n, c in enumerate(got['canvases']):
            name = stem + (f'__{n}' if len(got['canvases']) > 1 else '')
            svg_path = os.path.join(OUT, name + '.svg')
            open(svg_path, 'w').write(c['svg'])
            item = {'file': name + '.svg', 'width': c['width'], 'height': c['height'], 'ops': c['ops'],
                    'warnings': c['warnings']}
            if c.get('png'):
                png_path = os.path.join(OUT, name + '.png')
                open(png_path, 'wb').write(base64.b64decode(c['png'].split(',', 1)[1]))
                item['check'] = check(svg_path, png_path, c['width'], c['height'], tmp)
            entry['canvases'].append(item)
    manifest.append(entry)
    checks = ', '.join(f"{c['file']} {c.get('check', {}).get('px20', '?')} %" for c in entry['canvases'])
    print(f"{pid} {title[:50]}: {len(entry['canvases'])} canvases{' ERROR ' + entry['error'][:120] if entry['error'] else ''} {checks}", flush=True)
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(len(manifest), 'tests,', sum(len(e['canvases']) for e in manifest), 'canvases')
