//! What taking a clip costs the canvas once its mask exists: `mask_cost [mask|stencil] [star|blob] SIZE` clips to a
//! path that is no box and fills a rect under it, a hundred thousand times with the Void renderer, flushing every
//! hundred, and prints microseconds a clip. `stencil` sets the mask budget to zero.
use femtovg::{renderer::Void, Canvas, Color, FillRule, Paint, Path};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let how = args.get(1).map(String::as_str).unwrap_or("mask").to_owned();
    let what = args.get(2).map(String::as_str).unwrap_or("star").to_owned();
    let size: f32 = args.get(3).and_then(|v| v.parse().ok()).unwrap_or(200.0);
    let mut canvas = Canvas::new(Void).unwrap();
    canvas.set_size(1920, 1080, 1.0);
    if how == "stencil" {
        canvas.set_clip_mask_budget(0);
    }
    let (cx, cy, r) = (960.3, 540.6, size * 0.5);
    let mut clip = Path::new();
    if what == "star" {
        for i in 0..10 {
            let a = i as f32 * std::f32::consts::PI / 5.0;
            let radius = if i % 2 == 0 { r } else { r * 0.45 };
            let (x, y) = (cx + radius * a.sin(), cy - radius * a.cos());
            if i == 0 {
                clip.move_to(x, y);
            } else {
                clip.line_to(x, y);
            }
        }
    } else {
        // A circle with a bite out of it: curves all the way around.
        clip.arc(cx, cy, r, 0.4, std::f32::consts::TAU - 0.4, femtovg::Solidity::Hole);
        clip.quad_to(cx + r * 0.3, cy, cx + r * 0.4_f32.cos(), cy + r * 0.4_f32.sin());
    }
    clip.close();
    let mut rect = Path::new();
    rect.rect(cx - 10.0, cy - 10.0, 20.0, 20.0);
    let paint = Paint::color(Color::rgb(40, 90, 200));
    let frames = 1000;
    let started = std::time::Instant::now();
    for _ in 0..frames {
        for _ in 0..100 {
            canvas.save();
            canvas.clip_path(&clip, FillRule::NonZero);
            canvas.fill_path(&rect, &paint);
            canvas.restore();
        }
        canvas.flush_to_output(());
    }
    let us = started.elapsed().as_secs_f64() * 1e6 / (frames * 100) as f64;
    println!("{how} {what} {size}: {us:.2} us a clip and a fill");
}
