"""Applies (or with 'revert' undoes, from backups) the pass counter to a worktree's wgpu backend: a counter of render
passes begun, read by the harness under --cfg harness_pass_count. Experiment only, never committed."""
import pathlib, shutil, sys
wt, mode = pathlib.Path(sys.argv[1]), sys.argv[2]
files = [wt / 'src/renderer/wgpu.rs', wt / 'src/renderer.rs']
if mode == 'revert':
    for f in files:
        shutil.copy(str(f) + '.keep', f); pathlib.Path(str(f) + '.keep').unlink()
    sys.exit()
for f in files:
    shutil.copy(f, str(f) + '.keep')
s = files[0].read_text()
old = "        let mut rpass = self.encoder.begin_render_pass(&wgpu::RenderPassDescriptor {"
assert s.count(old) == 1
s = s.replace(old, "        RENDER_PASSES.fetch_add(1, std::sync::atomic::Ordering::Relaxed);\n" + old)
s += """
static RENDER_PASSES: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
/// Experiment: render passes begun so far.
pub fn render_passes_begun() -> usize {
    RENDER_PASSES.load(std::sync::atomic::Ordering::Relaxed)
}
"""
files[0].write_text(s)
s = files[1].read_text()
old = "pub use wgpu::{WGPURenderOutput, WGPURenderer};"
assert s.count(old) == 1
files[1].write_text(s.replace(old, "pub use wgpu::{render_passes_begun, WGPURenderOutput, WGPURenderer};"))
