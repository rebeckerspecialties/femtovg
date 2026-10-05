//! `ImageFilter::Crop` on the OpenGL backend, without a visible window: the repository's GPU tests run on wgpu
//! only, so this is the run-time check of the scissor the GL filter passes draw inside. A source with no two rows
//! and no two columns alike is run through chains that end in a crop - after one draw from an upload, on a blur's
//! second draw, alone, from a render target, between other passes, and in a layer - and composited on white:
//! inside the rect the source must show, outside it nothing. Copy to `examples/gl_crop_check.rs` of a femtovg
//! checkout with `ImageFilter::Crop` and `cargo run --example gl_crop_check`; prints `GL CROP CHECK OK`.
use std::num::NonZeroU32;

use femtovg::{renderer::OpenGl, Canvas, Color, ImageFilter, ImageFlags, ImageId, LayerEffects, Paint, Path, PixelFormat, RenderTarget};
use glutin::{
    config::ConfigTemplateBuilder,
    context::{ContextApi, ContextAttributesBuilder},
    display::GetGlDisplay,
    prelude::*,
    surface::SurfaceAttributesBuilder,
};
use glutin_winit::DisplayBuilder;
use raw_window_handle::HasWindowHandle;
use winit::application::ApplicationHandler;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, EventLoop};
use winit::window::Window;

const W: u32 = 32;
const H: u32 = 32;

struct App {
    done: bool,
}

fn filter_target(canvas: &mut Canvas<OpenGl>) -> ImageId {
    canvas
        .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::FLIP_Y | ImageFlags::PREMULTIPLIED)
        .unwrap()
}

/// `image` composited on white in an image target, read back top row first.
fn on_white(canvas: &mut Canvas<OpenGl>, image: ImageId) -> Vec<[u8; 3]> {
    let out = canvas
        .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty())
        .unwrap();
    canvas.set_render_target(RenderTarget::Image(out));
    canvas.clear_rect(0, 0, W, H, Color::white());
    let mut all = Path::new();
    all.rect(0.0, 0.0, W as f32, H as f32);
    canvas.fill_path(&all, &Paint::image(image, 0.0, 0.0, W as f32, H as f32, 0.0, 1.0));
    canvas.flush_to_output(());
    let shot = canvas.screenshot().unwrap();
    let pixels = shot.pixels().map(|p| [p.r, p.g, p.b]).collect();
    canvas.set_render_target(RenderTarget::Screen);
    canvas.flush_to_output(());
    canvas.delete_image(out);
    pixels
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.done {
            return;
        }
        self.done = true;
        let window_attrs = Window::default_attributes()
            .with_inner_size(winit::dpi::PhysicalSize::new(W, H))
            .with_visible(false);
        let template = ConfigTemplateBuilder::new().with_alpha_size(8).with_stencil_size(8);
        let (window, gl_config) = DisplayBuilder::new()
            .with_window_attributes(Some(window_attrs))
            .build(event_loop, template, |mut configs| configs.next().unwrap())
            .unwrap();
        let window = window.unwrap();
        let raw = window.window_handle().unwrap().as_raw();
        let gl_display = gl_config.display();
        let attributes = ContextAttributesBuilder::new().build(Some(raw));
        let fallback = ContextAttributesBuilder::new().with_context_api(ContextApi::Gles(None)).build(Some(raw));
        let context = unsafe {
            gl_display
                .create_context(&gl_config, &attributes)
                .unwrap_or_else(|_| gl_display.create_context(&gl_config, &fallback).unwrap())
        };
        let attrs = SurfaceAttributesBuilder::<glutin::surface::WindowSurface>::new().build(
            raw,
            NonZeroU32::new(W).unwrap(),
            NonZeroU32::new(H).unwrap(),
        );
        let surface = unsafe { gl_display.create_window_surface(&gl_config, &attrs).unwrap() };
        let _context = context.make_current(&surface).unwrap();
        let renderer = unsafe { OpenGl::new_from_function_cstr(|s| gl_display.get_proc_address(s).cast()) }.unwrap();
        let mut canvas = Canvas::new(renderer).unwrap();
        canvas.set_size(W, H, 1.0);

        let src: Vec<femtovg::rgb::RGBA8> = (0..W * H)
            .map(|i| femtovg::rgb::RGBA8::new((i % W * 8) as u8, (i / W * 8) as u8, 0, 255))
            .collect();
        let source = canvas
            .create_image(femtovg::imgref::Img::new(&src[..], W as usize, H as usize), ImageFlags::empty())
            .unwrap();
        let crop = ImageFilter::Crop { x: 3.0, y: 5.0, width: 10.0, height: 6.0 };
        let copy = ImageFilter::brightness(1.0);
        let mut failed = false;
        let mut check = |name: &str, pixels: &[[u8; 3]], inside: &dyn Fn(u32, u32) -> Option<[u8; 3]>| {
            let wrong = (0..W * H)
                .filter(|i| {
                    let (x, y) = (i % W, i / W);
                    let want = inside(x, y).unwrap_or([255, 255, 255]);
                    let got = pixels[*i as usize];
                    (0..3).any(|c| got[c].abs_diff(want[c]) > 1)
                })
                .count();
            println!("{name}: {wrong} pixels wrong");
            failed |= wrong > 0;
        };
        let pattern = |x: u32, y: u32| ((3..13).contains(&x) && (5..11).contains(&y)).then_some([(x * 8) as u8, (y * 8) as u8, 0]);

        for (name, chain) in [
            ("a draw from an upload", vec![copy, crop]),
            ("a blur's second draw", vec![ImageFilter::gaussian_blur(0.0), crop]),
            ("a crop alone", vec![crop]),
            ("passes on both sides", vec![copy, copy, crop, copy]),
        ] {
            let filtered = filter_target(&mut canvas);
            canvas.filter_image_chain(filtered, &chain, source).unwrap();
            let pixels = on_white(&mut canvas, filtered);
            check(name, &pixels, &pattern);
            canvas.delete_image(filtered);
        }

        // From a render target: the upload copied into one first.
        let stored = filter_target(&mut canvas);
        canvas.filter_image_chain(stored, &[], source).unwrap();
        let filtered = filter_target(&mut canvas);
        canvas.filter_image_chain(filtered, &[copy, crop], stored).unwrap();
        let pixels = on_white(&mut canvas, filtered);
        check("a draw from a render target", &pixels, &pattern);

        // What a crop clips away does not come back: a square shifted out of the rect and back.
        let mut square = vec![femtovg::rgb::RGBA8::new(0, 0, 0, 0); (W * H) as usize];
        for y in 8..16 {
            for x in 8..16 {
                square[(y * W + x) as usize] = femtovg::rgb::RGBA8::new(255, 0, 0, 255);
            }
        }
        let square = canvas
            .create_image(femtovg::imgref::Img::new(&square[..], W as usize, H as usize), ImageFlags::empty())
            .unwrap();
        let region = ImageFilter::Crop { x: 0.0, y: 0.0, width: 24.0, height: H as f32 };
        let (out, back) = (ImageFilter::Offset { dx: 12.0, dy: 0.0 }, ImageFilter::Offset { dx: -12.0, dy: 0.0 });
        let filtered = filter_target(&mut canvas);
        canvas.filter_image_chain(filtered, &[out, region, back], square).unwrap();
        let pixels = on_white(&mut canvas, filtered);
        check("shifted out of the rect and back", &pixels, &|x, y| {
            ((8..12).contains(&x) && (8..16).contains(&y)).then_some([255, 0, 0])
        });

        // A layer's crop, in root device space, under a scissor that moves the layer's store.
        let out = canvas
            .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty())
            .unwrap();
        canvas.set_render_target(RenderTarget::Image(out));
        canvas.clear_rect(0, 0, W, H, Color::white());
        canvas.save();
        canvas.scissor(6.0, 9.0, 20.0, 18.0);
        let effects = LayerEffects::new().with_filters(&[
            ImageFilter::Offset { dx: 3.0, dy: 0.0 },
            ImageFilter::Crop { x: 10.0, y: 12.0, width: 7.0, height: 5.0 },
        ]);
        assert!(canvas.begin_layer(&effects));
        let mut everything = Path::new();
        everything.rect(0.0, 0.0, W as f32, H as f32);
        canvas.fill_path(&everything, &Paint::color(Color::rgb(255, 0, 0)));
        canvas.end_layer();
        canvas.restore();
        canvas.flush_to_output(());
        let shot = canvas.screenshot().unwrap();
        let pixels: Vec<[u8; 3]> = shot.pixels().map(|p| [p.r, p.g, p.b]).collect();
        check("a layer's crop in root space", &pixels, &|x, y| {
            ((10..17).contains(&x) && (12..17).contains(&y)).then_some([255, 0, 0])
        });

        println!("{}", if failed { "GL CROP CHECK FAILED" } else { "GL CROP CHECK OK" });
        event_loop.exit();
    }

    fn window_event(&mut self, _: &ActiveEventLoop, _: winit::window::WindowId, _: WindowEvent) {}
}

fn main() {
    let event_loop = EventLoop::new().unwrap();
    event_loop.run_app(&mut App { done: false }).unwrap();
}
