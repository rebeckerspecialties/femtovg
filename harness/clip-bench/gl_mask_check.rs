//! Mask clips on the OpenGL backend, without a visible window: the repository's GPU tests run on wgpu only, so this
//! is the run-time check of the GL shader, its sampler and its uniforms. A path that is no box is clipped through a
//! coverage mask; each pixel must take the share of it the path covers, children must clip to their union, a mask
//! must cut with a clip shape beside it, and an operation coverage cannot bound must take a pixel whole or not at
//! all. Copy to `examples/gl_mask_check.rs` of a femtovg checkout with mask clips and
//! `cargo run --example gl_mask_check`; it prints the worst difference per case and `GL MASK CHECK OK`.
use std::num::NonZeroU32;

use femtovg::{
    renderer::OpenGl, Canvas, Color, CompositeOperation, FillRule, ImageFlags, Paint, Path, PixelFormat, RenderTarget,
    Transform2D,
};
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

/// The area of a simple polygon inside the pixel at (`px`, `py`): the polygon cut to the pixel's four sides.
fn area_inside(polygon: &[[f32; 2]], px: u32, py: u32) -> f32 {
    let mut points: Vec<[f64; 2]> = polygon.iter().map(|p| [f64::from(p[0]), f64::from(p[1])]).collect();
    let (x0, y0) = (f64::from(px), f64::from(py));
    for (axis, bound, below) in [(0, x0, false), (0, x0 + 1.0, true), (1, y0, false), (1, y0 + 1.0, true)] {
        let inside = |p: &[f64; 2]| if below { p[axis] <= bound } else { p[axis] >= bound };
        let mut out = Vec::with_capacity(points.len() + 4);
        for (index, current) in points.iter().enumerate() {
            let previous = &points[(index + points.len() - 1) % points.len()];
            let crossing = || {
                let t = (bound - previous[axis]) / (current[axis] - previous[axis]);
                [previous[0] + t * (current[0] - previous[0]), previous[1] + t * (current[1] - previous[1])]
            };
            match (inside(previous), inside(current)) {
                (true, true) => out.push(*current),
                (true, false) => out.push(crossing()),
                (false, true) => {
                    out.push(crossing());
                    out.push(*current);
                }
                (false, false) => {}
            }
        }
        points = out;
        if points.is_empty() {
            return 0.0;
        }
    }
    let twice: f64 = points.iter().zip(points.iter().cycle().skip(1)).map(|(a, b)| a[0] * b[1] - b[0] * a[1]).sum();
    (twice.abs() / 2.0) as f32
}

fn polygon(points: &[[f32; 2]]) -> Path {
    let mut path = Path::new();
    path.move_to(points[0][0], points[0][1]);
    for point in &points[1..] {
        path.line_to(point[0], point[1]);
    }
    path.close();
    path
}

const TRIANGLE: [[f32; 2]; 3] = [[48.3, 9.4], [86.7, 80.2], [11.6, 71.9]];
const ARROW: [[f32; 2]; 7] =
    [[12.4, 40.2], [50.3, 40.2], [50.3, 22.6], [84.9, 49.1], [50.3, 76.3], [50.3, 58.7], [22.4, 49.3]];
const SLIVER: [[f32; 2]; 3] = [[18.2, 30.3], [78.4, 50.8], [18.2, 30.63]];

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

        // Draws into a fresh image and reads it back: (red, green, blue) of each pixel.
        let mut shoot = |canvas: &mut Canvas<OpenGl>, background: Color, draw: &dyn Fn(&mut Canvas<OpenGl>)| {
            let image =
                canvas.create_image_empty(W as usize, H as usize, PixelFormat::Rgba8, ImageFlags::empty()).unwrap();
            canvas.save();
            canvas.set_render_target(RenderTarget::Image(image));
            canvas.clear_rect(0, 0, W, H, background);
            draw(canvas);
            // The image target stays bound after the flush, so the screenshot reads it.
            canvas.flush_to_output(());
            let shot = canvas.screenshot().unwrap();
            let pixels: Vec<[u8; 3]> = shot.pixels().map(|p| [p.r, p.g, p.b]).collect();
            canvas.restore();
            canvas.set_render_target(RenderTarget::Screen);
            canvas.flush_to_output(());
            canvas.delete_image(image);
            pixels
        };
        let fill_everything = |canvas: &mut Canvas<OpenGl>| {
            let mut everything = Path::new();
            everything.rect(-8.0, -8.0, W as f32 + 16.0, H as f32 + 16.0);
            canvas.fill_path(&everything, &Paint::color(Color::rgb(255, 0, 0)));
        };
        let covered = |pixels: &[[u8; 3]], x: u32, y: u32| 1.0 - f32::from(pixels[(y * W + x) as usize][1]) / 255.0;
        let mut failed = false;

        let turned = {
            let mut turned = Transform2D::translation(-48.0, -48.0);
            turned.rotate(0.37);
            turned.translate(46.6, 49.2);
            turned
        };
        let placements = [
            ("in place", Transform2D::identity()),
            ("scaled", Transform2D::new(0.7, 0.0, 0.0, 1.21, 9.3, -11.7)),
            ("turned", turned),
        ];
        let shapes: [(&str, &[[f32; 2]]); 3] = [("triangle", &TRIANGLE), ("arrow", &ARROW), ("sliver", &SLIVER)];
        for (placed, transform) in &placements {
            for (name, points) in shapes {
                let pixels = shoot(&mut canvas, Color::white(), &|canvas| {
                    canvas.set_transform(transform);
                    canvas.clip_path(&polygon(points), FillRule::NonZero);
                    canvas.reset_transform();
                    fill_everything(canvas);
                });
                let placed_points: Vec<[f32; 2]> = points
                    .iter()
                    .map(|p| {
                        let (x, y) = transform.transform_point(p[0], p[1]);
                        [x, y]
                    })
                    .collect();
                let (mut worst, mut partial) = (0.0f32, 0);
                for y in 0..H {
                    for x in 0..W {
                        let exact = area_inside(&placed_points, x, y);
                        partial += usize::from(exact > 0.02 && exact < 0.98);
                        worst = worst.max((covered(&pixels, x, y) - exact).abs());
                    }
                }
                println!("{name}, {placed}: worst {worst:.4} from the area inside ({partial} edge pixels)");
                failed |= worst > 1.5 / 255.0 + 1e-3 || partial < 40;
            }
        }

        // Children clip to their union: two rects that meet at x = 47.4 leave no seam, and circles one inside the
        // other under even-odd fill the disc.
        let rect = |x0: f32, x1: f32| polygon(&[[x0, 20.0], [x1, 20.0], [x1, 70.0], [x0, 70.0]]);
        let abutting = shoot(&mut canvas, Color::white(), &|canvas| {
            canvas.clip_paths(&[(&rect(16.0, 47.4), FillRule::NonZero), (&rect(47.4, 80.0), FillRule::NonZero)]);
            fill_everything(canvas);
        });
        let seam = (16..80).map(|x| covered(&abutting, x, 40)).fold(1.0, f32::min);
        println!("two rects that share an edge: least coverage along the row across it {seam:.3}");
        failed |= seam < 1.0 || covered(&abutting, 12, 40) != 0.0;
        let circle = |r: f32| {
            let mut path = Path::new();
            path.circle(48.0, 48.0, r);
            path
        };
        let discs = shoot(&mut canvas, Color::white(), &|canvas| {
            canvas.clip_paths(&[(&circle(40.0), FillRule::EvenOdd), (&circle(20.0), FillRule::EvenOdd)]);
            fill_everything(canvas);
        });
        println!(
            "circles one inside the other, even-odd each: center {:.3}, ring {:.3}, outside {:.3}",
            covered(&discs, 48, 48),
            covered(&discs, 48, 18),
            covered(&discs, 4, 4)
        );
        failed |= covered(&discs, 48, 48) != 1.0 || covered(&discs, 48, 18) != 1.0 || covered(&discs, 4, 4) != 0.0;

        // A mask beside a clip shape: the product of the two.
        let with_shape = shoot(&mut canvas, Color::white(), &|canvas| {
            canvas.clip_path(&circle(30.0), FillRule::NonZero);
            canvas.clip_path(&polygon(&TRIANGLE), FillRule::NonZero);
            fill_everything(canvas);
        });
        let shape_alone = shoot(&mut canvas, Color::white(), &|canvas| {
            canvas.clip_path(&circle(30.0), FillRule::NonZero);
            fill_everything(canvas);
        });
        let mut worst = 0.0f32;
        for y in 0..H {
            for x in 0..W {
                let expected = covered(&shape_alone, x, y) * area_inside(&TRIANGLE, x, y);
                worst = worst.max((covered(&with_shape, x, y) - expected).abs());
            }
        }
        println!("a mask beside a clip shape: worst {worst:.4} from the product of the two");
        failed |= worst > 2.5 / 255.0;

        // Copy under a mask: each pixel the fill's colour or what was there, by half the pixel.
        let copied = shoot(&mut canvas, Color::rgb(0, 0, 255), &|canvas| {
            canvas.clip_path(&polygon(&TRIANGLE), FillRule::NonZero);
            canvas.global_composite_operation(CompositeOperation::Copy);
            fill_everything(canvas);
        });
        let mut wrong = 0;
        for y in 0..H {
            for x in 0..W {
                let (share, pixel) = (area_inside(&TRIANGLE, x, y), copied[(y * W + x) as usize]);
                let (fill, there) = (pixel == [255, 0, 0], pixel == [0, 0, 255]);
                wrong += usize::from(!(fill || there) || (share > 0.55 && !fill) || (share < 0.45 && !there));
            }
        }
        println!("Copy under a mask: {wrong} pixels that are neither whole nor untouched by half the pixel");
        failed |= wrong != 0;

        println!("{}", if failed { "GL MASK CHECK FAILED" } else { "GL MASK CHECK OK" });
        event_loop.exit();
    }

    fn window_event(&mut self, _: &ActiveEventLoop, _: winit::window::WindowId, _: WindowEvent) {}
}

fn main() {
    let event_loop = EventLoop::new().unwrap();
    event_loop.run_app(&mut App { done: false }).unwrap();
}
