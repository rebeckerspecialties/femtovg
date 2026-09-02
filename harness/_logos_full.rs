//! Offscreen single-SVG-logo renderer for conformance cross-checks: maps usvg
//! paths and gradients onto femtovg paints and renders one logo centered
//! under a pivot zoom. Usage: `_logos <scale> <out.ppm> <logo.svg> [dark]`.
#![cfg(feature = "wgpu")]

use femtovg::{
    renderer::WGPURenderer, Canvas, Color, FillRule, ImageFilter, LayerEffects, MaskKind, Paint, Path, RenderTarget,
    Transform2D,
};

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
    if std::env::var("GRAD_DUMP").is_ok() {
        match p {
            usvg::Paint::LinearGradient(g) => eprintln!("linear {} stops x1y1x2y2=({},{})-({},{}) transform={:?}", g.stops().len(), g.x1(), g.y1(), g.x2(), g.y2(), g.transform()),
            usvg::Paint::RadialGradient(g) => eprintln!("radial {} stops c=({},{}) f=({},{}) r={} transform={:?}", g.stops().len(), g.cx(), g.cy(), g.fx(), g.fy(), g.r().get(), g.transform()),
            _ => {}
        }
    }
    if std::env::var("FORCE_SOLID").is_ok() && !matches!(p, usvg::Paint::Color(_)) {
        return Some(Paint::color(Color::rgb(200, 0, 200)));
    }
    Some(paint)
}

/// Renders `group`'s mask content into a canvas-sized image and returns it
/// with the mask kind; the caller hands it to LayerEffects::with_mask.
type MaskMap = std::collections::HashMap<usize, (femtovg::ImageId, MaskKind)>;

fn capture_mask(
    canvas: &mut Canvas<WGPURenderer>,
    mask: &usvg::Mask,
    group_transform: usvg::Transform,
    canvas_w: usize,
    canvas_h: usize,
    scale: f32,
    masks: &MaskMap,
) -> Option<(femtovg::ImageId, MaskKind)> {
    let image = canvas
        .create_image_empty(
            canvas_w,
            canvas_h,
            femtovg::PixelFormat::Rgba8,
            femtovg::ImageFlags::PREMULTIPLIED | femtovg::ImageFlags::FLIP_Y,
        )
        .ok()?;
    canvas.save();
    canvas.set_render_target(RenderTarget::Image(image));
    canvas.clear_rect(0, 0, canvas_w as u32, canvas_h as u32, Color::rgbaf(0.0, 0.0, 0.0, 0.0));
    // Mask content lives in the referencing group's user space.
    canvas.set_transform(&ts_to_t2d(group_transform));
    draw_nodes(canvas, mask.root().children(), scale, masks);
    canvas.set_render_target(RenderTarget::Screen);
    canvas.restore();
    let kind = match mask.kind() {
        usvg::MaskType::Luminance => MaskKind::Luminance,
        usvg::MaskType::Alpha => MaskKind::Alpha,
    };
    Some((image, kind))
}

/// All mask images are captured before any drawing so no capture has to
/// restore into a live layer.
fn precapture_masks(
    canvas: &mut Canvas<WGPURenderer>,
    children: &[usvg::Node],
    canvas_w: usize,
    canvas_h: usize,
    scale: f32,
    out: &mut MaskMap,
) {
    for node in children {
        if let usvg::Node::Group(group) = node {
            if let Some(mask) = group.mask() {
                precapture_masks(canvas, mask.root().children(), canvas_w, canvas_h, scale, out);
                if let Some(captured) =
                    capture_mask(canvas, mask, group.abs_transform(), canvas_w, canvas_h, scale, out)
                {
                    out.insert(&**group as *const usvg::Group as usize, captured);
                }
            }
            precapture_masks(canvas, group.children(), canvas_w, canvas_h, scale, out);
        }
    }
}

fn group_effects(
    canvas: &mut Canvas<WGPURenderer>,
    group: &usvg::Group,
    canvas_w: usize,
    canvas_h: usize,
    scale: f32,
    masks: &MaskMap,
) -> Option<LayerEffects> {
    let opacity = if std::env::var("NO_OPACITY").is_ok() { 1.0 } else { group.opacity().get() };
    let mut blurs: Vec<ImageFilter> = Vec::new();
    for f in group.filters() {
        for prim in f.primitives() {
            if let usvg::filter::Kind::GaussianBlur(b) = prim.kind() {
                // usvg std-dev is in user units; layer filters run in device
                // pixels, so scale by the composed canvas scale.
                let sigma = b.std_dev_x().get().max(b.std_dev_y().get()) * scale;
                if sigma > 0.0 {
                    blurs.push(ImageFilter::GaussianBlur { sigma });
                }
            }
        }
    }
    let _ = canvas;
    let mask = masks.get(&(group as *const usvg::Group as usize)).copied();
    if opacity >= 1.0 && blurs.is_empty() && mask.is_none() {
        return None;
    }
    let mut fx = LayerEffects::new().with_opacity(opacity).with_filters(&blurs);
    if let Some((image, kind)) = mask {
        fx = fx.with_mask(image, kind, 0.0, 0.0, canvas_w as f32, canvas_h as f32);
    }
    Some(fx)
}

#[allow(dead_code)]
fn dump(children: &[usvg::Node], depth: usize) {
    for node in children {
        match node {
            usvg::Node::Group(g) => {
                eprintln!("{:indent$}Group mask={:?} clip={:?} blend={:?} filters={} opacity={} transform={:?}", "", g.mask().map(|m| format!("{:?} rect={:?}", m.kind(), m.rect())), g.clip_path().map(|c| format!("transform={:?} children={}", c.transform(), c.root().children().len())), g.blend_mode(), g.filters().len(), g.opacity().get(), g.transform(), indent = depth * 2);
                dump(g.children(), depth + 1);
            }
            usvg::Node::Path(p) => {
                let b = p.abs_bounding_box();
                eprintln!("{:indent$}Path bbox=({:.0},{:.0} {:.0}x{:.0}) fill={} stroke={}", "", b.x(), b.y(), b.width(), b.height(), p.fill().is_some(), p.stroke().is_some(), indent = depth * 2);
            }
            usvg::Node::Text(_) => eprintln!("{:indent$}Text(unconverted)", "", indent = depth * 2),
            other => eprintln!("{:indent$}{:?}", "", format!("{other:?}").chars().take(60).collect::<String>(), indent = depth * 2),
        }
    }
}

static PATH_COUNTER: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);

fn draw_nodes(canvas: &mut Canvas<WGPURenderer>, children: &[usvg::Node], scale: f32, masks: &MaskMap) {
    use usvg::tiny_skia_path::PathSegment;
    for node in children {
        match node {
            usvg::Node::Group(group) => {
                if std::env::var("NO_BLEND").is_ok() && group.blend_mode() != usvg::BlendMode::Normal {
                    continue;
                }
                let clipped = group.clip_path().is_some() && std::env::var("NO_CLIP").is_err();
                if let Some(clip) = group.clip_path().filter(|_| std::env::var("NO_CLIP").is_err()) {
                    canvas.save();
                    let mut combined = Path::new();
                    let mut rule = FillRule::NonZero;
                    // Clip content may be nested in groups (usvg wraps a
                    // <use> inside <clipPath> in a Group); walk the whole
                    // subtree and bake every path's absolute transform.
                    fn collect_clip(nodes: &[usvg::Node], base: usvg::Transform, combined: &mut Path, rule: &mut FillRule) {
                        use usvg::tiny_skia_path::PathSegment;
                        for node in nodes {
                            match node {
                                usvg::Node::Group(g) => collect_clip(g.children(), base, combined, rule),
                                usvg::Node::Path(p) => {
                                    if let Some(f) = p.fill() {
                                        if matches!(f.rule(), usvg::FillRule::EvenOdd) {
                                            *rule = FillRule::EvenOdd;
                                        }
                                    }
                                    let ct = base.pre_concat(p.abs_transform());
                                    let map = |x: f32, y: f32| (ct.sx * x + ct.kx * y + ct.tx, ct.ky * x + ct.sy * y + ct.ty);
                                    for seg in p.data().segments() {
                                        match seg {
                                            PathSegment::MoveTo(q) => { let (x, y) = map(q.x, q.y); combined.move_to(x, y); }
                                            PathSegment::LineTo(q) => { let (x, y) = map(q.x, q.y); combined.line_to(x, y); }
                                            PathSegment::QuadTo(a, q) => { let (ax, ay) = map(a.x, a.y); let (x, y) = map(q.x, q.y); combined.quad_to(ax, ay, x, y); }
                                            PathSegment::CubicTo(a, b, q) => { let (ax, ay) = map(a.x, a.y); let (bx, by) = map(b.x, b.y); let (x, y) = map(q.x, q.y); combined.bezier_to(ax, ay, bx, by, x, y); }
                                            PathSegment::Close => combined.close(),
                                        }
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                    collect_clip(clip.root().children(), group.abs_transform().pre_concat(clip.transform()), &mut combined, &mut rule);
                    if std::env::var("CLIP_SHOW").is_ok() {
                        // Debug: paint the clip region instead of clipping with it.
                        let mut show = Paint::color(Color::rgba(200, 0, 200, 90));
                        show.set_fill_rule(rule);
                        canvas.fill_path(&combined, &show);
                    } else {
                        canvas.clip_path(&combined, rule);
                    }
                }
                match group_effects(canvas, group, W as usize, H as usize, scale, masks) {
                    Some(fx) => {
                        canvas.begin_layer(&fx);
                        draw_nodes(canvas, group.children(), scale, masks);
                        canvas.end_layer();
                    }
                    None => draw_nodes(canvas, group.children(), scale, masks),
                }
                if clipped {
                    canvas.restore();
                }
            }
            usvg::Node::Path(svg_path) => {
                if let Ok(range) = std::env::var("PATH_RANGE") {
                    let (lo, hi) = range.split_once(':').unwrap();
                    let (lo, hi): (usize, usize) = (lo.parse().unwrap(), hi.parse().unwrap());
                    let idx = PATH_COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    if idx < lo || idx >= hi {
                        continue;
                    }
                }
                if std::env::var("PATH_DUMP").is_ok() {
                    eprintln!("--- path fill={:?} rule={:?}", svg_path.fill().map(|f| format!("{:?}", f.paint()).chars().take(60).collect::<String>()), svg_path.fill().map(|f| f.rule()));
                    for seg in svg_path.data().segments() {
                        eprintln!("  {:?}", seg);
                    }
                }
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
                        canvas.set_global_alpha(fill.opacity().get());
                        canvas.fill_path(&path, &paint);
                        canvas.set_global_alpha(1.0);
                    }
                }
                if let Some(stroke) = svg_path.stroke() {
                    if let Some(mut paint) = to_paint(stroke.paint()) {
                        paint.set_line_width(stroke.width().get());
                        paint.set_line_cap(match stroke.linecap() {
                            usvg::LineCap::Butt => femtovg::LineCap::Butt,
                            usvg::LineCap::Round => femtovg::LineCap::Round,
                            usvg::LineCap::Square => femtovg::LineCap::Square,
                        });
                        paint.set_line_join(match stroke.linejoin() {
                            usvg::LineJoin::Miter | usvg::LineJoin::MiterClip => femtovg::LineJoin::Miter,
                            usvg::LineJoin::Round => femtovg::LineJoin::Round,
                            usvg::LineJoin::Bevel => femtovg::LineJoin::Bevel,
                        });
                        paint.set_miter_limit(stroke.miterlimit().get());
                        if let Some(dashes) = stroke.dasharray() {
                            paint.set_line_dash(dashes);
                            paint.set_line_dash_offset(stroke.dashoffset());
                        }
                        canvas.set_global_alpha(stroke.opacity().get());
                        canvas.stroke_path(&path, &paint);
                        canvas.set_global_alpha(1.0);
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

    let tree = {
        let mut opt = usvg::Options::default();
        opt.fontdb_mut().load_system_fonts();
        usvg::Tree::from_data(&std::fs::read(svg_path).unwrap(), &opt).unwrap()
    };
    if std::env::var("TREE_DUMP").is_ok() {
        dump(tree.root().children(), 0);
    }

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
    let mut masks = MaskMap::new();
    precapture_masks(&mut canvas, tree.root().children(), W as usize, H as usize, scale * fit, &mut masks);
    draw_nodes(&mut canvas, tree.root().children(), scale * fit, &masks);

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
