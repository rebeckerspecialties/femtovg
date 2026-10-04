//! The color-matrix filter tests from `color_matrix_wgpu.rs`, run on the
//! OpenGL backend through a surfaceless EGL context (Mesa's llvmpipe works,
//! no window or display server needed). Each test runs once per GL flavor the
//! host can create: desktop GL core and GLES 3 by default, plus GLES 2 when
//! Mesa is told to report it (`MESA_GLES_VERSION_OVERRIDE=2.0`, which is
//! process-wide, so that flavor needs its own run). Skips when no EGL device
//! is available unless `FEMTOVG_REQUIRE_GL` is set.
#![cfg(all(any(windows, unix), not(target_vendor = "apple"), not(target_arch = "wasm32")))]

use femtovg::{
    imgref::Img, rgb::RGBA8, Canvas, Color, ImageFilter, ImageFlags, Paint, Path, PixelFormat, RenderTarget,
};

mod common_gl;
use common_gl::{for_each_flavor, HeadlessGl};

const W: u32 = 32;
const H: u32 = 32;

fn pixel(pixels: &[u8], x: u32, y: u32) -> [u8; 4] {
    let i = ((y * W + x) * 4) as usize;
    [pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]]
}

fn draw_image(canvas: &mut Canvas<femtovg::renderer::OpenGl>, image: femtovg::ImageId) {
    let mut p = Path::new();
    p.rect(0.0, 0.0, W as f32, H as f32);
    canvas.fill_path(&p, &Paint::image(image, 0.0, 0.0, W as f32, H as f32, 0.0, 1.0));
}

/// Fill a source image with `src` (rendered, like the WGPU test, so the
/// render-to-image path feeds the filter), apply `filter` into a target
/// image, draw the target to the output, and return the centre pixel.
fn filtered_center(gl: &HeadlessGl, src: Color, filter: ImageFilter) -> [u8; 4] {
    let pixels = gl.render_rgba(Color::white(), |canvas| {
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
        draw_image(canvas, filtered);
    });
    pixel(&pixels, W / 2, H / 2)
}

fn close(a: u8, b: i32) -> bool {
    (a as i32 - b).abs() <= 3
}

fn rgb_close(px: [u8; 4], rgb: [i32; 3]) -> bool {
    close(px[0], rgb[0]) && close(px[1], rgb[1]) && close(px[2], rgb[2])
}

#[test]
fn color_matrix_filter_properties_gl() {
    for_each_flavor(W, H, |gl| {
        let flavor = gl.flavor;
        let f = |src: Color, filter| filtered_center(gl, src, filter);
        let red = Color::rgb(255, 0, 0);
        let green = Color::rgb(0, 255, 0);
        let blue = Color::rgb(0, 0, 255);

        // 1. grayscale(1) uses Rec.709 luma, not the 1/3 average or Rec.601.
        for (src, luma) in [(red, 54), (green, 182), (blue, 18)] {
            let g = f(src, ImageFilter::grayscale(1.0));
            assert!(
                rgb_close(g, [luma; 3]),
                "{flavor:?}: grayscale({src:?}) luma must be ~{luma}, got {g:?}"
            );
        }

        // 2. Identities.
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
            let out = f(Color::rgb(200, 120, 40), filt);
            assert!(
                rgb_close(out, [200, 120, 40]),
                "{flavor:?}: {name} must be an identity, got {out:?}"
            );
        }

        // 3. invert(1) of red -> cyan.
        let inv = f(red, ImageFilter::invert(1.0));
        assert!(
            rgb_close(inv, [0, 255, 255]),
            "{flavor:?}: invert(red) must be cyan, got {inv:?}"
        );

        // 4. Clamp: brightness(5) saturates to 255 (no overflow/NaN wrap).
        let bright = f(Color::rgb(200, 200, 200), ImageFilter::brightness(5.0));
        assert!(
            bright[..3] == [255, 255, 255],
            "{flavor:?}: brightness(5) must clamp to 255, got {bright:?}"
        );

        // 5. sepia(1) of the primaries, against the browsers' values.
        for (src, want) in [(red, [100, 89, 69]), (blue, [48, 43, 33])] {
            let s = f(src, ImageFilter::sepia(1.0));
            assert!(
                rgb_close(s, want),
                "{flavor:?}: sepia({src:?}) must be ~{want:?}, got {s:?}"
            );
        }

        // 6. hue-rotate periodicity: three 120-degree rotations return near identity.
        let orig = [150u8, 120, 90];
        let mut cur = Color::rgb(orig[0], orig[1], orig[2]);
        for _ in 0..3 {
            let out = f(cur, ImageFilter::hue_rotate(std::f32::consts::TAU / 3.0));
            cur = Color::rgb(out[0], out[1], out[2]);
        }
        let final_rgb = [cur.r, cur.g, cur.b].map(|c| (c * 255.0).round() as i32);
        for (ch, &o) in orig.iter().enumerate() {
            assert!(
                (final_rgb[ch] - o as i32).abs() <= 10,
                "{flavor:?}: 3x hue_rotate(120deg) must return near the original; channel {ch}: {} vs {o}",
                final_rgb[ch]
            );
        }

        // 7. Unpremultiplied application: a half-transparent source keeps its
        //    alpha, and its color is filtered as if opaque (the shader divides
        //    out alpha before the matrix and multiplies it back after).
        let half = f(Color::rgba(255, 0, 0, 128), ImageFilter::grayscale(1.0));
        // Composited over white: 54 * a + 255 * (1 - a), a = 128/255.
        let expect = (54.0_f32 * (128.0 / 255.0) + 255.0 * (127.0 / 255.0)).round() as i32;
        assert!(
            rgb_close(half, [expect; 3]),
            "{flavor:?}: grayscale of half-transparent red over white must be ~{expect}, got {half:?}"
        );
    });
}

/// A mirrored filter pass survives every solid-color test, so filter an
/// asymmetric source uploaded as pixel data: top half red, bottom half blue.
/// Image render targets store their content vertically flipped, so the target
/// is created with `ImageFlags::FLIP_Y` (as `filter_image` documents) — after
/// which red must still be on top, where browsers put it. Runs both an
/// identity-strength filter (orientation alone) and sepia (orientation with
/// real color math, so the two halves are distinguishable values).
#[test]
fn filter_preserves_source_orientation_gl() {
    let mut buf = vec![RGBA8::new(0, 0, 255, 255); (W * H) as usize];
    for px in buf.iter_mut().take((W * H / 2) as usize) {
        *px = RGBA8::new(255, 0, 0, 255);
    }

    for_each_flavor(W, H, |gl| {
        let flavor = gl.flavor;
        for (name, filter, top_want, bottom_want) in [
            ("brightness(1)", ImageFilter::brightness(1.0), [255, 0, 0], [0, 0, 255]),
            ("sepia(1)", ImageFilter::sepia(1.0), [100, 89, 69], [48, 43, 33]),
        ] {
            let pixels = gl.render_rgba(Color::white(), |canvas| {
                let source = canvas
                    .create_image(Img::new(buf.as_slice(), W as usize, H as usize), ImageFlags::empty())
                    .expect("source image");
                let filtered = canvas
                    .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::FLIP_Y)
                    .expect("target image");
                canvas.filter_image(filtered, filter, source);
                draw_image(canvas, filtered);
            });
            let top = pixel(&pixels, W / 2, 4);
            let bottom = pixel(&pixels, W / 2, H - 4);
            assert!(
                rgb_close(top, top_want),
                "{flavor:?} {name}: top half must be ~{top_want:?} (red was uploaded on top), got {top:?}"
            );
            assert!(
                rgb_close(bottom, bottom_want),
                "{flavor:?} {name}: bottom half must be ~{bottom_want:?} (blue was uploaded on the bottom), \
                 got {bottom:?} - a swapped pair means the filter pass mirrored the image"
            );
        }
    });
}

/// `set_screen_target` hands the renderer an FBO the caller created and still
/// owns; dropping the canvas (and with it the renderer) must leave it alive.
/// The harness reads the FBO back only after the canvas is gone, so every GL
/// test depends on this — this one names the contract explicitly.
#[test]
fn screen_target_fbo_survives_renderer_drop() {
    for_each_flavor(W, H, |gl| {
        let pixels = gl.render_rgba(Color::rgb(0, 128, 255), |_| {});
        assert_eq!(
            pixel(&pixels, 0, 0),
            [0, 128, 255, 255],
            "{:?}: the caller's FBO must still hold the frame after the renderer is dropped",
            gl.flavor
        );
    });
}
