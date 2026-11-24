# Repository notes

<!-- quest-qualification-handoff -->
## Quest runtime qualification

Correct contour holes before attributing missing glyph details to XR downsampling.

Start with the [shared Quest handoff](https://github.com/rebeckerspecialties/BabylonNative/blob/wgpu/Documentation/QuestRuntimeHandoff.md) for verified artifact pins, the camera ownership audit, and links to related PRs. Use normal logging, confirm both eyes on the physical display, and verify Home passthrough before and after a single test. Do not use compositor submission count as visual evidence or trigger hosted simulator screenshots for this handoff.

- Implementation: Verify nested/touching contour cases; pair accuracy and performance checks rather than tuning screenshot thresholds.
- Device: Compare text counters and glyph holes at full native label resolution before stereo downsample.
