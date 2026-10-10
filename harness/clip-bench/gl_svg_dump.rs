//! The OpenGL backend's pixels for SVG fills and strokes, without a visible window: `gl_svg_dump OUT.ppm SCALE
//! FILE.svg` draws each path of the file with its solid fill and stroke (gradients as their first stop's colour,
//! no clips, masks or filters) into a 1024 x 1024 image target and writes it as a binary PPM. Two builds' dumps
//! of the same file compare how their fills rasterize.
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
use usvg::tiny_skia_path::PathSegment;
use winit::application::ApplicationHandler;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, EventLoop};
use winit::window::Window;

const W: u32 = 1024;
const H: u32 = 1024;

fn color(paint: &usvg::Paint, opacity: f32) -> Option<Color> {
    let c = match paint {
        usvg::Paint::Color(c) => *c,
        usvg::Paint::LinearGradient(g) => g.stops().first()?.color(),
        usvg::Paint::RadialGradient(g) => g.stops().first()?.color(),
        usvg::Paint::Pattern(_) => return None,
    };
    Some(Color::rgbaf(c.red as f32 / 255.0, c.green as f32 / 255.0, c.blue as f32 / 255.0, opacity))
}

fn draw(canvas: &mut Canvas<OpenGl>, group: &usvg::Group, base: Transform2D) {
    for node in group.children() {
        match node {
            usvg::Node::Group(g) => draw(canvas, g, base),
            usvg::Node::Path(p) => {
                let mut path = Path::new();
                for seg in p.data().segments() {
                    match seg {
                        PathSegment::MoveTo(a) => path.move_to(a.x, a.y),
                        PathSegment::LineTo(a) => path.line_to(a.x, a.y),
                        PathSegment::QuadTo(a, b) => path.quad_to(a.x, a.y, b.x, b.y),
                        PathSegment::CubicTo(a, b, c) => path.bezier_to(a.x, a.y, b.x, b.y, c.x, c.y),
                        PathSegment::Close => path.close(),
                    }
                }
                let t = p.abs_transform();
                let m = Transform2D([t.sx, t.ky, t.kx, t.sy, t.tx, t.ty]) * base;
                canvas.save();
                canvas.reset_transform();
                canvas.set_transform(&m);
                if let Some(fill) = p.fill() {
                    if let Some(c) = color(fill.paint(), fill.opacity().get()) {
                        let mut paint = Paint::color(c);
                        paint.set_fill_rule(match fill.rule() {
                            usvg::FillRule::NonZero => FillRule::NonZero,
                            usvg::FillRule::EvenOdd => FillRule::EvenOdd,
                        });
                        canvas.fill_path(&path, &paint);
                    }
                }
                if let Some(stroke) = p.stroke() {
                    if let Some(c) = color(stroke.paint(), stroke.opacity().get()) {
                        let mut paint = Paint::color(c);
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
        let out = args[1].clone();
        let scale: f32 = args[2].parse().unwrap();
        let tree = usvg::Tree::from_data(&std::fs::read(&args[3]).unwrap(), &usvg::Options::default()).unwrap();
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
        canvas.set_render_target(RenderTarget::Image(image));
        canvas.clear_rect(0, 0, W, H, Color::white());
        let size = tree.size();
        let fit = (W as f32 / size.width()).min(H as f32 / size.height()) * scale;
        draw(&mut canvas, tree.root(), Transform2D::scaling(fit, fit));
        canvas.flush_to_output(());
        let shot = canvas.screenshot().unwrap();
        let mut ppm = format!("P6\n{W} {H}\n255\n").into_bytes();
        for p in shot.pixels() {
            ppm.extend_from_slice(&[p.r, p.g, p.b]);
        }
        std::fs::write(&out, ppm).unwrap();
        event_loop.exit();
    }

    fn window_event(&mut self, _: &ActiveEventLoop, _: winit::window::WindowId, _: WindowEvent) {}
}

fn main() {
    let event_loop = EventLoop::new().unwrap();
    event_loop.run_app(&mut App { done: false }).unwrap();
}
