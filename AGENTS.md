# Repository notes

<!-- quest-qualification-handoff -->
## Quest runtime qualification

Canvas rendering cost and clipping are distinct from XR eye resolution.

Start with the [shared Quest handoff](https://github.com/rebeckerspecialties/BabylonNative/blob/wgpu/Documentation/QuestRuntimeHandoff.md) for verified artifact pins, the camera ownership audit, and links to related PRs. Use normal logging, confirm both eyes on the physical display, and verify Home passthrough before and after a single test. Do not use compositor submission count as visual evidence or trigger hosted simulator screenshots for this handoff.

- Implementation: Preserve nested clip/layer coverage and compare recording allocations without a GPU readback.
- Device: Inspect full-resolution label and icon edges in both eyes and check memory through modal reopen.
