//! Two frames flushed before either is submitted, then submitted together,
//! each reach their own target.
//!
//! `WGPURenderer::render` uploads a frame's vertices and uniforms with
//! `Queue::write_buffer`. wgpu runs those writes at the next `Queue::submit`,
//! ahead of every command buffer in it, so what a frame's command buffer reads
//! is whatever the buffers hold once all the writes queued before that submit
//! have run. The bundled examples submit right after each flush; a caller
//! rendering several targets and submitting once, or any other pattern that
//! flushes again before submitting, must get its first frame all the same.
#![cfg(feature = "wgpu")]

use femtovg::{renderer::WGPURenderer, Canvas, Color, Paint, Path};

mod common;
use common::{headless_device, read_rgba, render_rgba};

const W: u32 = 32;
const H: u32 = 32;

fn target(device: &wgpu::Device, label: &str) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: Some(label),
        size: wgpu::Extent3d {
            width: W,
            height: H,
            depth_or_array_layers: 1,
        },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Rgba8Unorm,
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
        view_formats: &[],
    })
}

/// A square of `color` with its corner at (`at`, `at`). The two frames place
/// theirs apart, so their vertices differ, and color them apart, so their
/// uniforms differ, while recording the same commands with the same number
/// of vertices: a frame drawn from the other frame's uploads is that frame.
fn square(canvas: &mut Canvas<WGPURenderer>, at: f32, color: Color) {
    let mut path = Path::new();
    path.rect(at, at, 12.0, 12.0);
    canvas.fill_path(&path, &Paint::color(color));
}

fn red_square(canvas: &mut Canvas<WGPURenderer>) {
    square(canvas, 4.0, Color::rgb(255, 0, 0));
}

fn blue_square(canvas: &mut Canvas<WGPURenderer>) {
    square(canvas, 16.0, Color::rgb(0, 0, 255));
}

/// `got` must be `want` pixel for pixel. A target holding `other`, the frame
/// flushed through the same renderer, is named as such: that is what the
/// first frame's command buffer draws when the second flush replaced its
/// uploads before they were submitted.
fn assert_frame(which: &str, got: &[u8], want: &[u8], other: &[u8]) {
    assert_eq!(got.len(), want.len());
    if got == want {
        return;
    }
    if got == other {
        panic!("the {which} target holds the other frame");
    }
    let first = (0..got.len()).find(|&i| got[i] != want[i]).unwrap() / 4;
    panic!(
        "the {which} target differs at ({}, {}): {:?} instead of {:?}",
        first as u32 % W,
        first as u32 / W,
        &got[first * 4..first * 4 + 4],
        &want[first * 4..first * 4 + 4],
    );
}

#[test]
fn two_flushes_submitted_together_each_reach_their_own_target() {
    let Some((device, queue)) = headless_device() else {
        return;
    };
    let (first, second) = (target(&device, "first frame"), target(&device, "second frame"));
    let mut canvas = Canvas::new(WGPURenderer::new(device.clone(), queue.clone())).expect("canvas");
    canvas.set_size(W, H, 1.0);

    canvas.clear_rect(0, 0, W, H, Color::white());
    red_square(&mut canvas);
    let first_commands = canvas
        .flush_to_output(&first)
        .expect("flush_to_output produced no command buffer for a frame with draws");
    canvas.clear_rect(0, 0, W, H, Color::white());
    blue_square(&mut canvas);
    let second_commands = canvas
        .flush_to_output(&second)
        .expect("flush_to_output produced no command buffer for a frame with draws");
    queue.submit([first_commands, second_commands]);

    // Each frame flushed and submitted on its own, the pattern every other test uses.
    let red = render_rgba(&device, &queue, W, H, Color::white(), red_square);
    let blue = render_rgba(&device, &queue, W, H, Color::white(), blue_square);
    assert_frame("first", &read_rgba(&device, &queue, &first, None), &red, &blue);
    assert_frame("second", &read_rgba(&device, &queue, &second, None), &blue, &red);
}
