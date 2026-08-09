//! Headless GPU tests for the color-matrix image filter (`ImageFilter::ColorMatrix`
//! and the CSS filter-function constructors). The assertions are the property
//! checks that guard the classic feColorMatrix bug classes: exact Rec.709 luma
//! weights, identity round-trips, hue-rotate periodicity, clamping (no overflow
//! or NaN), and channel correctness. Skips when no GPU adapter is available.
#![cfg(feature = "wgpu")]

use femtovg::imgref::Img;
use femtovg::rgb::RGBA8;
use femtovg::{renderer::WGPURenderer, Canvas, Color, ImageFilter, ImageFlags, Paint, Path, PixelFormat, RenderTarget};

const W: u32 = 32;
const H: u32 = 32;

fn headless_device() -> Option<(wgpu::Device, wgpu::Queue)> {
    let instance = wgpu::Instance::default();
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::default(),
        force_fallback_adapter: false,
        compatible_surface: None,
        ..Default::default()
    }))
    .ok()?;
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: Some("femtovg color matrix test device"),
        required_features: wgpu::Features::empty(),
        required_limits: wgpu::Limits::downlevel_defaults().using_resolution(adapter.limits()),
        experimental_features: wgpu::ExperimentalFeatures::disabled(),
        memory_hints: wgpu::MemoryHints::MemoryUsage,
        trace: wgpu::Trace::default(),
    }))
    .ok()?;
    Some((device, queue))
}

fn output_texture(device: &wgpu::Device) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: Some("cmat out"),
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

/// Copy the `W`x`H` output texture back to the CPU and return the pixels in
/// row-major order (row 0 is the top of the canvas), one `[r,g,b,a]` per pixel.
fn read_pixels(device: &wgpu::Device, queue: &wgpu::Queue, target: &wgpu::Texture) -> Vec<[u8; 4]> {
    let unpadded = W * 4;
    let align = wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    let padded = unpadded.div_ceil(align) * align;
    let readback = device.create_buffer(&wgpu::BufferDescriptor {
        label: None,
        size: (padded * H) as u64,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    let mut enc = device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
    enc.copy_texture_to_buffer(
        wgpu::TexelCopyTextureInfo {
            texture: target,
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        wgpu::TexelCopyBufferInfo {
            buffer: &readback,
            layout: wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(padded),
                rows_per_image: Some(H),
            },
        },
        wgpu::Extent3d {
            width: W,
            height: H,
            depth_or_array_layers: 1,
        },
    );
    queue.submit(Some(enc.finish()));
    let slice = readback.slice(..);
    slice.map_async(wgpu::MapMode::Read, |_| {});
    device.poll(wgpu::PollType::wait_indefinitely()).unwrap();
    let mapped = slice.get_mapped_range().expect("readback");
    (0..(W * H) as usize)
        .map(|p| {
            let (x, y) = (p % W as usize, p / W as usize);
            let i = y * padded as usize + x * 4;
            [mapped[i], mapped[i + 1], mapped[i + 2], mapped[i + 3]]
        })
        .collect()
}

/// Fill a source image with `src`, apply `filter` into a target image, draw the
/// target to the output, and return the centre pixel `[r,g,b,a]`.
fn filtered_center(device: &wgpu::Device, queue: &wgpu::Queue, src: Color, filter: ImageFilter) -> [u8; 4] {
    let target = output_texture(device);

    let renderer = WGPURenderer::new(device.clone(), queue.clone());
    let mut canvas = Canvas::new(renderer).expect("canvas");
    canvas.set_size(W, H, 1.0);

    let source = canvas
        .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty())
        .expect("source image");
    canvas.set_render_target(RenderTarget::Image(source));
    canvas.clear_rect(0, 0, W, H, src);
    canvas.set_render_target(RenderTarget::Screen);

    let filtered = canvas
        .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty())
        .expect("target image");
    canvas.filter_image(filtered, filter, source);

    // Composite the filtered image onto the (white) output so we can read it back.
    canvas.clear_rect(0, 0, W, H, Color::white());
    let mut p = Path::new();
    p.rect(0.0, 0.0, W as f32, H as f32);
    canvas.fill_path(&p, &Paint::image(filtered, 0.0, 0.0, W as f32, H as f32, 0.0, 1.0));

    let commands = canvas.flush_to_output(&target);
    queue.submit(commands);

    let pixels = read_pixels(device, queue, &target);
    pixels[(H as usize / 2) * W as usize + W as usize / 2]
}

fn close(a: u8, b: i32) -> bool {
    (a as i32 - b).abs() <= 3
}

#[test]
fn color_matrix_filter_properties() {
    let Some((device, queue)) = headless_device() else {
        eprintln!("skipping: no wgpu adapter available");
        return;
    };
    let f = |src: Color, filter| filtered_center(&device, &queue, src, filter);
    let red = Color::rgb(255, 0, 0);
    let green = Color::rgb(0, 255, 0);
    let blue = Color::rgb(0, 0, 255);

    // 1. grayscale(1) uses Rec.709 luma (0.2126/0.7152/0.0722), NOT the 1/3
    //    average (85) or Rec.601 (76 for red).
    let g = f(red, ImageFilter::grayscale(1.0));
    println!("grayscale(red) = {g:?}");
    assert!(
        close(g[0], 54) && close(g[1], 54) && close(g[2], 54),
        "grayscale(red) luma must be ~54, got {g:?}"
    );
    assert!(
        close(f(green, ImageFilter::grayscale(1.0))[0], 182),
        "grayscale(green) luma must be ~182"
    );
    assert!(
        close(f(blue, ImageFilter::grayscale(1.0))[0], 18),
        "grayscale(blue) luma must be ~18"
    );

    // 2. Identities: these must all leave a color unchanged.
    for (name, filt) in [
        ("grayscale(0)", ImageFilter::grayscale(0.0)),
        ("saturate(1)", ImageFilter::saturate(1.0)),
        ("brightness(1)", ImageFilter::brightness(1.0)),
        ("contrast(1)", ImageFilter::contrast(1.0)),
        ("sepia(0)", ImageFilter::sepia(0.0)),
        ("invert(0)", ImageFilter::invert(0.0)),
        ("opacity(1)", ImageFilter::opacity(1.0)),
        ("hue_rotate(0)", ImageFilter::hue_rotate(0.0)),
        ("hue_rotate(2pi)", ImageFilter::hue_rotate(std::f32::consts::TAU)),
    ] {
        let probe = Color::rgb(200, 120, 40);
        let out = f(probe, filt);
        assert!(
            close(out[0], 200) && close(out[1], 120) && close(out[2], 40),
            "{name} must be an identity, got {out:?}"
        );
    }

    // 3. invert(1) of red -> cyan.
    let inv = f(red, ImageFilter::invert(1.0));
    assert!(
        close(inv[0], 0) && close(inv[1], 255) && close(inv[2], 255),
        "invert(red) must be cyan, got {inv:?}"
    );

    // 4. Clamp: brightness(5) of a bright color saturates to 255 (no overflow/NaN
    //    wrap to a small value).
    let bright = f(Color::rgb(200, 200, 200), ImageFilter::brightness(5.0));
    assert!(
        bright[0] == 255 && bright[1] == 255 && bright[2] == 255,
        "brightness(5) must clamp to 255, got {bright:?}"
    );

    // 5. hue-rotate periodicity: three 120-degree rotations return near identity.
    // A mid-tone gray-ish probe stays in gamut so clamping doesn't accumulate.
    let orig = [150u8, 120, 90];
    let mut cur = Color::rgb(orig[0], orig[1], orig[2]);
    for _ in 0..3 {
        let out = f(cur, ImageFilter::hue_rotate(std::f32::consts::TAU / 3.0));
        cur = Color::rgb(out[0], out[1], out[2]);
    }
    let final_rgb = [
        (cur.r * 255.0).round() as i32,
        (cur.g * 255.0).round() as i32,
        (cur.b * 255.0).round() as i32,
    ];
    for (ch, &o) in orig.iter().enumerate() {
        assert!(
            (final_rgb[ch] - o as i32).abs() <= 10,
            "3x hue_rotate(120deg) must return near the original; channel {ch}: {} vs {o}",
            final_rgb[ch]
        );
    }
}

/// The other tests filter solid colors, so they cannot see a vertically
/// mirrored filter pass. This one uploads an asymmetric source (top half red,
/// bottom half blue), runs sepia through `filter_image` and asserts the halves
/// land where Chromium's `ctx.filter = "sepia(1)"` puts them: top stays top.
#[test]
fn color_matrix_filter_preserves_orientation() {
    let Some((device, queue)) = headless_device() else {
        eprintln!("skipping: no wgpu adapter available");
        return;
    };
    let target = output_texture(&device);

    let renderer = WGPURenderer::new(device.clone(), queue.clone());
    let mut canvas = Canvas::new(renderer).expect("canvas");
    canvas.set_size(W, H, 1.0);

    // Upload the source from CPU data so its orientation is unambiguous:
    // row 0 of the upload is the top of the image when drawn.
    let mut src_pixels = vec![RGBA8::new(255, 0, 0, 255); (W * H) as usize];
    for p in &mut src_pixels[(W * H / 2) as usize..] {
        *p = RGBA8::new(0, 0, 255, 255);
    }
    let source = canvas
        .create_image(
            Img::new(src_pixels.as_slice(), W as usize, H as usize),
            ImageFlags::empty(),
        )
        .expect("source image");

    // `filter_image` renders into the target, and image render targets store
    // their content vertically flipped in texture space (see the render-target
    // notes in src/lib.rs), so the target must be created with FLIP_Y to be
    // sampled upright — exactly like the shadow-blur offscreen images.
    let filtered = canvas
        .create_image_empty(
            W as usize,
            H as usize,
            PixelFormat::Rgba8,
            ImageFlags::FLIP_Y | ImageFlags::PREMULTIPLIED,
        )
        .expect("target image");
    canvas.filter_image(filtered, ImageFilter::sepia(1.0), source);

    canvas.clear_rect(0, 0, W, H, Color::white());
    let mut p = Path::new();
    p.rect(0.0, 0.0, W as f32, H as f32);
    canvas.fill_path(&p, &Paint::image(filtered, 0.0, 0.0, W as f32, H as f32, 0.0, 1.0));

    let commands = canvas.flush_to_output(&target);
    queue.submit(commands);

    let pixels = read_pixels(&device, &queue, &target);
    let at = |x: u32, y: u32| pixels[(y * W + x) as usize];
    let top = at(W / 2, H / 4);
    let bottom = at(W / 2, 3 * H / 4);
    println!("top = {top:?}, bottom = {bottom:?}");

    // Chromium reference values for ctx.filter = "sepia(1)":
    // red (255,0,0) -> (100,89,69) and blue (0,0,255) -> (48,43,33).
    // A mirrored filter pass swaps the two, so these also pin the orientation.
    assert!(
        close(top[0], 100) && close(top[1], 89) && close(top[2], 69),
        "top half must be sepia(red) ~(100,89,69) — red was uploaded to the top — got {top:?}"
    );
    assert!(
        close(bottom[0], 48) && close(bottom[1], 43) && close(bottom[2], 33),
        "bottom half must be sepia(blue) ~(48,43,33) — blue was uploaded to the bottom — got {bottom:?}"
    );
}
