//! What a draw costs the canvas before the renderer sees it: `draw_cost [scissor|clip|none] [rect|path]` records
//! two million fills of a small shape with the Void renderer, flushing every thousand, and prints nanoseconds a fill.
use femtovg::{renderer::Void, Canvas, Color, FillRule, Paint, Path};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let under = args.get(1).map(String::as_str).unwrap_or("none").to_owned();
    let what = args.get(2).map(String::as_str).unwrap_or("rect").to_owned();
    let mut canvas = Canvas::new(Void).unwrap();
    canvas.set_size(1920, 1080, 1.0);
    let paint = Paint::color(Color::rgb(40, 90, 200));
    let mut shapes = Vec::new();
    for i in 0..64 {
        let (x, y) = (100.0 + (i % 8) as f32 * 90.0, 100.0 + (i / 8) as f32 * 90.0);
        let mut path = Path::new();
        if what == "rect" {
            path.rect(x, y, 60.0, 50.0);
        } else {
            path.move_to(x, y);
            path.line_to(x + 60.0, y + 5.0);
            path.line_to(x + 50.0, y + 50.0);
            path.line_to(x + 20.0, y + 30.0);
            path.line_to(x - 5.0, y + 45.0);
            path.close();
        }
        shapes.push(path);
    }
    let frames = 2000;
    let started = std::time::Instant::now();
    for _ in 0..frames {
        canvas.save();
        match under.as_str() {
            "scissor" => canvas.scissor(50.0, 50.0, 1800.0, 980.0),
            "clip" => {
                let mut clip = Path::new();
                clip.rounded_rect(50.0, 50.0, 1800.0, 980.0, 40.0);
                canvas.clip_path(&clip, FillRule::NonZero);
            }
            _ => {}
        }
        for i in 0..1000 {
            canvas.fill_path(&shapes[i % 64], &paint);
        }
        canvas.restore();
        canvas.flush_to_output(());
    }
    let ns = started.elapsed().as_secs_f64() * 1e9 / (frames * 1000) as f64;
    println!("{under} {what}: {ns:.1} ns a fill");
}
