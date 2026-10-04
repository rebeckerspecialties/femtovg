//! An `ImgRef` can be a view into a wider buffer (`sub_image`), so its rows
//! are `stride` pixels apart, not `width`. Both backends used to upload such
//! a view as if it were tightly packed, reading each row's tail from the
//! padding and skewing the image diagonally. These tests upload a strided
//! view of every pixel format - through `create_image` and through
//! `update_image` at an offset - and require the drawn result to equal that
//! of a tightly packed copy of the same pixels. They run on WGPU (with the
//! `wgpu` feature) and on every OpenGL flavor a surfaceless EGL context can
//! provide; each skips when its device is missing.
#![cfg(not(target_arch = "wasm32"))]

use femtovg::{
    imgref::{Img, ImgRef},
    rgb::{alt::Gray, RGB8, RGBA8},
    Canvas, Color, ImageFlags, ImageSource, Paint, Path, PixelFormat, Renderer,
};

#[cfg(feature = "wgpu")]
mod common;
#[cfg(all(any(windows, unix), not(target_vendor = "apple")))]
mod common_gl;

const W: u32 = 48;
const H: u32 = 32;

/// The full buffer the views are cut from: every pixel distinct, so a skew
/// of even one pixel per row changes the image.
const FULL_W: usize = 29;
const FULL_H: usize = 17;
/// The view: an odd-sized window away from the buffer's edges.
const VIEW: (usize, usize, usize, usize) = (5, 3, 11, 7);
/// Where `update_image` places the view inside a larger image.
const UPDATE_AT: (usize, usize) = (2, 1);

fn byte(i: usize, k: usize) -> u8 {
    ((i * (37 + 22 * k) + 11 * k) % 251) as u8
}

#[derive(Clone, Copy, Debug)]
enum Format {
    Rgba,
    Rgb,
    Gray,
}

/// The full buffers the views are cut from, and packed copies of the views.
struct Buffers {
    rgba: (Vec<RGBA8>, Vec<RGBA8>),
    rgb: (Vec<RGB8>, Vec<RGB8>),
    gray: (Vec<Gray<u8>>, Vec<Gray<u8>>),
}

fn with_packed<P: Copy>(full: Vec<P>) -> (Vec<P>, Vec<P>) {
    let packed = strided_view(&full).pixels().collect();
    (full, packed)
}

fn strided_view<P>(full: &[P]) -> ImgRef<'_, P> {
    let (x, y, w, h) = VIEW;
    let view = Img::new(full, FULL_W, FULL_H).sub_image(x, y, w, h);
    assert!(view.stride() > view.width(), "the view must actually be strided");
    view
}

fn buffers() -> Buffers {
    let n = FULL_W * FULL_H;
    Buffers {
        rgba: with_packed(
            (0..n)
                .map(|i| RGBA8::new(byte(i, 0), byte(i, 1), byte(i, 2), 255))
                .collect(),
        ),
        rgb: with_packed((0..n).map(|i| RGB8::new(byte(i, 0), byte(i, 1), byte(i, 2))).collect()),
        gray: with_packed((0..n).map(|i| Gray(byte(i, 0))).collect()),
    }
}

/// The view as an `ImageSource`: strided (cut straight out of the full
/// buffer) or packed (the same pixels in a buffer of their own).
fn source(bufs: &Buffers, format: Format, strided: bool) -> ImageSource<'_> {
    let (_, _, w, h) = VIEW;
    fn pick<'a, P>(pair: &'a (Vec<P>, Vec<P>), strided: bool, w: usize, h: usize) -> ImgRef<'a, P> {
        if strided {
            strided_view(&pair.0)
        } else {
            Img::new(pair.1.as_slice(), w, h)
        }
    }
    match format {
        Format::Rgba => pick(&bufs.rgba, strided, w, h).into(),
        Format::Rgb => pick(&bufs.rgb, strided, w, h).into(),
        Format::Gray => pick(&bufs.gray, strided, w, h).into(),
    }
}

fn pixel_format(format: Format) -> PixelFormat {
    match format {
        Format::Rgba => PixelFormat::Rgba8,
        Format::Rgb => PixelFormat::Rgb8,
        Format::Gray => PixelFormat::Gray8,
    }
}

/// Draws the view twice at 2x, nearest-filtered so every texel maps to whole
/// pixels: on the left as uploaded by `create_image`, on the right as written
/// into a larger image by `update_image` at an offset.
fn draw<T: Renderer>(canvas: &mut Canvas<T>, bufs: &Buffers, format: Format, strided: bool) {
    let (_, _, w, h) = VIEW;
    let created = canvas
        .create_image(source(bufs, format, strided), ImageFlags::NEAREST)
        .unwrap();
    let mut p = Path::new();
    p.rect(0.0, 0.0, (2 * w) as f32, (2 * h) as f32);
    canvas.fill_path(
        &p,
        &Paint::image(created, 0.0, 0.0, (2 * w) as f32, (2 * h) as f32, 0.0, 1.0),
    );

    let (big_w, big_h) = (w + 4, h + 3);
    let updated = canvas
        .create_image_empty(big_w, big_h, pixel_format(format), ImageFlags::NEAREST)
        .unwrap();
    canvas
        .update_image(updated, source(bufs, format, strided), UPDATE_AT.0, UPDATE_AT.1)
        .unwrap();
    let left = (2 * w + 2) as f32;
    let mut p = Path::new();
    p.rect(left, 0.0, (2 * big_w) as f32, (2 * big_h) as f32);
    canvas.fill_path(
        &p,
        &Paint::image(updated, left, 0.0, (2 * big_w) as f32, (2 * big_h) as f32, 0.0, 1.0),
    );
}

fn assert_same(backend: &str, format: Format, strided: &[u8], packed: &[u8]) {
    let differing: Vec<_> = (0..(W * H) as usize)
        .filter(|p| strided[p * 4..p * 4 + 4] != packed[p * 4..p * 4 + 4])
        .collect();
    if let Some(&p) = differing.first() {
        panic!(
            "{backend} {format:?}: a strided view uploaded differently from its packed copy in {} pixels; \
             first at ({}, {}): strided {:?} vs packed {:?}",
            differing.len(),
            p % W as usize,
            p / W as usize,
            &strided[p * 4..p * 4 + 4],
            &packed[p * 4..p * 4 + 4],
        );
    }
}

#[cfg(feature = "wgpu")]
#[test]
fn strided_views_upload_like_packed_wgpu() {
    let Some((device, queue)) = common::headless_device() else {
        return;
    };
    let bufs = buffers();
    for format in [Format::Rgba, Format::Rgb, Format::Gray] {
        let render = |strided| {
            common::render_rgba(&device, &queue, W, H, Color::white(), |c| {
                draw(c, &bufs, format, strided)
            })
        };
        assert_same("wgpu", format, &render(true), &render(false));
    }
}

#[cfg(all(any(windows, unix), not(target_vendor = "apple")))]
#[test]
fn strided_views_upload_like_packed_gl() {
    let bufs = buffers();
    common_gl::for_each_flavor(W, H, |gl| {
        for format in [Format::Rgba, Format::Rgb, Format::Gray] {
            let render = |strided| gl.render_rgba(Color::white(), |c| draw(c, &bufs, format, strided));
            assert_same(&format!("{:?}", gl.flavor), format, &render(true), &render(false));
        }
    });
}
