//! The WGPU backend builds a render pipeline only from fixed-function state:
//! blend, topology, cull mode, stencil and render target. The shader type and
//! the glyph texture reach the shader through the uniform and the bind group,
//! so a pipeline cache keyed on them built identical pipelines once per shader
//! type, and again for glyph quads.
//!
//! A cached pipeline lives for as long as frames bind it and goes after the
//! first frame that does not. Within a frame the pipelines looked up last are
//! found by comparing keys, without the cache, and that changes neither their
//! lifetime nor which pipeline a draw gets.
//!
//! Live pipelines are read from wgpu's internal counters, enabled by the
//! `counters` feature on the `wgpu` dev-dependency. Feature unification also
//! enables counters in examples. We accept the extra atomic updates so
//! these tests run with just the `wgpu` feature.
#![cfg(feature = "wgpu")]

use femtovg::{
    renderer::WGPURenderer, BlendFactor, Canvas, Color, DrawCommand, GlyphDrawCommands, ImageFlags, Paint, Path,
    PixelFormat, Quad,
};

mod common;
use common::{headless_device, render_rgba};

/// Large enough to hold the 48 px square at (8, 8); the tests count pipelines, not pixels.
const SIZE: u32 = 64;

fn target(device: &wgpu::Device) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: Some("pipeline key target"),
        size: wgpu::Extent3d {
            width: SIZE,
            height: SIZE,
            depth_or_array_layers: 1,
        },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Rgba8Unorm,
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
        view_formats: &[],
    })
}

fn rect() -> Path {
    let mut path = Path::new();
    path.rect(8.0, 8.0, 48.0, 48.0);
    path
}

/// Flushes `canvas` into `target` and returns how many render pipelines are alive on `device`.
fn live_pipelines_after_flush(
    device: &wgpu::Device,
    queue: &wgpu::Queue,
    canvas: &mut Canvas<WGPURenderer>,
    target: &wgpu::Texture,
) -> isize {
    let commands = canvas
        .flush_to_output(target)
        .expect("flush_to_output produced no command buffer for a frame with draws");
    queue.submit([commands]);
    device
        .poll(wgpu::PollType::wait_indefinitely())
        .expect("device poll failed");
    let live = device.get_internal_counters().hal.render_pipelines.read();
    // Without the `counters` feature every counter reads zero, and the tests' comparisons would pass vacuously.
    assert!(
        live > 0,
        "no live render pipelines counted; is wgpu's `counters` feature on?"
    );
    live
}

/// Filling one rectangle with each kind of paint, eight shader types between
/// them, needs no pipeline beyond those a solid fill of it needs.
#[test]
fn fills_that_differ_only_in_paint_share_their_pipelines() {
    let Some((device, queue)) = headless_device() else {
        return;
    };
    let target = target(&device);
    let mut canvas = Canvas::new(WGPURenderer::new(device.clone(), queue.clone())).expect("canvas");
    canvas.set_size(SIZE, SIZE, 1.0);
    let pattern = canvas
        .create_image_empty(4, 4, PixelFormat::Rgba8, ImageFlags::empty())
        .expect("pattern image");

    let (red, blue) = (Color::rgb(255, 0, 0), Color::rgb(0, 0, 255));
    let stops = [(0.0, red), (0.5, Color::rgb(0, 255, 0)), (1.0, blue)];
    let solid = Paint::color(red);

    canvas.fill_path(&rect(), &solid);
    let solid_only = live_pipelines_after_flush(&device, &queue, &mut canvas, &target);

    let paints = [
        solid,
        Paint::linear_gradient(8.0, 0.0, 56.0, 0.0, red, blue),
        Paint::linear_gradient_stops(8.0, 0.0, 56.0, 0.0, stops),
        Paint::radial_gradient(32.0, 32.0, 4.0, 24.0, red, blue),
        Paint::box_gradient(16.0, 16.0, 32.0, 32.0, 4.0, 8.0, red, blue),
        Paint::conic_gradient(32.0, 32.0, red, blue),
        Paint::conic_gradient_stops(32.0, 32.0, stops),
        Paint::two_point_radial_gradient(24.0, 32.0, 4.0, 40.0, 32.0, 24.0, red, blue),
        Paint::two_point_radial_gradient_stops(24.0, 32.0, 4.0, 40.0, 32.0, 24.0, stops),
        Paint::image(pattern, 8.0, 8.0, 4.0, 4.0, 0.0, 1.0),
    ];
    for paint in &paints {
        canvas.fill_path(&rect(), paint);
    }
    let every_paint = live_pipelines_after_flush(&device, &queue, &mut canvas, &target);

    assert_eq!(
        every_paint, solid_only,
        "a solid fill needs {solid_only} pipelines, but the same fill in every kind of paint left {every_paint} alive"
    );
}

/// A glyph quad is drawn with the same fixed-function state as the interior of
/// a convex fill, so it shares that fill's pipeline.
#[test]
fn glyph_quads_share_the_pipeline_of_a_plain_fill() {
    let Some((device, queue)) = headless_device() else {
        return;
    };
    let target = target(&device);
    let mut canvas = Canvas::new(WGPURenderer::new(device.clone(), queue.clone())).expect("canvas");
    canvas.set_size(SIZE, SIZE, 1.0);
    let atlas = canvas
        .create_image_empty(8, 8, PixelFormat::Gray8, ImageFlags::empty())
        .expect("glyph atlas");
    let solid = Paint::color(Color::rgb(255, 0, 0));

    canvas.fill_path(&rect(), &solid);
    let fill_only = live_pipelines_after_flush(&device, &queue, &mut canvas, &target);

    canvas.fill_path(&rect(), &solid);
    let glyph = Quad {
        x0: 8.0,
        y0: 8.0,
        s0: 0.0,
        t0: 0.0,
        x1: 16.0,
        y1: 16.0,
        s1: 1.0,
        t1: 1.0,
    };
    canvas.draw_glyph_commands(
        GlyphDrawCommands {
            alpha_glyphs: vec![DrawCommand {
                image_id: atlas,
                quads: vec![glyph],
            }],
            color_glyphs: Vec::new(),
        },
        &solid,
    );
    let with_glyphs = live_pipelines_after_flush(&device, &queue, &mut canvas, &target);

    assert_eq!(
        with_glyphs, fill_only,
        "a solid fill needs {fill_only} pipelines, but adding a glyph quad in the same paint left {with_glyphs} alive"
    );
}

/// Every fill of a frame after its first finds the two pipelines of a convex
/// fill among those the frame looked up last, not in the cache. They still
/// count as used: frames of fills keep them alive, and the first frame without
/// a fill drops them.
#[test]
fn a_pipeline_lives_until_a_frame_does_not_bind_it() {
    let Some((device, queue)) = headless_device() else {
        return;
    };
    let target = target(&device);
    let mut canvas = Canvas::new(WGPURenderer::new(device.clone(), queue.clone())).expect("canvas");
    canvas.set_size(SIZE, SIZE, 1.0);
    let solid = Paint::color(Color::rgb(255, 0, 0));

    canvas.clear_rect(0, 0, SIZE, SIZE, Color::black());
    let clear_only = live_pipelines_after_flush(&device, &queue, &mut canvas, &target);

    let mut frame_of_fills = || {
        for _ in 0..4 {
            canvas.fill_path(&rect(), &solid);
        }
        live_pipelines_after_flush(&device, &queue, &mut canvas, &target)
    };
    let fills_only = frame_of_fills();
    assert!(
        fills_only > clear_only,
        "four fills left {fills_only} pipelines alive and a clear {clear_only}; the frames must differ for the last check to mean anything"
    );
    for frame in 2..=3 {
        let live = frame_of_fills();
        assert_eq!(
            live, fills_only,
            "the first frame of fills left {fills_only} pipelines alive, frame {frame} of the same fills {live}"
        );
    }

    canvas.clear_rect(0, 0, SIZE, SIZE, Color::black());
    let after_idle_frame = live_pipelines_after_flush(&device, &queue, &mut canvas, &target);
    assert_eq!(
        after_idle_frame, clear_only,
        "a clear needs {clear_only} pipelines, but {after_idle_frame} are alive after a frame that drew nothing else"
    );
}

/// The blend factors of the Porter-Duff operators: each of their 36 pairs is a
/// blend state of its own.
const FACTORS: [BlendFactor; 6] = [
    BlendFactor::Zero,
    BlendFactor::One,
    BlendFactor::SrcAlpha,
    BlendFactor::OneMinusSrcAlpha,
    BlendFactor::DstAlpha,
    BlendFactor::OneMinusDstAlpha,
];

/// Fills one square per entry of `order`: square `i` sits in its own cell of a
/// six by six grid and is blended with the `i`th pair of `FACTORS`.
fn blended_squares(device: &wgpu::Device, queue: &wgpu::Queue, order: &[usize]) -> Vec<u8> {
    render_rgba(device, queue, SIZE, SIZE, Color::rgba(40, 90, 200, 128), |canvas| {
        let paint = Paint::color(Color::rgba(220, 120, 30, 160));
        for &i in order {
            canvas.global_composite_blend_func(FACTORS[i / 6], FACTORS[i % 6]);
            let mut square = Path::new();
            square.rect(2.0 + 10.0 * (i % 6) as f32, 2.0 + 10.0 * (i / 6) as f32, 6.0, 6.0);
            canvas.fill_path(&square, &paint);
        }
    })
}

/// A frame keeps only so many of the pipelines it looked up at hand. One that
/// rotates through more, and comes back to pipelines it has let go, still draws
/// every fill with its own: the squares are disjoint, so drawing them one
/// square at a time instead gives the same picture.
#[test]
fn a_frame_rotating_through_many_pipelines_draws_each_fill_with_its_own() {
    let Some((device, queue)) = headless_device() else {
        return;
    };
    // Five squares in turn, ten pipelines, moving on by one square each time; then all of it again.
    let squares = FACTORS.len() * FACTORS.len();
    let sweep = (0..squares).flat_map(|first| first..(first + 5).min(squares));
    let rotating: Vec<usize> = sweep.clone().chain(sweep).collect();
    let mut square_by_square = rotating.clone();
    square_by_square.sort_unstable();

    assert!(
        blended_squares(&device, &queue, &rotating) == blended_squares(&device, &queue, &square_by_square),
        "the same fills on disjoint squares gave different pictures in two orders"
    );
}
