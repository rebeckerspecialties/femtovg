//! Offscreen single-SVG-logo renderer for conformance cross-checks: maps usvg
//! paths and gradients onto femtovg paints and renders one logo centered
//! under a pivot zoom. Usage: `_logos <scale> <out.ppm> <logo.svg> [dark]`.
#![cfg(feature = "wgpu")]

use femtovg::{renderer::WGPURenderer, Canvas, Color, FillRule, Paint, Path, Transform2D};

const W: u32 = 460;
const H: u32 = 260;

fn ts_to_t2d(t: usvg::Transform) -> Transform2D {
    Transform2D([t.sx, t.ky, t.kx, t.sy, t.tx, t.ty])
}

fn stop_list(stops: &[usvg::Stop]) -> Vec<(f32, Color)> {
    stops
        .iter()
        .map(|s| {
            let c = s.color();
            let mut col = Color::rgb(c.red, c.green, c.blue);
            col.set_alphaf(s.opacity().get());
            (s.offset().get(), col)
        })
        .collect()
}

fn to_paint(p: &usvg::Paint) -> Option<Paint> {
    let mut paint = match p {
        usvg::Paint::Color(c) => Paint::color(Color::rgb(c.red, c.green, c.blue)),
        usvg::Paint::LinearGradient(g) => {
            Paint::linear_gradient_stops(g.x1(), g.y1(), g.x2(), g.y2(), stop_list(g.stops()))
                .with_gradient_transform(ts_to_t2d(g.transform()))
        }
        usvg::Paint::RadialGradient(g) => Paint::two_point_radial_gradient_stops(
            g.fx(),
            g.fy(),
            0.0,
            g.cx(),
            g.cy(),
            g.r().get(),
            stop_list(g.stops()),
        )
        .with_gradient_transform(ts_to_t2d(g.transform())),
        usvg::Paint::Pattern(_) => return None,
    };
    paint.set_anti_alias(true);
    Some(paint)
}

fn draw_nodes(canvas: &mut Canvas<WGPURenderer>, children: &[usvg::Node]) {
    use usvg::tiny_skia_path::PathSegment;
    for node in children {
        match node {
            usvg::Node::Group(group) => draw_nodes(canvas, group.children()),
            usvg::Node::Path(svg_path) => {
                let mut path = Path::new();
                for seg in svg_path.data().segments() {
                    match seg {
                        PathSegment::MoveTo(p) => path.move_to(p.x, p.y),
                        PathSegment::LineTo(p) => path.line_to(p.x, p.y),
                        PathSegment::CubicTo(a, b, p) => path.bezier_to(a.x, a.y, b.x, b.y, p.x, p.y),
                        PathSegment::QuadTo(a, p) => path.quad_to(a.x, a.y, p.x, p.y),
                        PathSegment::Close => path.close(),
                    }
                }
                canvas.save();
                canvas.set_transform(&ts_to_t2d(svg_path.abs_transform()));
                if let Some(fill) = svg_path.fill() {
                    if let Some(mut paint) = to_paint(fill.paint()) {
                        paint.set_fill_rule(match fill.rule() {
                            usvg::FillRule::NonZero => FillRule::NonZero,
                            usvg::FillRule::EvenOdd => FillRule::EvenOdd,
                        });
                        canvas.fill_path(&path, &paint);
                    }
                }
                if let Some(stroke) = svg_path.stroke() {
                    if let Some(mut paint) = to_paint(stroke.paint()) {
                        paint.set_line_width(stroke.width().get());
                        canvas.stroke_path(&path, &paint);
                    }
                }
                canvas.restore();
            }
            _ => {}
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let scale: f32 = args[1].parse().expect("scale");
    let out = &args[2];
    let svg_path = &args[3];
    let dark = args.get(4).map(String::as_str) == Some("dark");

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

    let tree = usvg::Tree::from_data(&std::fs::read(svg_path).unwrap(), &usvg::Options::default()).unwrap();

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

    let bg = if dark { Color::rgb(32, 34, 37) } else { Color::white() };
    canvas.clear_rect(0, 0, W, H, bg);
    canvas.save();
    let (px, py) = std::env::var("PIVOT")
        .ok()
        .and_then(|s| s.split_once(',').map(|(a, b)| (a.parse().unwrap(), b.parse().unwrap())))
        .unwrap_or((230.0f32, 130.0f32));
    canvas.translate(px, py);
    canvas.scale(scale, scale);
    canvas.translate(-px, -py);

    let size = tree.size();
    let fit = 200.0 / size.width().max(size.height());
    canvas.translate(130.0, 30.0);
    canvas.scale(fit, fit);
    draw_nodes(&mut canvas, tree.root().children());

    canvas.restore();

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
        let src = row * padded as usize;
        for px in 0..W as usize {
            let i = src + px * 4;
            ppm.extend_from_slice(&mapped[i..i + 3]);
        }
    }
    std::fs::write(out, ppm).unwrap();
}
