//! Cross-backend parity for the OpenGL renderer. Each scene - fills,
//! gradients, strokes, shadows, every image filter, filter chains, layers
//! with opacity/filters/masks/blend modes, path clipping, scissors,
//! composite operations, image uploads in every pixel format, mipmaps,
//! repeating patterns and text - is drawn with both backends and the GL
//! frame must match the WGPU one. The WGPU suite pins most of these scenes
//! against browser references, so parity carries those guarantees over to GL
//! on desktop GL, GLES 3 and GLES 2 (see `common_gl` for selecting the GLES
//! 2 flavor). The GL frames are also required to stay identical across
//! frames of one canvas, which exercises the atlas, transient-image and
//! framebuffer caches. GL errors fail the test (`common_gl` captures them).
//!
//! Set `PARITY_OUT` to a directory to get PNGs of every mismatching frame.
#![cfg(all(any(windows, unix), not(target_vendor = "apple"), not(target_arch = "wasm32")))]

use femtovg::{
    imgref::Img, rgb::RGBA8, BlendMode, Canvas, Color, CompositeOperation, FillRule, ImageFilter, ImageFlags, ImageId,
    LayerEffects, LineCap, LineJoin, MaskKind, MorphologyOperator, Paint, Path, PixelFormat, RenderTarget, Renderer,
    Transform2D, TurbulenceKind,
};

#[cfg(feature = "wgpu")]
mod common;
mod common_gl;

const W: u32 = 64;
const H: u32 = 64;

/// An asymmetric source: quadrants red, green, blue and a half-transparent
/// olive, plus a white bar near the top-left, so flips and shifts show.
fn source_pixels() -> Vec<RGBA8> {
    let mut v = vec![RGBA8::new(0, 0, 0, 0); (W * H) as usize];
    for y in 0..H {
        for x in 0..W {
            let c = match (x < W / 2, y < H / 2) {
                (true, true) => RGBA8::new(255, 0, 0, 255),
                (false, true) => RGBA8::new(0, 255, 0, 255),
                (true, false) => RGBA8::new(0, 0, 255, 255),
                (false, false) => RGBA8::new(128, 128, 0, 128),
            };
            v[(y * W + x) as usize] = c;
        }
    }
    for y in 4..8 {
        for x in 4..28 {
            v[(y * W + x) as usize] = RGBA8::new(255, 255, 255, 255);
        }
    }
    v
}

fn upload<T: Renderer>(c: &mut Canvas<T>) -> ImageId {
    let px = source_pixels();
    c.create_image(Img::new(px.as_slice(), W as usize, H as usize), ImageFlags::empty())
        .unwrap()
}

fn target<T: Renderer>(c: &mut Canvas<T>) -> ImageId {
    c.create_image_empty(
        W as usize,
        H as usize,
        PixelFormat::Rgba8,
        ImageFlags::FLIP_Y | ImageFlags::PREMULTIPLIED,
    )
    .unwrap()
}

fn draw_img<T: Renderer>(c: &mut Canvas<T>, img: ImageId) {
    let mut p = Path::new();
    p.rect(0.0, 0.0, W as f32, H as f32);
    c.fill_path(&p, &Paint::image(img, 0.0, 0.0, W as f32, H as f32, 0.0, 1.0));
}

fn filt<T: Renderer>(c: &mut Canvas<T>, f: ImageFilter) {
    let s = upload(c);
    let t = target(c);
    c.filter_image(t, f, s);
    draw_img(c, t);
}

fn chain<T: Renderer>(c: &mut Canvas<T>, fs: &[ImageFilter]) {
    let s = upload(c);
    let t = target(c);
    c.filter_image_chain(t, fs, s).expect("chain");
    draw_img(c, t);
}

fn shapes<T: Renderer>(c: &mut Canvas<T>) {
    let mut p = Path::new();
    p.rect(6.0, 6.0, 30.0, 14.0);
    c.fill_path(&p, &Paint::color(Color::rgb(220, 30, 30)));
    let mut p = Path::new();
    p.circle(44.0, 44.0, 14.0);
    c.fill_path(&p, &Paint::color(Color::rgba(30, 30, 220, 200)));
}

const NAMES: &[&str] = &[
    "fill_aa_circle",
    "linear_gradient",
    "radial_gradient",
    "conic_gradient",
    "two_point_radial",
    "dashed_stroke",
    "evenodd_star",
    "shadow_blur",
    "shadow_offset_noblur",
    "upload_draw",
    "filter_blur3",
    "filter_blur_aniso",
    "filter_dilate",
    "filter_erode",
    "filter_offset",
    "filter_turbulence",
    "filter_fractal_stitch",
    "filter_lin2srgb",
    "filter_srgb2lin",
    "filter_sepia",
    "filter_lum2alpha",
    "filter_blend_multiply",
    "filter_blend_hue",
    "chain_blur_sepia",
    "chain_blur20",
    "chain_dilate30",
    "chain_offset_blur",
    "layer_opacity",
    "layer_blur",
    "layer_mask_lum",
    "layer_mask_alpha",
    "layer_blend_multiply",
    "clip_path_evenodd",
    "image_rotated",
    "rounded_scissor",
    "composite_dest_out",
    "composite_xor",
    "image_tint",
    "render_to_image_then_draw",
    "gradient_transform",
    "upload_rgb_odd",
    "upload_gray_odd",
    "update_subrect",
    "mipmap_minify",
    "repeat_pattern",
    "text",
    "text_scaled_rotated",
];

fn scene<T: Renderer>(i: usize, c: &mut Canvas<T>) {
    match NAMES[i] {
        "fill_aa_circle" => {
            let mut p = Path::new();
            p.circle(31.3, 30.7, 20.2);
            c.fill_path(&p, &Paint::color(Color::rgb(10, 120, 200)));
        }
        "linear_gradient" => {
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(
                &p,
                &Paint::linear_gradient(0.0, 0.0, 64.0, 40.0, Color::rgb(255, 0, 0), Color::rgb(0, 0, 255)),
            );
        }
        "radial_gradient" => {
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(
                &p,
                &Paint::radial_gradient(20.0, 24.0, 4.0, 30.0, Color::rgb(255, 255, 0), Color::rgb(0, 80, 0)),
            );
        }
        "conic_gradient" => {
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(
                &p,
                &Paint::conic_gradient_stops(
                    30.0,
                    26.0,
                    [
                        (0.0, Color::rgb(255, 0, 0)),
                        (0.5, Color::rgb(0, 255, 0)),
                        (1.0, Color::rgb(0, 0, 255)),
                    ],
                ),
            );
        }
        "two_point_radial" => {
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(
                &p,
                &Paint::two_point_radial_gradient(
                    20.0,
                    20.0,
                    2.0,
                    36.0,
                    40.0,
                    26.0,
                    Color::rgb(255, 128, 0),
                    Color::rgb(0, 0, 128),
                ),
            );
        }
        "dashed_stroke" => {
            let mut p = Path::new();
            p.move_to(6.0, 10.0);
            p.line_to(58.0, 20.0);
            p.line_to(20.0, 56.0);
            let paint = Paint::color(Color::rgb(0, 0, 0))
                .with_line_width(4.0)
                .with_line_cap(LineCap::Round)
                .with_line_join(LineJoin::Round)
                .with_line_dash(&[8.0, 5.0]);
            c.stroke_path(&p, &paint);
        }
        "evenodd_star" => {
            let mut p = Path::new();
            for k in 0..5 {
                let a = std::f32::consts::TAU * (k as f32 * 2.0) / 5.0 - std::f32::consts::FRAC_PI_2;
                let (x, y) = (32.0 + 28.0 * a.cos(), 34.0 + 28.0 * a.sin());
                if k == 0 {
                    p.move_to(x, y)
                } else {
                    p.line_to(x, y)
                }
            }
            p.close();
            c.fill_path(
                &p,
                &Paint::color(Color::rgb(120, 0, 160)).with_fill_rule(FillRule::EvenOdd),
            );
        }
        "shadow_blur" => {
            c.set_shadow_color(Color::rgba(0, 0, 0, 200));
            c.set_shadow_blur(6.0);
            c.set_shadow_offset(5.0, 8.0);
            let mut p = Path::new();
            p.rect(10.0, 6.0, 30.0, 18.0);
            c.fill_path(&p, &Paint::color(Color::rgb(250, 160, 0)));
        }
        "shadow_offset_noblur" => {
            c.set_shadow_color(Color::rgba(0, 0, 255, 255));
            c.set_shadow_blur(0.0);
            c.set_shadow_offset(6.0, 12.0);
            let mut p = Path::new();
            p.rect(10.0, 6.0, 30.0, 10.0);
            c.fill_path(&p, &Paint::color(Color::rgb(250, 0, 0)));
        }
        "upload_draw" => {
            let s = upload(c);
            draw_img(c, s);
        }
        "filter_blur3" => filt(c, ImageFilter::gaussian_blur(3.0)),
        "filter_blur_aniso" => filt(
            c,
            ImageFilter::GaussianBlur {
                sigma_x: 0.0,
                sigma_y: 5.0,
            },
        ),
        "filter_dilate" => filt(
            c,
            ImageFilter::Morphology {
                radius_x: 3.0,
                radius_y: 1.0,
                operator: MorphologyOperator::Dilate,
            },
        ),
        "filter_erode" => filt(
            c,
            ImageFilter::Morphology {
                radius_x: 1.0,
                radius_y: 3.0,
                operator: MorphologyOperator::Erode,
            },
        ),
        "filter_offset" => filt(c, ImageFilter::Offset { dx: 7.0, dy: 11.0 }),
        "filter_turbulence" => filt(
            c,
            ImageFilter::Turbulence {
                base_frequency: [0.05, 0.08],
                num_octaves: 3,
                seed: 7,
                stitch_tiles: false,
                kind: TurbulenceKind::Turbulence,
                transform: Transform2D::identity(),
            },
        ),
        "filter_fractal_stitch" => filt(
            c,
            ImageFilter::Turbulence {
                base_frequency: [0.04, 0.04],
                num_octaves: 2,
                seed: 3,
                stitch_tiles: true,
                kind: TurbulenceKind::FractalNoise,
                transform: Transform2D::identity(),
            },
        ),
        "filter_lin2srgb" => filt(c, ImageFilter::LinearRgbToSrgb),
        "filter_srgb2lin" => filt(c, ImageFilter::SrgbToLinearRgb),
        "filter_sepia" => filt(c, ImageFilter::sepia(0.8)),
        "filter_lum2alpha" => filt(c, ImageFilter::luminance_to_alpha()),
        "filter_blend_multiply" | "filter_blend_hue" => {
            let mode = if NAMES[i] == "filter_blend_hue" {
                BlendMode::Hue
            } else {
                BlendMode::Multiply
            };
            let backdrop = c
                .create_image_empty(
                    W as usize,
                    H as usize,
                    PixelFormat::Rgba8,
                    ImageFlags::FLIP_Y | ImageFlags::PREMULTIPLIED,
                )
                .unwrap();
            c.set_render_target(RenderTarget::Image(backdrop));
            c.clear_rect(0, 0, W, H, Color::rgba(0, 0, 0, 0));
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(
                &p,
                &Paint::linear_gradient(
                    0.0,
                    0.0,
                    64.0,
                    0.0,
                    Color::rgb(255, 255, 0),
                    Color::rgba(0, 200, 255, 160),
                ),
            );
            c.set_render_target(RenderTarget::Screen);
            chain(
                c,
                &[ImageFilter::Blend {
                    mode,
                    backdrop,
                    x: 8.0,
                    y: 4.0,
                    width: 48.0,
                    height: 40.0,
                }],
            );
        }
        "chain_blur_sepia" => chain(c, &[ImageFilter::gaussian_blur(2.0), ImageFilter::sepia(1.0)]),
        "chain_blur20" => chain(c, &[ImageFilter::gaussian_blur(20.0)]),
        "chain_dilate30" => chain(
            c,
            &[ImageFilter::Morphology {
                radius_x: 30.0,
                radius_y: 2.0,
                operator: MorphologyOperator::Dilate,
            }],
        ),
        "chain_offset_blur" => chain(
            c,
            &[
                ImageFilter::Offset { dx: -5.0, dy: 9.0 },
                ImageFilter::gaussian_blur(1.5),
            ],
        ),
        "layer_opacity" => {
            assert!(c.begin_layer(&LayerEffects::new().with_opacity(0.5)));
            shapes(c);
            c.end_layer();
        }
        "layer_blur" => {
            assert!(c.begin_layer(&LayerEffects::new().with_filters(&[ImageFilter::gaussian_blur(3.0)])));
            shapes(c);
            c.end_layer();
        }
        "layer_mask_lum" | "layer_mask_alpha" => {
            let kind = if NAMES[i] == "layer_mask_lum" {
                MaskKind::Luminance
            } else {
                MaskKind::Alpha
            };
            let m = upload(c);
            assert!(c.begin_layer(&LayerEffects::new().with_mask(m, kind, 4.0, 2.0, 56.0, 50.0)));
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(&p, &Paint::color(Color::rgb(200, 0, 120)));
            c.end_layer();
        }
        "layer_blend_multiply" => {
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 32.0);
            c.fill_path(&p, &Paint::color(Color::rgb(0, 200, 255)));
            assert!(c.begin_layer(&LayerEffects::new().with_blend(BlendMode::Multiply)));
            shapes(c);
            c.end_layer();
        }
        "clip_path_evenodd" => {
            let mut clip = Path::new();
            clip.circle(32.0, 32.0, 26.0);
            clip.circle(40.0, 24.0, 10.0);
            c.clip_path(&clip, FillRule::EvenOdd);
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 40.0);
            c.fill_path(&p, &Paint::color(Color::rgb(0, 150, 60)));
        }
        "image_rotated" => {
            let s = upload(c);
            c.translate(32.0, 32.0);
            c.rotate(0.4);
            c.translate(-32.0, -32.0);
            draw_img(c, s);
        }
        "rounded_scissor" => {
            c.rounded_scissor(8.0, 10.0, 44.0, 30.0, 9.0);
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(&p, &Paint::color(Color::rgb(90, 0, 200)));
        }
        "composite_dest_out" | "composite_xor" => {
            shapes(c);
            c.global_composite_operation(if NAMES[i] == "composite_xor" {
                CompositeOperation::Xor
            } else {
                CompositeOperation::DestinationOut
            });
            let mut p = Path::new();
            p.circle(28.0, 20.0, 12.0);
            c.fill_path(&p, &Paint::color(Color::rgba(0, 0, 0, 180)));
        }
        "image_tint" => {
            let s = upload(c);
            let mut p = Path::new();
            p.rect(0.0, 0.0, W as f32, H as f32);
            c.fill_path(
                &p,
                &Paint::image_tint(s, 0.0, 0.0, W as f32, H as f32, 0.0, Color::rgba(255, 128, 0, 200)),
            );
        }
        "render_to_image_then_draw" => {
            let t = c
                .create_image_empty(
                    W as usize,
                    H as usize,
                    PixelFormat::Rgba8,
                    ImageFlags::FLIP_Y | ImageFlags::PREMULTIPLIED,
                )
                .unwrap();
            c.set_render_target(RenderTarget::Image(t));
            c.clear_rect(0, 0, W, H, Color::rgba(0, 0, 0, 0));
            shapes(c);
            c.set_render_target(RenderTarget::Screen);
            draw_img(c, t);
        }
        "gradient_transform" => {
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            let mut t = Transform2D::identity();
            t.rotate(0.6);
            c.fill_path(
                &p,
                &Paint::linear_gradient(0.0, 0.0, 40.0, 0.0, Color::rgb(255, 0, 0), Color::rgb(0, 0, 255))
                    .with_gradient_transform(t),
            );
        }
        "upload_rgb_odd" => {
            let (w, h) = (13usize, 9usize);
            let px: Vec<femtovg::rgb::RGB8> = (0..w * h)
                .map(|i| femtovg::rgb::RGB8::new((i * 37 % 256) as u8, (i * 91 % 256) as u8, (i % w * 19) as u8))
                .collect();
            let img = c
                .create_image(Img::new(px.as_slice(), w, h), ImageFlags::NEAREST)
                .unwrap();
            let mut p = Path::new();
            p.rect(0.0, 0.0, 52.0, 36.0);
            c.fill_path(&p, &Paint::image(img, 0.0, 0.0, 52.0, 36.0, 0.0, 1.0));
        }
        "upload_gray_odd" => {
            let (w, h) = (11usize, 7usize);
            let px: Vec<femtovg::rgb::alt::Gray<u8>> = (0..w * h)
                .map(|i| femtovg::rgb::alt::Gray((i * 53 % 256) as u8))
                .collect();
            let img = c
                .create_image(Img::new(px.as_slice(), w, h), ImageFlags::NEAREST)
                .unwrap();
            let mut p = Path::new();
            p.rect(0.0, 0.0, 44.0, 28.0);
            c.fill_path(&p, &Paint::image(img, 0.0, 0.0, 44.0, 28.0, 0.0, 1.0));
        }
        "update_subrect" => {
            let s = upload(c);
            let patch = vec![RGBA8::new(255, 0, 255, 255); 10 * 6];
            c.update_image(s, Img::new(patch.as_slice(), 10, 6), 40, 3).unwrap();
            draw_img(c, s);
        }
        "mipmap_minify" => {
            let px: Vec<RGBA8> = (0..256 * 256)
                .map(|i| {
                    if ((i % 256) / 4 + (i / 256) / 4) % 2 == 0 {
                        RGBA8::new(255, 255, 255, 255)
                    } else {
                        RGBA8::new(0, 0, 0, 255)
                    }
                })
                .collect();
            let img = c
                .create_image(Img::new(px.as_slice(), 256, 256), ImageFlags::GENERATE_MIPMAPS)
                .unwrap();
            let mut p = Path::new();
            p.rect(0.0, 0.0, 32.0, 32.0);
            c.fill_path(&p, &Paint::image(img, 0.0, 0.0, 32.0, 32.0, 0.0, 1.0));
        }
        "repeat_pattern" => {
            let px: Vec<RGBA8> = (0..8 * 8)
                .map(|i| {
                    if (i % 8 < 4) ^ (i / 8 < 3) {
                        RGBA8::new(200, 20, 20, 255)
                    } else {
                        RGBA8::new(20, 20, 200, 255)
                    }
                })
                .collect();
            let img = c
                .create_image(
                    Img::new(px.as_slice(), 8, 8),
                    ImageFlags::REPEAT_X | ImageFlags::REPEAT_Y | ImageFlags::NEAREST,
                )
                .unwrap();
            let mut p = Path::new();
            p.rect(0.0, 0.0, 64.0, 64.0);
            c.fill_path(&p, &Paint::image(img, 3.0, 5.0, 8.0, 8.0, 0.0, 1.0));
        }
        "text" | "text_scaled_rotated" => {
            let font = c.add_font("examples/assets/RobotoFlex-VariableFont.ttf").expect("font");
            if NAMES[i] == "text_scaled_rotated" {
                c.translate(10.0, 20.0);
                c.rotate(0.3);
                c.scale(1.7, 1.7);
            }
            let paint = Paint::color(Color::rgb(0, 0, 0))
                .with_font(&[font])
                .with_font_size(18.0);
            c.fill_text(4.0, 30.0, "Fg@j", &paint).unwrap();
            let paint = Paint::color(Color::rgb(200, 0, 0))
                .with_font(&[font])
                .with_font_size(11.0);
            c.fill_text(2.0, 56.0, "yqZ8", &paint).unwrap();
        }
        other => panic!("unknown scene {other}"),
    }
}

fn save_png(name: &str, px: &[u8]) {
    let dir = std::env::var("PARITY_OUT").unwrap_or_default();
    if dir.is_empty() {
        return;
    }
    let img = image::RgbaImage::from_raw(W, H, px.to_vec()).unwrap();
    img.save(format!("{dir}/{name}.png")).unwrap();
}

/// Counts the pixels whose channels differ by more than `tolerance`.
fn differing_pixels(a: &[u8], b: &[u8], tolerance: i32) -> Vec<usize> {
    (0..(W * H) as usize)
        .filter(|p| (0..4).any(|k| (a[p * 4 + k] as i32 - b[p * 4 + k] as i32).abs() > tolerance))
        .collect()
}

fn describe(name: &str, p: usize, a: &[u8], b: &[u8], count: usize) -> String {
    format!(
        "{name}: {count} pixels differ, first at ({}, {}): {:?} vs {:?}",
        p % W as usize,
        p / W as usize,
        &a[p * 4..p * 4 + 4],
        &b[p * 4..p * 4 + 4]
    )
}

/// Different rasterizers may round a few antialiased edge pixels apart, so a
/// scene matches when at most `EDGE_PIXELS` pixels differ by more than
/// `TOLERANCE` per channel. Mesa's llvmpipe and lavapipe agree to within 1.
#[cfg(feature = "wgpu")]
const TOLERANCE: i32 = 8;
#[cfg(feature = "wgpu")]
const EDGE_PIXELS: usize = 4;

#[cfg(feature = "wgpu")]
#[test]
fn gl_matches_wgpu() {
    let Some((device, queue)) = common::headless_device() else {
        return;
    };
    let mut failures = vec![];
    common_gl::for_each_flavor(W, H, |gl| {
        let flavor = gl.flavor;
        for (i, name) in NAMES.iter().enumerate() {
            let wgpu = common::render_rgba(&device, &queue, W, H, Color::white(), |c| scene(i, c));
            let gl_frame = gl.render_rgba(Color::white(), |c| scene(i, c));
            let diff = differing_pixels(&wgpu, &gl_frame, TOLERANCE);
            if diff.len() > EDGE_PIXELS {
                failures.push(describe(
                    &format!("{flavor:?} {name} (wgpu vs gl)"),
                    diff[0],
                    &wgpu,
                    &gl_frame,
                    diff.len(),
                ));
                save_png(&format!("{flavor:?}_{name}_wgpu"), &wgpu);
                save_png(&format!("{flavor:?}_{name}_gl"), &gl_frame);
            }
        }
    });
    assert!(
        failures.is_empty(),
        "GL frames diverge from WGPU:\n{}",
        failures.join("\n")
    );
}

#[test]
fn gl_frames_repeat_exactly() {
    let mut failures = vec![];
    common_gl::for_each_flavor(W, H, |gl| {
        let flavor = gl.flavor;
        for (i, name) in NAMES.iter().enumerate() {
            let mut canvas = Canvas::new(gl.renderer()).expect("canvas");
            canvas.set_size(W, H, 1.0);
            let mut frames = vec![];
            for _ in 0..3 {
                canvas.save();
                canvas.clear_rect(0, 0, W, H, Color::white());
                scene(i, &mut canvas);
                canvas.restore();
                canvas.flush();
                gl.assert_no_gl_errors();
                frames.push(gl.read_rgba());
            }
            for (k, frame) in frames.iter().enumerate().skip(1) {
                let diff = differing_pixels(&frames[0], frame, 0);
                if !diff.is_empty() {
                    failures.push(describe(
                        &format!("{flavor:?} {name} (frame 0 vs frame {k})"),
                        diff[0],
                        &frames[0],
                        frame,
                        diff.len(),
                    ));
                    save_png(&format!("{flavor:?}_{name}_frame{k}"), frame);
                }
            }
        }
    });
    assert!(
        failures.is_empty(),
        "GL frames change between frames of one canvas:\n{}",
        failures.join("\n")
    );
}
