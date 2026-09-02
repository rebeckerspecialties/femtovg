//! Effect-chain matrix probe: runs a filter chain spec over a structured
//! 256x256 source and writes the result composited over white as PPM.
//! Usage: `_chainmx <spec> <out.ppm>` where spec is comma-separated ops:
//! `sepia:1,blur:3,bright:1.4,contrast:1.2,gray:1,invert:1,opacity:0.5,sat:2,hue:90`.
#![cfg(feature = "wgpu")]

use femtovg::{renderer::WGPURenderer, Canvas, Color, ImageFilter, ImageFlags, ImageSource, Paint, Path};

const W: u32 = 256;
const H: u32 = 256;

fn source_pixels() -> Vec<rgb::RGBA8> {
    let mut px = vec![rgb::RGBA8::new(0, 0, 0, 0); (W * H) as usize];
    for y in 0..H as usize {
        for x in 0..W as usize {
            let on = ((x / 16) + (y / 16)) % 2 == 0;
            px[y * W as usize + x] = if on {
                rgb::RGBA8::new(60, 120, 220, 255)
            } else {
                rgb::RGBA8::new(240, 200, 60, 255)
            };
            let (dx, dy) = (x as f32 - 96.0, y as f32 - 72.0);
            if dx * dx + dy * dy <= 40.0 * 40.0 {
                px[y * W as usize + x] = rgb::RGBA8::new(200, 30, 30, 255);
            }
            if (160..200).contains(&y) {
                // premultiplied half-alpha green (straight 40,180,40 @ 128)
                px[y * W as usize + x] = rgb::RGBA8::new(20, 90, 20, 128);
            }
        }
    }
    px
}

fn parse(spec: &str) -> Vec<ImageFilter> {
    spec.split(',')
        .filter(|s| !s.is_empty())
        .map(|op| {
            let (name, v) = op.split_once(':').unwrap_or((op, "1"));
            let v: f32 = v.parse().expect("op value");
            match name {
                "blur" => ImageFilter::GaussianBlur { sigma: v },
                "sepia" => ImageFilter::sepia(v),
                "gray" => ImageFilter::grayscale(v),
                "bright" => ImageFilter::brightness(v),
                "contrast" => ImageFilter::contrast(v),
                "invert" => ImageFilter::invert(v),
                "opacity" => ImageFilter::opacity(v),
                "sat" => ImageFilter::saturate(v),
                "hue" => ImageFilter::hue_rotate(v.to_radians()),
                other => panic!("unknown op {other}"),
            }
        })
        .collect()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let filters = parse(&args[1]);
    let out = &args[2];

    let instance = wgpu::Instance::default();
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).unwrap();
    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: None,
        required_features: wgpu::Features::empty(),
        required_limits: wgpu::Limits::downlevel_defaults().using_resolution(adapter.limits()),
        experimental_features: wgpu::ExperimentalFeatures::disabled(),
        memory_hints: wgpu::MemoryHints::MemoryUsage,
        trace: wgpu::Trace::default(),
    }))
    .unwrap();
    let renderer = WGPURenderer::new(device.clone(), queue.clone());
    let mut canvas = Canvas::new(renderer).unwrap();
    canvas.set_size(W, H, 1.0);

    let src_px = source_pixels();
    let src = canvas
        .create_image(
            ImageSource::from(imgref::Img::new(&src_px[..], W as usize, H as usize)),
            ImageFlags::PREMULTIPLIED,
        )
        .unwrap();
    let dst = canvas
        .create_image_empty(
            W as usize,
            H as usize,
            femtovg::PixelFormat::Rgba8,
            ImageFlags::PREMULTIPLIED | ImageFlags::FLIP_Y,
        )
        .unwrap();
    canvas.filter_image_chain(dst, &filters, src);

    let target = device.create_texture(&wgpu::TextureDescriptor {
        label: None,
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
    });
    canvas.clear_rect(0, 0, W, H, Color::white());
    let mut p = Path::new();
    p.rect(0.0, 0.0, W as f32, H as f32);
    canvas.fill_path(&p, &Paint::image(dst, 0.0, 0.0, W as f32, H as f32, 0.0, 1.0));
    let commands = canvas.flush_to_output(&target);
    queue.submit(commands);

    let unpadded = W * 4;
    let align = wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    let padded = unpadded.div_ceil(align) * align;
    let readback = device.create_buffer(&wgpu::BufferDescriptor {
        label: None,
        size: (padded * H) as u64,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
    encoder.copy_texture_to_buffer(
        wgpu::TexelCopyTextureInfo {
            texture: &target,
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
    queue.submit(Some(encoder.finish()));
    let slice = readback.slice(..);
    slice.map_async(wgpu::MapMode::Read, |_| {});
    device.poll(wgpu::PollType::wait_indefinitely()).unwrap();
    let mapped = slice.get_mapped_range().unwrap();
    let mut ppm = format!("P6\n{W} {H}\n255\n").into_bytes();
    for row in 0..H as usize {
        let s = row * padded as usize;
        for x in 0..W as usize {
            let i = s + x * 4;
            ppm.extend_from_slice(&mapped[i..i + 3]);
        }
    }
    std::fs::write(out, ppm).unwrap();
}
