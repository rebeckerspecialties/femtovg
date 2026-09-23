//! A renderer that serializes each flush instead of drawing it, and a
//! replayer that feeds the serialized flush to another renderer.
//!
//! [`WireRenderer`] splits femtovg at the [`Renderer`] boundary: everything
//! the [`Canvas`](crate::Canvas) does on the CPU (transforms, path flattening,
//! tessellation, command building) runs where the `WireRenderer` lives, and
//! each flush leaves as the canvas's vertex array plus a flat stream of
//! little-endian `u32` words describing the commands. [`WireReplayer`]
//! decodes that stream back into [`Command`]s and hands them, with the
//! vertices, to a real renderer. The GPU side is then exactly that renderer's
//! own path, and the two halves can sit in different address spaces, for
//! instance a WebAssembly guest producing frames for a native host that owns
//! the GPU.
//!
//! Images cross the boundary as `u32` handles that the [`WireSink`] hands out
//! (the replayer's [`image_alloc`](WireReplayer::image_alloc) is one such
//! allocator). Image pixel data is sent through the sink when the canvas
//! uploads it, not with every frame.
//!
//! The encoder and decoder are both in this module and share one layout, so
//! they must come from the same femtovg version; the stream starts with
//! [`WIRE_VERSION`] so that a mismatch is caught at decode time. Word layout,
//! `NONE` = `u32::MAX`:
//!
//! ```text
//! stream   := WIRE_VERSION n_commands command*
//! command  := kind clip_active fill_rule image filter_scratch
//!             glyph_kind glyph_image blend[4] tri_first tri_count
//!             n_drawables (fill_first fill_count stroke_first stroke_count)*
//!             payload
//! payload  := ClipFill:            -
//!             ClipReset:           visible
//!             SetRenderTarget:     target (0 screen, 1 image) handle
//!             ClearRect:           f32 rgba[4] keep_clip
//!             ConvexFill / Stroke / Triangles: params
//!             ConcaveFill:         params(stencil) params(fill)
//!             StencilStroke:       params(1) params(2)
//!             RenderFilteredImage: target_image filter
//! params   := 53 words, the fields of `Params` in declaration order (f32 bits,
//!             shader_type and glyph_texture_type as integers)
//! filter   := 0 sigma | 1 f32 matrix[20] | 2 f32 base_frequency[2] num_octaves
//!             seed stitch_tiles kind f32 transform[6] | 3 (linear→sRGB) |
//!             4 (sRGB→linear)
//! ```
//!
//! `kind` is 0..=9 in `CommandType` declaration order, `fill_rule` is 0
//! even-odd / 1 non-zero, `glyph_kind` is 0 none / 1 alpha mask / 2 color
//! texture, and `blend` holds `BlendFactor` ordinals.

use imgref::{ImgRef, ImgVec};
use rgb::{alt::Gray, RGB8, RGBA8};

use crate::{
    image::ImageStore, paint::GlyphTexture, renderer::Drawable, BlendFactor, Color, CompositeOperationState, ErrorKind,
    FillRule, ImageFilter, ImageId, ImageInfo, ImageSource, PixelFormat, Transform2D, TurbulenceKind,
};

use super::{Command, CommandType, Params, RenderTarget, Renderer, ShaderType, SurfacelessRenderer, Vertex};

/// Version word at the start of every encoded flush.
pub const WIRE_VERSION: u32 = 1;

const NONE: u32 = u32::MAX;
const PARAMS_WORDS: usize = 53;

/// Where a [`WireRenderer`] sends what it produces.
pub trait WireSink {
    /// The canvas size changed.
    fn set_size(&mut self, width: u32, height: u32, dpi: f32);
    /// Allocate an image; returns the handle later commands refer to it by.
    fn image_alloc(&mut self, info: ImageInfo) -> Result<u32, ErrorKind>;
    /// Upload `width` × `height` pixels of `format` at (`x`, `y`) of image
    /// `handle`. `data` is tightly packed rows.
    #[allow(clippy::too_many_arguments)]
    fn image_update(
        &mut self,
        handle: u32,
        x: usize,
        y: usize,
        width: usize,
        height: usize,
        format: PixelFormat,
        data: &[u8],
    ) -> Result<(), ErrorKind>;
    /// Free image `handle`.
    fn image_delete(&mut self, handle: u32);
    /// One flush: the canvas's vertices and the encoded command stream.
    fn render(&mut self, verts: &[Vertex], commands: &[u32]);
}

/// Image type of [`WireRenderer`]: the sink's handle plus the image's info.
#[derive(Debug)]
pub struct WireImage {
    handle: u32,
    info: ImageInfo,
}

impl WireImage {
    /// The handle the sink assigned to this image.
    pub fn handle(&self) -> u32 {
        self.handle
    }
}

/// A [`Renderer`] that encodes every flush into the wire format and passes it
/// to a [`WireSink`].
#[derive(Debug)]
pub struct WireRenderer<S: WireSink> {
    sink: S,
    words: Vec<u32>,
}

impl<S: WireSink> WireRenderer<S> {
    /// Creates a wire renderer that delivers to `sink`.
    pub fn new(sink: S) -> Self {
        Self {
            sink,
            words: Vec::new(),
        }
    }

    /// The sink.
    pub fn sink(&self) -> &S {
        &self.sink
    }

    /// The sink, mutably.
    pub fn sink_mut(&mut self) -> &mut S {
        &mut self.sink
    }

    fn flush(&mut self, images: &ImageStore<WireImage>, verts: &[Vertex], commands: &[Command]) {
        self.words.clear();
        encode(&mut self.words, images, commands);
        self.sink.render(verts, &self.words);
    }
}

impl<S: WireSink> Renderer for WireRenderer<S> {
    type Image = WireImage;
    type NativeTexture = ();
    type ExternalTexture = ();
    type RenderOutput = ();
    type CommandBuffer = ();

    fn set_size(&mut self, width: u32, height: u32, dpi: f32) {
        self.sink.set_size(width, height, dpi);
    }

    fn render(
        &mut self,
        _output: impl Into<Self::RenderOutput>,
        images: &mut ImageStore<Self::Image>,
        verts: &[Vertex],
        commands: Vec<Command>,
    ) {
        self.flush(images, verts, &commands);
    }

    fn alloc_image(&mut self, info: ImageInfo) -> Result<Self::Image, ErrorKind> {
        Ok(WireImage {
            handle: self.sink.image_alloc(info)?,
            info,
        })
    }

    fn create_image_from_native_texture(
        &mut self,
        _native_texture: Self::NativeTexture,
        _info: ImageInfo,
    ) -> Result<Self::Image, ErrorKind> {
        Err(ErrorKind::UnsupportedImageFormat)
    }

    fn create_image_from_external_texture(
        &mut self,
        _external_texture: Self::ExternalTexture,
        _info: ImageInfo,
    ) -> Result<Self::Image, ErrorKind> {
        Err(ErrorKind::UnsupportedImageFormat)
    }

    fn update_image(
        &mut self,
        image: &mut Self::Image,
        data: ImageSource,
        x: usize,
        y: usize,
    ) -> Result<(), ErrorKind> {
        data.check_update(&image.info, x, y)?;
        let (format, width, height, bytes) = match data {
            ImageSource::Rgb(img) => (PixelFormat::Rgb8, img.width(), img.height(), packed_rows(img)),
            ImageSource::Rgba(img) => (PixelFormat::Rgba8, img.width(), img.height(), packed_rows(img)),
            ImageSource::Gray(img) => (PixelFormat::Gray8, img.width(), img.height(), packed_rows(img)),
            #[allow(unreachable_patterns)]
            _ => return Err(ErrorKind::UnsupportedImageFormat),
        };
        self.sink
            .image_update(image.handle, x, y, width, height, format, &bytes)
    }

    fn delete_image(&mut self, image: Self::Image, _image_id: ImageId) {
        self.sink.image_delete(image.handle);
    }

    fn screenshot(&mut self) -> Result<ImgVec<RGBA8>, ErrorKind> {
        Err(ErrorKind::UnsupportedImageFormat)
    }
}

impl<S: WireSink> SurfacelessRenderer for WireRenderer<S> {
    fn render_surfaceless(&mut self, images: &mut ImageStore<Self::Image>, verts: &[Vertex], commands: Vec<Command>) {
        self.flush(images, verts, &commands);
    }
}

fn packed_rows<P: bytemuck::Pod>(img: ImgRef<'_, P>) -> Vec<u8> {
    let mut out = Vec::with_capacity(img.width() * img.height() * std::mem::size_of::<P>());
    for row in img.rows() {
        out.extend_from_slice(bytemuck::cast_slice(row));
    }
    out
}

// ---------------------------------------------------------------------------
// Encoding
// ---------------------------------------------------------------------------

fn encode(w: &mut Vec<u32>, images: &ImageStore<WireImage>, commands: &[Command]) {
    let handle = |id: Option<ImageId>| -> u32 { id.and_then(|id| images.get(id)).map_or(NONE, |img| img.handle) };
    w.push(WIRE_VERSION);
    w.push(commands.len() as u32);
    for cmd in commands {
        let kind = match &cmd.cmd_type {
            CommandType::ClipFill => 0,
            CommandType::ClipReset { .. } => 1,
            CommandType::SetRenderTarget(_) => 2,
            CommandType::ClearRect { .. } => 3,
            CommandType::ConvexFill { .. } => 4,
            CommandType::ConcaveFill { .. } => 5,
            CommandType::Stroke { .. } => 6,
            CommandType::StencilStroke { .. } => 7,
            CommandType::Triangles { .. } => 8,
            CommandType::RenderFilteredImage { .. } => 9,
        };
        w.push(kind);
        w.push(u32::from(cmd.clip_active));
        w.push(match cmd.fill_rule {
            FillRule::EvenOdd => 0,
            FillRule::NonZero => 1,
        });
        w.push(handle(cmd.image));
        w.push(handle(cmd.filter_scratch));
        let (glyph_kind, glyph_image) = match cmd.glyph_texture {
            GlyphTexture::None => (0, NONE),
            GlyphTexture::AlphaMask(id) => (1, handle(Some(id))),
            GlyphTexture::ColorTexture(id) => (2, handle(Some(id))),
        };
        w.push(glyph_kind);
        w.push(glyph_image);
        let op = &cmd.composite_operation;
        for f in [op.src_rgb, op.src_alpha, op.dst_rgb, op.dst_alpha] {
            w.push(blend_to_u32(f));
        }
        push_range(w, cmd.triangles_verts);
        w.push(cmd.drawables.len() as u32);
        for d in &cmd.drawables {
            push_range(w, d.fill_verts);
            push_range(w, d.stroke_verts);
        }
        match &cmd.cmd_type {
            CommandType::ClipFill => {}
            CommandType::ClipReset { visible } => w.push(u32::from(*visible)),
            CommandType::SetRenderTarget(target) => match target {
                RenderTarget::Screen => w.extend_from_slice(&[0, NONE]),
                RenderTarget::Image(id) => w.extend_from_slice(&[1, handle(Some(*id))]),
            },
            CommandType::ClearRect { color, keep_clip } => {
                for c in [color.r, color.g, color.b, color.a] {
                    w.push(c.to_bits());
                }
                w.push(u32::from(*keep_clip));
            }
            CommandType::ConvexFill { params } | CommandType::Stroke { params } | CommandType::Triangles { params } => {
                push_params(w, params)
            }
            CommandType::ConcaveFill {
                stencil_params,
                fill_params,
            } => {
                push_params(w, stencil_params);
                push_params(w, fill_params);
            }
            CommandType::StencilStroke { params1, params2 } => {
                push_params(w, params1);
                push_params(w, params2);
            }
            CommandType::RenderFilteredImage { target_image, filter } => {
                w.push(handle(Some(*target_image)));
                push_filter(w, filter);
            }
        }
    }
}

fn push_range(w: &mut Vec<u32>, range: Option<(usize, usize)>) {
    match range {
        Some((first, count)) => w.extend_from_slice(&[first as u32, count as u32]),
        None => w.extend_from_slice(&[NONE, NONE]),
    }
}

fn push_f32s(w: &mut Vec<u32>, values: &[f32]) {
    w.extend(values.iter().map(|v| v.to_bits()));
}

fn push_params(w: &mut Vec<u32>, p: &Params) {
    let start = w.len();
    push_f32s(w, &p.scissor_mat);
    push_f32s(w, &p.paint_mat);
    push_f32s(w, &p.inner_col);
    push_f32s(w, &p.outer_col);
    push_f32s(w, &p.scissor_ext);
    push_f32s(w, &p.scissor_scale);
    push_f32s(
        w,
        &[
            p.scissor_radius,
            p.extent[0],
            p.extent[1],
            p.radius,
            p.feather,
            p.stroke_mult,
            p.stroke_thr,
            p.tex_type,
        ],
    );
    w.push(u32::from(p.shader_type.to_u8()));
    w.push(u32::from(p.glyph_texture_type));
    push_f32s(w, &p.image_blur_filter_direction);
    w.push(p.image_blur_filter_sigma.to_bits());
    push_f32s(w, &p.image_blur_filter_coeff);
    w.push(p.conic_start_angle.to_bits());
    debug_assert_eq!(w.len() - start, PARAMS_WORDS);
}

fn push_filter(w: &mut Vec<u32>, filter: &ImageFilter) {
    match filter {
        ImageFilter::GaussianBlur { sigma } => w.extend_from_slice(&[0, sigma.to_bits()]),
        ImageFilter::ColorMatrix { matrix } => {
            w.push(1);
            push_f32s(w, matrix);
        }
        ImageFilter::Turbulence {
            base_frequency,
            num_octaves,
            seed,
            stitch_tiles,
            kind,
            transform,
        } => {
            w.push(2);
            push_f32s(w, base_frequency);
            w.push(*num_octaves);
            w.push(*seed as u32);
            w.push(u32::from(*stitch_tiles));
            w.push(match kind {
                TurbulenceKind::FractalNoise => 0,
                TurbulenceKind::Turbulence => 1,
            });
            push_f32s(w, &transform.0);
        }
        ImageFilter::LinearRgbToSrgb => w.push(3),
        ImageFilter::SrgbToLinearRgb => w.push(4),
    }
}

const BLEND_FACTORS: [BlendFactor; 11] = [
    BlendFactor::Zero,
    BlendFactor::One,
    BlendFactor::SrcColor,
    BlendFactor::OneMinusSrcColor,
    BlendFactor::DstColor,
    BlendFactor::OneMinusDstColor,
    BlendFactor::SrcAlpha,
    BlendFactor::OneMinusSrcAlpha,
    BlendFactor::DstAlpha,
    BlendFactor::OneMinusDstAlpha,
    BlendFactor::SrcAlphaSaturate,
];

fn blend_to_u32(f: BlendFactor) -> u32 {
    BLEND_FACTORS.iter().position(|&b| b == f).unwrap_or(0) as u32
}

// ---------------------------------------------------------------------------
// Decoding and replay
// ---------------------------------------------------------------------------

/// Owns a real renderer and its image store, allocates images for a
/// [`WireRenderer`] on the other side, and renders its encoded flushes.
#[derive(Debug)]
pub struct WireReplayer<R: Renderer> {
    renderer: R,
    images: ImageStore<R::Image>,
    handles: Vec<Option<ImageId>>,
}

impl<R: Renderer> WireReplayer<R> {
    /// Creates a replayer that renders with `renderer`.
    pub fn new(renderer: R) -> Self {
        Self {
            renderer,
            images: ImageStore::new(),
            handles: Vec::new(),
        }
    }

    /// The renderer.
    pub fn renderer(&self) -> &R {
        &self.renderer
    }

    /// The renderer, mutably.
    pub fn renderer_mut(&mut self) -> &mut R {
        &mut self.renderer
    }

    /// Forwards a [`WireSink::set_size`].
    pub fn set_size(&mut self, width: u32, height: u32, dpi: f32) {
        self.renderer.set_size(width, height, dpi);
    }

    /// Allocates an image in the replayer's store; the returned handle is
    /// what the [`WireRenderer`] side refers to it by.
    pub fn image_alloc(&mut self, info: ImageInfo) -> Result<u32, ErrorKind> {
        let id = self.images.alloc(&mut self.renderer, info)?;
        let handle = match self.handles.iter().position(Option::is_none) {
            Some(free) => {
                self.handles[free] = Some(id);
                free
            }
            None => {
                self.handles.push(Some(id));
                self.handles.len() - 1
            }
        };
        Ok(handle as u32)
    }

    /// Applies a [`WireSink::image_update`].
    #[allow(clippy::too_many_arguments)]
    pub fn image_update(
        &mut self,
        handle: u32,
        x: usize,
        y: usize,
        width: usize,
        height: usize,
        format: PixelFormat,
        data: &[u8],
    ) -> Result<(), ErrorKind> {
        let id = self.id(handle)?;
        let bpp = match format {
            PixelFormat::Rgb8 => 3,
            PixelFormat::Rgba8 => 4,
            PixelFormat::Gray8 => 1,
        };
        if data.len() != width * height * bpp {
            return Err(ErrorKind::ImageUpdateOutOfBounds);
        }
        let source = match format {
            PixelFormat::Rgb8 => ImageSource::Rgb(ImgRef::new(bytemuck::cast_slice::<u8, RGB8>(data), width, height)),
            PixelFormat::Rgba8 => {
                ImageSource::Rgba(ImgRef::new(bytemuck::cast_slice::<u8, RGBA8>(data), width, height))
            }
            PixelFormat::Gray8 => {
                ImageSource::Gray(ImgRef::new(bytemuck::cast_slice::<u8, Gray<u8>>(data), width, height))
            }
        };
        self.images.update(&mut self.renderer, id, source, x, y)
    }

    /// Applies a [`WireSink::image_delete`].
    pub fn image_delete(&mut self, handle: u32) {
        if let Some(slot) = self.handles.get_mut(handle as usize) {
            if let Some(id) = slot.take() {
                self.images.remove(&mut self.renderer, id);
            }
        }
    }

    /// Decodes an encoded flush into commands on this replayer's images.
    pub fn decode(&self, words: &[u32]) -> Result<Vec<Command>, ErrorKind> {
        let mut r = Reader { words, pos: 0 };
        if r.u()? != WIRE_VERSION {
            return Err(wire_error("wire version mismatch"));
        }
        let n = r.u()? as usize;
        let mut commands = Vec::with_capacity(n.min(words.len()));
        for _ in 0..n {
            let kind = r.u()?;
            let clip_active = r.u()? != 0;
            let fill_rule = match r.u()? {
                0 => FillRule::EvenOdd,
                1 => FillRule::NonZero,
                _ => return Err(wire_error("bad fill rule")),
            };
            let image = self.opt_id(r.u()?)?;
            let filter_scratch = self.opt_id(r.u()?)?;
            let glyph_kind = r.u()?;
            let glyph_image = r.u()?;
            let glyph_texture = match glyph_kind {
                0 => GlyphTexture::None,
                1 => GlyphTexture::AlphaMask(self.id(glyph_image)?),
                2 => GlyphTexture::ColorTexture(self.id(glyph_image)?),
                _ => return Err(wire_error("bad glyph texture kind")),
            };
            let composite_operation = CompositeOperationState {
                src_rgb: r.blend()?,
                src_alpha: r.blend()?,
                dst_rgb: r.blend()?,
                dst_alpha: r.blend()?,
            };
            let triangles_verts = r.range()?;
            let n_drawables = r.u()? as usize;
            let mut drawables = Vec::with_capacity(n_drawables.min(words.len()));
            for _ in 0..n_drawables {
                drawables.push(Drawable {
                    fill_verts: r.range()?,
                    stroke_verts: r.range()?,
                });
            }
            let cmd_type = match kind {
                0 => CommandType::ClipFill,
                1 => CommandType::ClipReset { visible: r.u()? != 0 },
                2 => {
                    let target = r.u()?;
                    let handle = r.u()?;
                    CommandType::SetRenderTarget(match target {
                        0 => RenderTarget::Screen,
                        1 => RenderTarget::Image(self.id(handle)?),
                        _ => return Err(wire_error("bad render target")),
                    })
                }
                3 => CommandType::ClearRect {
                    color: Color::rgbaf(r.f()?, r.f()?, r.f()?, r.f()?),
                    keep_clip: r.u()? != 0,
                },
                4 => CommandType::ConvexFill { params: r.params()? },
                5 => CommandType::ConcaveFill {
                    stencil_params: r.params()?,
                    fill_params: r.params()?,
                },
                6 => CommandType::Stroke { params: r.params()? },
                7 => CommandType::StencilStroke {
                    params1: r.params()?,
                    params2: r.params()?,
                },
                8 => CommandType::Triangles { params: r.params()? },
                9 => CommandType::RenderFilteredImage {
                    target_image: self.id(r.u()?)?,
                    filter: r.filter()?,
                },
                _ => return Err(wire_error("bad command kind")),
            };
            commands.push(Command {
                cmd_type,
                clip_active,
                drawables,
                triangles_verts,
                image,
                filter_scratch,
                glyph_texture,
                fill_rule,
                composite_operation,
            });
        }
        if r.pos != words.len() {
            return Err(wire_error("trailing words"));
        }
        Ok(commands)
    }

    /// Decodes an encoded flush and renders it, with `verts`, to `output`.
    pub fn render(
        &mut self,
        output: impl Into<R::RenderOutput>,
        verts: &[Vertex],
        words: &[u32],
    ) -> Result<R::CommandBuffer, ErrorKind> {
        let commands = self.decode(words)?;
        Ok(self.renderer.render(output, &mut self.images, verts, commands))
    }

    fn id(&self, handle: u32) -> Result<ImageId, ErrorKind> {
        self.handles
            .get(handle as usize)
            .copied()
            .flatten()
            .ok_or(ErrorKind::ImageIdNotFound)
    }

    fn opt_id(&self, handle: u32) -> Result<Option<ImageId>, ErrorKind> {
        if handle == NONE {
            Ok(None)
        } else {
            self.id(handle).map(Some)
        }
    }
}

impl<R: Renderer> Drop for WireReplayer<R> {
    fn drop(&mut self) {
        self.images.clear(&mut self.renderer);
    }
}

fn wire_error(what: &str) -> ErrorKind {
    ErrorKind::GeneralError(format!("femtovg wire stream: {what}"))
}

struct Reader<'a> {
    words: &'a [u32],
    pos: usize,
}

impl Reader<'_> {
    fn u(&mut self) -> Result<u32, ErrorKind> {
        let v = *self.words.get(self.pos).ok_or_else(|| wire_error("truncated"))?;
        self.pos += 1;
        Ok(v)
    }

    fn f(&mut self) -> Result<f32, ErrorKind> {
        self.u().map(f32::from_bits)
    }

    fn fs<const N: usize>(&mut self) -> Result<[f32; N], ErrorKind> {
        let mut out = [0.0; N];
        for v in &mut out {
            *v = self.f()?;
        }
        Ok(out)
    }

    fn range(&mut self) -> Result<Option<(usize, usize)>, ErrorKind> {
        let first = self.u()?;
        let count = self.u()?;
        Ok((first != NONE).then_some((first as usize, count as usize)))
    }

    fn blend(&mut self) -> Result<BlendFactor, ErrorKind> {
        BLEND_FACTORS
            .get(self.u()? as usize)
            .copied()
            .ok_or_else(|| wire_error("bad blend factor"))
    }

    fn params(&mut self) -> Result<Params, ErrorKind> {
        let start = self.pos;
        let scissor_mat = self.fs::<12>()?;
        let paint_mat = self.fs::<12>()?;
        let inner_col = self.fs::<4>()?;
        let outer_col = self.fs::<4>()?;
        let scissor_ext = self.fs::<2>()?;
        let scissor_scale = self.fs::<2>()?;
        let [scissor_radius, extent0, extent1, radius, feather, stroke_mult, stroke_thr, tex_type] = self.fs::<8>()?;
        let shader_type = shader_type_from_u32(self.u()?)?;
        let glyph_texture_type = u8::try_from(self.u()?).map_err(|_| wire_error("bad glyph texture type"))?;
        let image_blur_filter_direction = self.fs::<2>()?;
        let image_blur_filter_sigma = self.f()?;
        let image_blur_filter_coeff = self.fs::<3>()?;
        let conic_start_angle = self.f()?;
        debug_assert_eq!(self.pos - start, PARAMS_WORDS);
        Ok(Params {
            scissor_mat,
            paint_mat,
            inner_col,
            outer_col,
            scissor_ext,
            scissor_scale,
            scissor_radius,
            extent: [extent0, extent1],
            radius,
            feather,
            stroke_mult,
            stroke_thr,
            tex_type,
            shader_type,
            glyph_texture_type,
            image_blur_filter_direction,
            image_blur_filter_sigma,
            image_blur_filter_coeff,
            conic_start_angle,
        })
    }

    fn filter(&mut self) -> Result<ImageFilter, ErrorKind> {
        Ok(match self.u()? {
            0 => ImageFilter::GaussianBlur { sigma: self.f()? },
            1 => ImageFilter::ColorMatrix {
                matrix: self.fs::<20>()?,
            },
            2 => ImageFilter::Turbulence {
                base_frequency: self.fs::<2>()?,
                num_octaves: self.u()?,
                seed: self.u()? as i32,
                stitch_tiles: self.u()? != 0,
                kind: match self.u()? {
                    0 => TurbulenceKind::FractalNoise,
                    1 => TurbulenceKind::Turbulence,
                    _ => return Err(wire_error("bad turbulence kind")),
                },
                transform: Transform2D(self.fs::<6>()?),
            },
            3 => ImageFilter::LinearRgbToSrgb,
            4 => ImageFilter::SrgbToLinearRgb,
            _ => return Err(wire_error("bad image filter")),
        })
    }
}

fn shader_type_from_u32(v: u32) -> Result<ShaderType, ErrorKind> {
    const ALL: [ShaderType; 15] = [
        ShaderType::FillGradient,
        ShaderType::FillImage,
        ShaderType::Stencil,
        ShaderType::FillImageGradient,
        ShaderType::FilterImage,
        ShaderType::FillColor,
        ShaderType::TextureCopyUnclipped,
        ShaderType::FillColorUnclipped,
        ShaderType::FillGradientConic,
        ShaderType::FillImageGradientConic,
        ShaderType::FilterImageColorMatrix,
        ShaderType::FillGradientTwoPointRadial,
        ShaderType::FillImageGradientTwoPointRadial,
        ShaderType::FilterImageTurbulence,
        ShaderType::FilterImageTransfer,
    ];
    let t = *ALL.get(v as usize).ok_or_else(|| wire_error("bad shader type"))?;
    debug_assert_eq!(u32::from(t.to_u8()), v);
    Ok(t)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{renderer::Void, Canvas, Paint, Path};

    /// Records what a guest would send, allocating handles through a
    /// replayer the way a host does, so the round trip runs in one process.
    struct Recorder {
        replay: WireReplayer<Void>,
        frames: Vec<(Vec<Vertex>, Vec<u32>)>,
    }

    impl WireSink for Recorder {
        fn set_size(&mut self, width: u32, height: u32, dpi: f32) {
            self.replay.set_size(width, height, dpi);
        }
        fn image_alloc(&mut self, info: ImageInfo) -> Result<u32, ErrorKind> {
            self.replay.image_alloc(info)
        }
        fn image_update(
            &mut self,
            handle: u32,
            x: usize,
            y: usize,
            width: usize,
            height: usize,
            format: PixelFormat,
            data: &[u8],
        ) -> Result<(), ErrorKind> {
            self.replay.image_update(handle, x, y, width, height, format, data)
        }
        fn image_delete(&mut self, handle: u32) {
            self.replay.image_delete(handle);
        }
        fn render(&mut self, verts: &[Vertex], commands: &[u32]) {
            self.frames.push((verts.to_vec(), commands.to_vec()));
        }
    }

    #[test]
    fn round_trip_preserves_every_command() {
        let rec = Recorder {
            replay: WireReplayer::new(Void),
            frames: Vec::new(),
        };
        let mut canvas = Canvas::new(WireRenderer::new(rec)).unwrap();
        canvas.set_size(256, 256, 1.0);
        canvas.clear_rect(0, 0, 256, 256, Color::rgbf(0.1, 0.2, 0.3));

        let mut concave = Path::new();
        concave.move_to(10.0, 10.0);
        concave.line_to(200.0, 40.0);
        concave.line_to(40.0, 200.0);
        concave.line_to(120.0, 30.0);
        concave.close();
        canvas.fill_path(&concave, &Paint::color(Color::rgb(200, 30, 30)));
        let mut circle = Path::new();
        circle.circle(128.0, 128.0, 40.0);
        let gradient = Paint::linear_gradient(0.0, 0.0, 256.0, 256.0, Color::white(), Color::black());
        canvas.fill_path(&circle, &gradient);
        canvas.stroke_path(
            &concave,
            &Paint::color(Color::rgba(0, 0, 255, 128)).with_line_width(3.0),
        );

        canvas.save();
        let mut clip = Path::new();
        clip.rect(20.0, 20.0, 100.0, 100.0);
        canvas.clip_path(&clip, FillRule::EvenOdd);
        canvas.fill_path(&circle, &Paint::color(Color::rgb(0, 255, 0)));
        canvas.restore();

        let pixels = [RGBA8::new(1, 2, 3, 4); 16];
        let image = canvas
            .create_image(ImgRef::new(&pixels[..], 4, 4), crate::ImageFlags::empty())
            .unwrap();
        let mut rect = Path::new();
        rect.rect(0.0, 0.0, 64.0, 64.0);
        canvas.fill_path(&rect, &Paint::image(image, 0.0, 0.0, 64.0, 64.0, 0.0, 1.0));
        canvas.flush();

        let rec = canvas.renderer.sink_mut();
        assert_eq!(rec.frames.len(), 1);
        let (verts, words) = &rec.frames[0];
        assert!(!verts.is_empty());
        let decoded = rec.replay.decode(words).unwrap();
        let kinds: std::collections::HashSet<_> = decoded.iter().map(|c| std::mem::discriminant(&c.cmd_type)).collect();
        assert!(kinds.len() >= 5, "expected a mixed command list, got {decoded:?}");
        // Re-encoding the decoded commands under the same handle numbers gives
        // back the identical word stream, so no field was lost or altered.
        let mut shim = Shim { next: 0 };
        let mut store: ImageStore<WireImage> = ImageStore::new();
        let ids: Vec<ImageId> = (0..rec.replay.handles.len())
            .map(|_| {
                store
                    .alloc(
                        &mut shim,
                        ImageInfo::new(crate::ImageFlags::empty(), 1, 1, PixelFormat::Rgba8),
                    )
                    .unwrap()
            })
            .collect();
        let remapped: Vec<Command> = decoded.into_iter().map(|c| remap(c, &rec.replay, &ids)).collect();
        let mut reencoded = Vec::new();
        encode(&mut reencoded, &store, &remapped);
        assert_eq!(&reencoded, words);
    }

    struct Shim {
        next: u32,
    }

    impl Renderer for Shim {
        type Image = WireImage;
        type NativeTexture = ();
        type ExternalTexture = ();
        type RenderOutput = ();
        type CommandBuffer = ();
        fn set_size(&mut self, _: u32, _: u32, _: f32) {}
        fn render(&mut self, _: impl Into<()>, _: &mut ImageStore<WireImage>, _: &[Vertex], _: Vec<Command>) {}
        fn alloc_image(&mut self, info: ImageInfo) -> Result<WireImage, ErrorKind> {
            self.next += 1;
            Ok(WireImage {
                handle: self.next - 1,
                info,
            })
        }
        fn create_image_from_native_texture(&mut self, _: (), _: ImageInfo) -> Result<WireImage, ErrorKind> {
            Err(ErrorKind::UnsupportedImageFormat)
        }
        fn create_image_from_external_texture(&mut self, _: (), _: ImageInfo) -> Result<WireImage, ErrorKind> {
            Err(ErrorKind::UnsupportedImageFormat)
        }
        fn update_image(&mut self, _: &mut WireImage, _: ImageSource, _: usize, _: usize) -> Result<(), ErrorKind> {
            Ok(())
        }
        fn delete_image(&mut self, _: WireImage, _: ImageId) {}
        fn screenshot(&mut self) -> Result<ImgVec<RGBA8>, ErrorKind> {
            Err(ErrorKind::UnsupportedImageFormat)
        }
    }

    /// Maps the replayer's ImageIds back to the re-encoding store's ids with
    /// the same handle numbers.
    fn remap(mut c: Command, replay: &WireReplayer<Void>, ids: &[ImageId]) -> Command {
        let map = |id: ImageId| -> ImageId {
            let handle = replay.handles.iter().position(|h| *h == Some(id)).unwrap();
            ids[handle]
        };
        c.image = c.image.map(map);
        c.filter_scratch = c.filter_scratch.map(map);
        c.glyph_texture = match c.glyph_texture {
            GlyphTexture::None => GlyphTexture::None,
            GlyphTexture::AlphaMask(id) => GlyphTexture::AlphaMask(map(id)),
            GlyphTexture::ColorTexture(id) => GlyphTexture::ColorTexture(map(id)),
        };
        c.cmd_type = match c.cmd_type {
            CommandType::SetRenderTarget(RenderTarget::Image(id)) => {
                CommandType::SetRenderTarget(RenderTarget::Image(map(id)))
            }
            CommandType::RenderFilteredImage { target_image, filter } => CommandType::RenderFilteredImage {
                target_image: map(target_image),
                filter,
            },
            other => other,
        };
        c
    }
}
