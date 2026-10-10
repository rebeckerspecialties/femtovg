# Babylon.js canvas tests as SVG

BabylonNative draws a page's 2D canvas with femtovg, so the Babylon.js visual
tests that draw on one - a `DynamicTexture`'s context, or a GUI
`AdvancedDynamicTexture`, which lays out its controls and draws them on one -
are femtovg conformance and performance drivers (femtovg/femtovg#280, #281,
#283). `capture.py` turns each into the SVG of what it draws, so that the
corpus harness renders it like any other file.

    BABYLON_DIST=../BabylonNative/Apps/node_modules \
    BABYLON_CONFIGS=../Babylon.js/packages/tools/tests/test/visualization/config.json:../BabylonNative/Apps/Playground/Scripts/config.json \
    harness/babylon/capture.py out/

For every test of those suites whose playground uses a 2D canvas, it runs the
playground in headless Chromium on Babylon's NullEngine (no WebGL is needed:
the 2D canvases draw as they would in the playground), with `recorder.js`
recording each canvas call by call, then lets every GUI texture redraw itself
whole once. Each canvas drawn on becomes `<test>[__<n>].svg` beside the
canvas's own pixels (`.png`), and `manifest.json` records the playground, the
suites and reference images, the canvas size, anything the recording left out,
and how far Chromium's rendering of the SVG lands from the canvas pixels -
the recording's own check.

`recorder.js` keeps a path in device space as it is built and writes it in the
user space of the call that paints it; styles, gradients, text, images, clips,
global alpha, blur filters, shadows and blend modes come from the context's
state. A `clearRect` over the whole canvas starts over. SVG has no partial
clear or Porter-Duff operator: those are listed in the warnings.

`corpus/babylon` holds the SVGs of one capture (with its manifest).
