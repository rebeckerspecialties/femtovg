# Babylon.js canvas tests

What the Babylon.js visual tests draw on 2D canvases they turn into textures,
as SVG: GUI `AdvancedDynamicTexture`s (labels, panels, gradients, input
fields, sliders, holographic slates) and `DynamicTexture` contexts (the
BabylonNative canvas test, clipping, a 65,536-rectangle normal map). These are
the scenes BabylonNative draws with femtovg (femtovg/femtovg#280, #281, #283).

Captured by `harness/babylon/capture.py` from the tests of Babylon.js
(`packages/tools/tests/test/visualization/config.json`) and BabylonNative
(`Apps/Playground/Scripts/config.json`), with Babylon.js 9.22.1: 66 canvases
from 47 of the 55 tests whose playground uses a 2D canvas. `manifest.json`
gives each file's playground, test titles, suites, reference images, canvas
size, what the recording left out, and how far Chromium's rendering of the
SVG lands from the canvas's own pixels (median 0.0 %, at most 0.33 % of the
pixels beyond 20/255). Not captured: the two Havok tests (the physics module
is not loaded), terrain-erosion (WebGPU storage buffers), and five frame-graph
and post-process tests that draw no 2D canvas outside the playground.
`gui-images-in-grid` is left out: it is ten embedded raster images (5.6 MB).

The tests are Babylon.js's (Apache-2.0) and the drawing their playgrounds',
from the Babylon.js snippet server. A few files embed raster images the
playgrounds load (`default-render-pipeline`, `gui-slate__1`, `gui-slate__2`,
`show-multiple-guis__1`, `sliders`), from Babylon's assets.
