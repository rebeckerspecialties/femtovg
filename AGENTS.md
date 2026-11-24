# Repository notes

<!-- quest-qualification-handoff -->
## Quest runtime qualification

Released transient images must survive queued drawing and flush.

Start with the [shared Quest handoff](https://github.com/rebeckerspecialties/BabylonNative/blob/wgpu/Documentation/QuestRuntimeHandoff.md) for verified artifact pins, the camera ownership audit, and links to related PRs. Use normal logging, confirm both eyes on the physical display, and verify Home passthrough before and after a single test. Do not use compositor submission count as visual evidence or trigger hosted simulator screenshots for this handoff.

- Implementation: Pin delayed flush, reuse and shutdown ordering while keeping the image lifetime bounded.
- Device: Open/close text-heavy modals repeatedly and verify pixels after resource reuse.
