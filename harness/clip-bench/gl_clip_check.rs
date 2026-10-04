//! Shape clips on the OpenGL backend against each pixel's exact share inside the shape, without a visible window:
//! the repository's GPU tests run on wgpu only, so this is the run-time check of the GL shader and its uniforms.
//! Copy to `examples/gl_clip_check.rs` of a femtovg checkout with shape clips and `cargo run --example gl_clip_check`;
//! it prints the worst difference per case and `GL CLIP CHECK OK` when every one is under 0.08.
use std::num::NonZeroU32;

use femtovg::{renderer::OpenGl, Canvas, Color, FillRule, ImageFlags, Paint, Path, PixelFormat, RenderTarget, Transform2D};
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

const W: u32 = 96;
const H: u32 = 96;

/// The share of each pixel inside a box with round corners under `transform`, from 16 x 16 samples.
fn share_inside(transform: &Transform2D, center: [f32; 2], extent: [f32; 2], radius: f32) -> Vec<f32> {
    let inverse = transform.inverse();
    let inside = |x: f32, y: f32| {
        let (x, y) = inverse.transform_point(x, y);
        let side = [(x - center[0]).abs() - extent[0], (y - center[1]).abs() - extent[1]];
        let corner = [side[0] + radius, side[1] + radius];
        if corner[0] > 0.0 && corner[1] > 0.0 {
            corner[0].hypot(corner[1]) <= radius
        } else {
            side[0] <= 0.0 && side[1] <= 0.0
        }
    };
    (0..W * H)
        .map(|i| {
            let (left, top) = ((i % W) as f32, (i / W) as f32);
            (0..256)
                .filter(|s| inside(left + ((s % 16) as f32 + 0.5) / 16.0, top + ((s / 16) as f32 + 0.5) / 16.0))
                .count() as f32
                / 256.0
        })
        .collect()
}

struct App {
    done: bool,
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

        type Place = fn(&mut Canvas<OpenGl>);
        let turned_then_stretched: Place = |canvas| {
            canvas.translate(48.0, 48.0);
            canvas.scale(1.4, 0.6);
            canvas.rotate(0.5);
            canvas.translate(-48.0, -48.0);
        };
        let sheared: Place = |canvas| {
            canvas.translate(48.0, 48.0);
            canvas.skew_x(0.6);
            canvas.translate(-48.0, -48.0);
        };
        let turned: Place = |canvas| {
            canvas.translate(48.0, 48.0);
            canvas.rotate(0.4);
            canvas.translate(-48.0, -48.0);
        };
        let in_place: Place = |_| {};
        let mut failed = false;
        for (name, place, center, extent, radius) in [
            ("circle", in_place, [48.3, 47.6], [30.4, 30.4], 30.4),
            ("rounded rect", in_place, [47.4, 45.95], [35.0, 25.25], 14.0),
            ("rect", in_place, [45.55, 45.725], [25.25, 15.125], 0.0),
            ("rect, turned", turned, [45.55, 45.725], [25.25, 15.125], 0.0),
            ("circle, turned then stretched", turned_then_stretched, [48.3, 47.6], [30.4, 30.4], 30.4),
            ("rounded rect, turned then stretched", turned_then_stretched, [47.4, 45.95], [27.0, 20.25], 12.0),
            ("rounded rect, sheared", sheared, [47.4, 45.95], [22.0, 28.25], 12.0),
            ("circle, sheared", sheared, [48.3, 47.6], [24.4, 24.4], 24.4),
            ("corners of 0.3 px", in_place, [47.4, 45.95], [35.0, 25.25], 0.3),
            ("a box one pixel tall", in_place, [47.4, 40.3], [35.0, 0.5], 0.0),
            ("a box 1.2 px wide, turned", turned, [47.45, 46.2], [0.6, 36.0], 0.0),
        ] {
            let image = canvas
                .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty())
                .unwrap();
            canvas.save();
            canvas.set_render_target(RenderTarget::Image(image));
            canvas.clear_rect(0, 0, W, H, Color::white());
            place(&mut canvas);
            let expected = share_inside(&canvas.transform(), center, extent, radius);
            let mut clip = Path::new();
            if radius > 0.0 {
                clip.rounded_rect(center[0] - extent[0], center[1] - extent[1], 2.0 * extent[0], 2.0 * extent[1], radius);
            } else {
                clip.rect(center[0] - extent[0], center[1] - extent[1], 2.0 * extent[0], 2.0 * extent[1]);
            }
            canvas.clip_path(&clip, FillRule::NonZero);
            canvas.reset_transform();
            let mut everything = Path::new();
            // No rect: under an upright rect clip a rect is drawn as the rect the two share, by its own fringe.
            everything.move_to(-8.0, -8.0);
            everything.line_to(W as f32 + 8.0, -8.0);
            everything.line_to(W as f32 + 8.0, H as f32 + 8.0);
            everything.line_to(-8.0, H as f32 + 8.0);
            everything.line_to(-24.0, H as f32 * 0.5);
            everything.close();
            canvas.fill_path(&everything, &Paint::color(Color::rgb(255, 0, 0)));
            // The image target stays bound after the flush, so the screenshot reads it.
            canvas.flush_to_output(());
            let shot = canvas.screenshot().unwrap();
            let pixels: Vec<_> = shot.pixels().collect();
            let worst = (0..(W * H) as usize)
                .map(|i| (1.0 - f32::from(pixels[i].g) / 255.0 - expected[i]).abs())
                .fold(0.0, f32::max);
            let partial = pixels.iter().filter(|p| p.g != 0 && p.g != 255).count();
            println!("{name}: worst {worst:.3} from the share inside ({partial} partly covered pixels)");
            failed |= worst >= 0.08 || partial < 60;
            canvas.restore();
            canvas.set_render_target(RenderTarget::Screen);
            canvas.flush_to_output(());
            canvas.delete_image(image);
        }
        println!("{}", if failed { "GL CLIP CHECK FAILED" } else { "GL CLIP CHECK OK" });
        event_loop.exit();
    }

    fn window_event(&mut self, _: &ActiveEventLoop, _: winit::window::WindowId, _: WindowEvent) {}
}

fn main() {
    let event_loop = EventLoop::new().unwrap();
    event_loop.run_app(&mut App { done: false }).unwrap();
}
