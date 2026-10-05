//! Fill-rate cost on the OpenGL backend, without a visible window. `gl_fill_bench <scene> <frames>` draws into a
//! 1920 x 1080 image target and prints the mean frame time once the last frame has been read back. Scenes: `none`
//! (40 full-screen translucent fills), `rect` and `rounded` (the same under one clip), `cards` (200 small cards)
//! and `cards_rounded` (each card under a rounded-rect clip of its own). A fill scene takes `paths_` before its
//! name for fills that are no rects and `_small` after it for a 400 x 300 clip in the middle of the target; `ellipse`
//! clips to the ellipse in the clip's rect and `star` to a ten-pointed star, which is no box. Copy to `examples/` of a femtovg checkout and
//! `cargo build --release --example gl_fill_bench`; glpaired.py compares two builds.
use std::num::NonZeroU32;

use femtovg::{renderer::OpenGl, Canvas, Color, FillRule, ImageFlags, Paint, Path, PixelFormat, RenderTarget};
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

const W: u32 = 1920;
const H: u32 = 1080;

struct App {
    done: bool,
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.done {
            return;
        }
        self.done = true;
        let args: Vec<String> = std::env::args().collect();
        let scene = args.get(1).map(String::as_str).unwrap_or("none").to_owned();
        let frames: usize = args.get(2).and_then(|v| v.parse().ok()).unwrap_or(100);
        let window_attrs = Window::default_attributes()
            .with_inner_size(winit::dpi::PhysicalSize::new(64, 64))
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
            NonZeroU32::new(64).unwrap(),
            NonZeroU32::new(64).unwrap(),
        );
        let surface = unsafe { gl_display.create_window_surface(&gl_config, &attrs).unwrap() };
        let _context = context.make_current(&surface).unwrap();
        let renderer = unsafe { OpenGl::new_from_function_cstr(|s| gl_display.get_proc_address(s).cast()) }.unwrap();
        let mut canvas = Canvas::new(renderer).unwrap();
        canvas.set_size(W, H, 1.0);
        let image = canvas
            .create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty())
            .unwrap();
        let mut frame = |canvas: &mut Canvas<OpenGl>| {
            canvas.save();
            canvas.set_render_target(RenderTarget::Image(image));
            canvas.clear_rect(0, 0, W, H, Color::white());
            if scene == "cards" || scene == "cards_rounded" {
                for i in 0..200 {
                    let (x, y) = (6.0 + (i % 20) as f32 * 96.0, 6.0 + (i / 20) as f32 * 102.0);
                    canvas.save();
                    if scene == "cards_rounded" {
                        let mut clip = Path::new();
                        clip.rounded_rect(x, y, 90.0, 96.0, 12.0);
                        canvas.clip_path(&clip, FillRule::NonZero);
                    }
                    let mut card = Path::new();
                    card.rect(x - 4.0, y - 4.0, 98.0, 104.0);
                    canvas.fill_path(&card, &Paint::color(Color::rgba(40, 90, (i % 255) as u8, 255)));
                    let mut band = Path::new();
                    band.rect(x, y + 30.0, 90.0, 20.0);
                    canvas.fill_path(&band, &Paint::color(Color::rgba(250, 200, 60, 255)));
                    canvas.restore();
                }
            } else {
                let paths = scene.starts_with("paths_");
                let small = scene.ends_with("_small");
                let clip_kind = scene.trim_start_matches("paths_").trim_end_matches("_small");
                if clip_kind != "none" {
                    let (x, y, w, h, r) = if small {
                        (760.5, 390.5, 400.0, 300.0, 40.0)
                    } else {
                        (10.5, 10.5, 1899.0, 1059.0, 80.0)
                    };
                    let mut clip = Path::new();
                    match clip_kind {
                        "rect" => clip.rect(x, y, w, h),
                        "star" => {
                            let (cx, cy, outer) = (x + w * 0.5, y + h * 0.5, w.min(h) * 0.5);
                            for i in 0..20 {
                                let a = i as f32 * std::f32::consts::PI / 10.0;
                                let radius = if i % 2 == 0 { outer } else { outer * 0.45 };
                                let (px, py) = (cx + radius * a.sin(), cy - radius * a.cos());
                                if i == 0 {
                                    clip.move_to(px, py);
                                } else {
                                    clip.line_to(px, py);
                                }
                            }
                            clip.close();
                        }
                        "ellipse" => clip.ellipse(x + w * 0.5, y + h * 0.5, w * 0.5, h * 0.5),
                        _ => clip.rounded_rect(x, y, w, h, r),
                    }
                    canvas.clip_path(&clip, FillRule::NonZero);
                }
                for i in 0..40 {
                    let (x, y) = (-5.0 + (i % 3) as f32, -5.0 + (i % 2) as f32);
                    let mut fill = Path::new();
                    if paths {
                        fill.move_to(x, y);
                        fill.line_to(x + 1930.0, y);
                        fill.line_to(x + 1930.0, y + 1090.0);
                        fill.line_to(x, y + 1090.0);
                        fill.line_to(x - 20.0, y + 545.0);
                        fill.close();
                    } else {
                        fill.rect(x, y, 1930.0, 1090.0);
                    }
                    canvas.fill_path(&fill, &Paint::color(Color::rgba((i * 6) as u8, 120, 200 - (i * 4) as u8, 51)));
                }
            }
            canvas.restore();
            canvas.flush_to_output(());
        };
        // Warm up, and let the readback drain the queue before the clock starts.
        frame(&mut canvas);
        canvas.screenshot().unwrap();
        let started = std::time::Instant::now();
        for _ in 0..frames {
            frame(&mut canvas);
        }
        let shot = canvas.screenshot().unwrap();
        let ms = started.elapsed().as_secs_f64() * 1000.0 / frames as f64;
        let p = shot.pixels().nth((540 * W + 960) as usize).unwrap();
        println!("frame_ms={ms:.4} scene={scene} frames={frames} center={},{},{}", p.r, p.g, p.b);
        event_loop.exit();
    }

    fn window_event(&mut self, _: &ActiveEventLoop, _: winit::window::WindowId, _: WindowEvent) {}
}

fn main() {
    let event_loop = EventLoop::new().unwrap();
    event_loop.run_app(&mut App { done: false }).unwrap();
}
