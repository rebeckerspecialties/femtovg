#![deny(missing_docs)]
#![warn(missing_debug_implementations)]
#![cfg_attr(docsrs, feature(doc_cfg))]

/*!
 * The femtovg API is (like [NanoVG](https://github.com/memononen/nanovg))
 * loosely modeled on the
 * [HTML5 Canvas API](https://bucephalus.org/text/CanvasHandbook/CanvasHandbook.html).
 *
 * The coordinate system’s origin is the top-left corner,
 * with positive X rightwards, positive Y downwards.
 */

/*
TODO:
    - Tests
*/

#[cfg(feature = "serde")]
#[macro_use]
extern crate serde;

#[cfg(feature = "textlayout")]
use std::ops::Range;
use std::{cell::RefCell, path::Path as FilePath, rc::Rc};

use imgref::ImgVec;
use rgb::RGBA8;

mod text;

mod error;
pub use error::ErrorKind;

pub use text::{
    Align, Atlas, Baseline, DrawCommand, FontId, FontMetrics, GlyphDrawCommands, Quad, RenderMode, VariationAxisInfo,
};

pub use text::TextContext;
#[cfg(feature = "textlayout")]
pub use text::TextMetrics;

use text::{GlyphAtlas, TextContextImpl};

mod image;
use crate::image::ImageStore;
pub use crate::image::{ImageFilter, ImageFlags, ImageId, ImageInfo, ImageSource, PixelFormat};

mod color;
pub use color::Color;

pub mod renderer;
pub use renderer::{RenderTarget, Renderer};

use renderer::{Command, CommandType, Drawable, Params, ShaderType, SurfacelessRenderer, Vertex};

pub(crate) mod geometry;
pub use geometry::Transform2D;
use geometry::*;

mod paint;
pub use paint::Paint;
pub use paint::TextDecoration;
use paint::{GlyphTexture, PaintFlavor, StrokeSettings};

mod path;
use path::Convexity;
pub use path::{Path, PathIter, Solidity, Verb};

mod gradient_store;
use gradient_store::GradientStore;

/// Determines the fill rule used when filling paths.
///
/// The fill rule defines how the interior of a shape is determined.
#[derive(Copy, Clone, Debug, Eq, PartialEq, Default)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum FillRule {
    /// The interior is determined using the even-odd rule.
    /// A point is considered inside the shape if it intersects the shape's outline an odd number of times.
    EvenOdd,
    /// The interior is determined using the non-zero winding rule (default).
    /// A point is considered inside the shape if it intersects the shape's outline a non-zero number of times,
    /// considering the direction of each intersection.
    #[default]
    NonZero,
}

/// Blend factors.
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Hash)]
pub enum BlendFactor {
    /// Not all
    Zero,
    /// All use
    One,
    /// Using the source color
    SrcColor,
    /// Minus the source color
    OneMinusSrcColor,
    /// Using the target color
    DstColor,
    /// Minus the target color
    OneMinusDstColor,
    /// Using the source alpha
    SrcAlpha,
    /// Minus the source alpha
    OneMinusSrcAlpha,
    /// Using the target alpha
    DstAlpha,
    /// Minus the target alpha
    OneMinusDstAlpha,
    /// Scale color by minimum of source alpha and destination alpha
    SrcAlphaSaturate,
}

/// Predefined composite oprations.
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Hash)]
pub enum CompositeOperation {
    /// Displays the source over the destination.
    SourceOver,
    /// Displays the source in the destination, i.e. only the part of the source inside the destination is shown and the destination is transparent.
    SourceIn,
    /// Only displays the part of the source that is outside the destination, which is made transparent.
    SourceOut,
    /// Displays the source on top of the destination. The part of the source outside the destination is not shown.
    Atop,
    /// Displays the destination over the source.
    DestinationOver,
    /// Only displays the part of the destination that is inside the source, which is made transparent.
    DestinationIn,
    /// Only displays the part of the destination that is outside the source, which is made transparent.
    DestinationOut,
    /// Displays the destination on top of the source. The part of the destination that is outside the source is not shown.
    DestinationAtop,
    /// Displays the source together with the destination, the overlapping area is rendered lighter.
    Lighter,
    /// Ignores the destination and just displays the source.
    Copy,
    /// Only the areas that exclusively belong either to the destination or the source are displayed. Overlapping parts are ignored.
    Xor,
}

/// Determines how a new ("source") data is displayed against an existing ("destination") data.
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Hash)]
pub struct CompositeOperationState {
    src_rgb: BlendFactor,
    src_alpha: BlendFactor,
    dst_rgb: BlendFactor,
    dst_alpha: BlendFactor,
}

impl CompositeOperationState {
    /// Creates a new `CompositeOperationState` from the provided `CompositeOperation`
    pub fn new(op: CompositeOperation) -> Self {
        let (sfactor, dfactor) = match op {
            CompositeOperation::SourceOver => (BlendFactor::One, BlendFactor::OneMinusSrcAlpha),
            CompositeOperation::SourceIn => (BlendFactor::DstAlpha, BlendFactor::Zero),
            CompositeOperation::SourceOut => (BlendFactor::OneMinusDstAlpha, BlendFactor::Zero),
            CompositeOperation::Atop => (BlendFactor::DstAlpha, BlendFactor::OneMinusSrcAlpha),
            CompositeOperation::DestinationOver => (BlendFactor::OneMinusDstAlpha, BlendFactor::One),
            CompositeOperation::DestinationIn => (BlendFactor::Zero, BlendFactor::SrcAlpha),
            CompositeOperation::DestinationOut => (BlendFactor::Zero, BlendFactor::OneMinusSrcAlpha),
            CompositeOperation::DestinationAtop => (BlendFactor::OneMinusDstAlpha, BlendFactor::SrcAlpha),
            CompositeOperation::Lighter => (BlendFactor::One, BlendFactor::One),
            CompositeOperation::Copy => (BlendFactor::One, BlendFactor::Zero),
            CompositeOperation::Xor => (BlendFactor::OneMinusDstAlpha, BlendFactor::OneMinusSrcAlpha),
        };

        Self {
            src_rgb: sfactor,
            src_alpha: sfactor,
            dst_rgb: dfactor,
            dst_alpha: dfactor,
        }
    }

    /// Creates a new `CompositeOperationState` with source and destination blend factors.
    pub fn with_blend_factors(src_factor: BlendFactor, dst_factor: BlendFactor) -> Self {
        Self {
            src_rgb: src_factor,
            src_alpha: src_factor,
            dst_rgb: dst_factor,
            dst_alpha: dst_factor,
        }
    }
}

impl Default for CompositeOperationState {
    fn default() -> Self {
        Self::new(CompositeOperation::SourceOver)
    }
}

#[derive(Copy, Clone, Debug, Default)]
struct Scissor {
    transform: Transform2D,
    extent: Option<[f32; 2]>,
}

impl Scissor {
    /// Returns the bounding rect if the scissor clip if it's an untransformed rectangular clip
    fn as_rect(&self, canvas_width: f32, canvas_height: f32) -> Option<Rect> {
        let Some(extent) = self.extent else {
            return Some(Rect::new(0., 0., canvas_width, canvas_height));
        };

        let Transform2D([a, b, c, d, x, y]) = self.transform;

        // Abort if we're skewing (usually doesn't happen)
        if b != 0.0 || c != 0.0 {
            return None;
        }

        // Abort if we're scaling
        if a != 1.0 || d != 1.0 {
            return None;
        }

        let half_width = extent[0];
        let half_height = extent[1];
        Some(Rect::new(
            x - half_width,
            y - half_height,
            half_width * 2.0,
            half_height * 2.0,
        ))
    }
}

/// Determines the shape used to draw the end points of lines.
///
/// The default value is `Butt`.
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Default)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum LineCap {
    /// The ends of lines are squared off at the endpoints.
    #[default]
    Butt,
    /// The ends of lines are rounded.
    Round,
    /// The ends of lines are squared off by adding a box with an equal
    /// width and half the height of the line's thickness.
    Square,
}

/// Determines the shape used to join two line segments where they meet.
///
/// The default value is `Miter`.
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Default)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum LineJoin {
    /// Connected segments are joined by extending their outside edges to
    /// connect at a single point, with the effect of filling an additional
    /// lozenge-shaped area. This setting is affected by the miterLimit property.
    #[default]
    Miter,
    /// Rounds off the corners of a shape by filling an additional sector
    /// of disc centered at the common endpoint of connected segments.
    /// The radius for these rounded corners is equal to the line width.
    Round,
    /// Fills an additional triangular area between the common endpoint
    /// of connected segments, and the separate outside rectangular
    /// corners of each segment.
    Bevel,
}

#[derive(Copy, Clone, Debug)]
struct State {
    composite_operation: CompositeOperationState,
    transform: Transform2D,
    scissor: Scissor,
    alpha: f32,
}

impl Default for State {
    fn default() -> Self {
        Self {
            composite_operation: CompositeOperationState::default(),
            transform: Transform2D::identity(),
            scissor: Scissor::default(),
            alpha: 1.0,
        }
    }
}

/// Main 2D drawing context.
#[derive(Debug)]
pub struct Canvas<T: Renderer> {
    width: u32,
    height: u32,
    renderer: T,
    text_context: Rc<RefCell<TextContextImpl>>,
    glyph_atlas: Rc<GlyphAtlas>,
    // Glyph atlas used for direct rendering of color glyphs, dropped after flush()
    ephemeral_glyph_atlas: Option<Rc<GlyphAtlas>>,
    current_render_target: RenderTarget,
    state_stack: Vec<State>,
    commands: Vec<Command>,
    verts: Vec<Vertex>,
    images: ImageStore<T::Image>,
    fringe_width: f32,
    device_px_ratio: f32,
    tess_tol: f32,
    dist_tol: f32,
    gradients: GradientStore,
}

/// Returns the shared baseline of a shaped horizontal run, in shaping space, or
/// `None` if the run has no drawable glyph.
///
/// `layout` positions each glyph as
/// `glyph.y = (cursor_y + alignment_offset).round() + glyph.offset_y`, so every
/// glyph shares the same `(cursor_y + alignment_offset).round()` baseline and the
/// per-glyph term is `glyph.offset_y` (the GPOS y-offset). Recovering the baseline
/// as `glyph.y - glyph.offset_y` is what keeps text decorations anchored to the
/// run baseline even when the first drawable glyph carries a non-zero offset (e.g.
/// text starting with a combining mark), instead of riding that mark up or down.
#[cfg(feature = "textlayout")]
fn run_baseline(glyphs: &[text::ShapedGlyph]) -> Option<f32> {
    glyphs
        .iter()
        .find(|shaped_glyph| !shaped_glyph.c.is_control())
        .map(|shaped_glyph| shaped_glyph.y - shaped_glyph.offset_y)
}

impl<T> Canvas<T>
where
    T: Renderer,
{
    /// Creates a new canvas.
    pub fn new(renderer: T) -> Result<Self, ErrorKind> {
        let text_context = Rc::new(RefCell::new(TextContextImpl::default()));
        let glyph_atlas = Rc::new(GlyphAtlas::new(&text_context));
        let mut canvas = Self {
            width: 0,
            height: 0,
            renderer,
            text_context,
            glyph_atlas,
            ephemeral_glyph_atlas: None,
            current_render_target: RenderTarget::Screen,
            state_stack: Vec::new(),
            commands: Vec::new(),
            verts: Vec::new(),
            images: ImageStore::new(),
            fringe_width: 1.0,
            device_px_ratio: 1.0,
            tess_tol: 0.25,
            dist_tol: 0.01,
            gradients: GradientStore::new(),
        };

        canvas.save();

        Ok(canvas)
    }

    /// Creates a new canvas with the specified renderer and using the fonts registered with the
    /// provided [`TextContext`]. Note that the context is explicitly shared, so that any fonts
    /// registered with a clone of this context will also be visible to this canvas.
    pub fn new_with_text_context(renderer: T, text_context: TextContext) -> Result<Self, ErrorKind> {
        let glyph_atlas = Rc::new(GlyphAtlas::new(&text_context.0));
        let mut canvas = Self {
            width: 0,
            height: 0,
            renderer,
            text_context: text_context.0,
            glyph_atlas,
            ephemeral_glyph_atlas: None,
            current_render_target: RenderTarget::Screen,
            state_stack: Vec::new(),
            commands: Vec::new(),
            verts: Vec::new(),
            images: ImageStore::new(),
            fringe_width: 1.0,
            device_px_ratio: 1.0,
            tess_tol: 0.25,
            dist_tol: 0.01,
            gradients: GradientStore::new(),
        };

        canvas.save();

        Ok(canvas)
    }

    /// Sets the size of the default framebuffer (screen size)
    pub fn set_size(&mut self, width: u32, height: u32, dpi: f32) {
        self.width = width;
        self.height = height;
        self.fringe_width = 1.0 / dpi;
        self.tess_tol = 0.25 / dpi;
        self.dist_tol = 0.01 / dpi;
        self.device_px_ratio = dpi;

        self.renderer.set_size(width, height, dpi);

        self.append_cmd(Command::new(CommandType::SetRenderTarget(RenderTarget::Screen)));
    }

    /// Clears the rectangle area defined by left upper corner (x,y), width and height with the provided color.
    pub fn clear_rect(&mut self, x: u32, y: u32, width: u32, height: u32, color: Color) {
        let mut cmd = Command::new(CommandType::ClearRect { color });
        cmd.composite_operation = self.state().composite_operation;

        let x0 = x as f32;
        let y0 = y as f32;
        let x1 = x0 + width as f32;
        let y1 = y0 + height as f32;

        let (p0, p1) = (x0, y0);
        let (p2, p3) = (x1, y0);
        let (p4, p5) = (x1, y1);
        let (p6, p7) = (x0, y1);

        let verts = [
            Vertex::new(p0, p1, 0.0, 0.0),
            Vertex::new(p4, p5, 0.0, 0.0),
            Vertex::new(p2, p3, 0.0, 0.0),
            Vertex::new(p0, p1, 0.0, 0.0),
            Vertex::new(p6, p7, 0.0, 0.0),
            Vertex::new(p4, p5, 0.0, 0.0),
        ];

        cmd.triangles_verts = Some((self.verts.len(), verts.len()));
        self.append_cmd(cmd);

        self.verts.extend_from_slice(&verts);
    }

    /// Returns the width of the current render target.
    pub fn width(&self) -> u32 {
        match self.current_render_target {
            RenderTarget::Image(id) => self.image_info(id).map(|info| info.width() as u32).unwrap_or(0),
            RenderTarget::Screen => self.width,
        }
    }

    /// Returns the height of the current render target.
    pub fn height(&self) -> u32 {
        match self.current_render_target {
            RenderTarget::Image(id) => self.image_info(id).map(|info| info.height() as u32).unwrap_or(0),
            RenderTarget::Screen => self.height,
        }
    }

    /// Tells the renderer to execute all drawing commands and clears the current internal state
    ///
    /// Call this at the end of each frame.
    pub fn flush_to_output(&mut self, output: impl Into<T::RenderOutput>) -> T::CommandBuffer {
        let command_buffer = self.renderer.render(
            output,
            &mut self.images,
            &self.verts,
            std::mem::take(&mut self.commands),
        );
        self.verts.clear();
        self.gradients
            .release_old_gradients(&mut self.images, &mut self.renderer);
        if let Some(atlas) = self.ephemeral_glyph_atlas.take() {
            atlas.clear(self);
        }
        command_buffer
    }

    /// Returns a screenshot of the current canvas.
    pub fn screenshot(&mut self) -> Result<ImgVec<RGBA8>, ErrorKind> {
        self.renderer.screenshot()
    }

    // State Handling

    /// Pushes and saves the current render state into a state stack.
    ///
    /// A matching `restore()` must be used to restore the state.
    pub fn save(&mut self) {
        let state = self.state_stack.last().map_or_else(State::default, |state| *state);

        self.state_stack.push(state);
    }

    /// Restores the previous render state
    ///
    /// Restoring the initial/first state will just reset it to the defaults
    pub fn restore(&mut self) {
        if self.state_stack.len() > 1 {
            self.state_stack.pop();
        } else {
            self.reset();
        }
    }

    /// Resets current state to default values. Does not affect the state stack.
    pub fn reset(&mut self) {
        *self.state_mut() = State::default();
    }

    /// Saves the current state before calling the callback and restores it afterwards
    ///
    /// This is less error prone than remembering to match `save()` -> `restore()` calls
    pub fn save_with(&mut self, mut callback: impl FnMut(&mut Self)) {
        self.save();

        callback(self);

        self.restore();
    }

    // Render styles

    /// Sets the transparency applied to all rendered shapes.
    ///
    /// Already transparent paths will get proportionally more transparent as well.
    pub fn set_global_alpha(&mut self, alpha: f32) {
        self.state_mut().alpha = alpha;
    }

    /// Sets the composite operation.
    pub fn global_composite_operation(&mut self, op: CompositeOperation) {
        self.state_mut().composite_operation = CompositeOperationState::new(op);
    }

    /// Sets the composite operation with custom pixel arithmetic.
    pub fn global_composite_blend_func(&mut self, src_factor: BlendFactor, dst_factor: BlendFactor) {
        self.global_composite_blend_func_separate(src_factor, dst_factor, src_factor, dst_factor);
    }

    /// Sets the composite operation with custom pixel arithmetic for RGB and alpha components separately.
    pub fn global_composite_blend_func_separate(
        &mut self,
        src_rgb: BlendFactor,
        dst_rgb: BlendFactor,
        src_alpha: BlendFactor,
        dst_alpha: BlendFactor,
    ) {
        self.state_mut().composite_operation = CompositeOperationState {
            src_rgb,
            src_alpha,
            dst_rgb,
            dst_alpha,
        }
    }

    /// Sets a new render target. All drawing operations after this call will happen on the provided render target
    pub fn set_render_target(&mut self, target: RenderTarget) {
        if self.current_render_target != target {
            self.append_cmd(Command::new(CommandType::SetRenderTarget(target)));
            self.current_render_target = target;
        }
    }

    fn append_cmd(&mut self, cmd: Command) {
        self.commands.push(cmd);
    }

    // Images

    /// Allocates an empty image with the provided domensions and format.
    pub fn create_image_empty(
        &mut self,
        width: usize,
        height: usize,
        format: PixelFormat,
        flags: ImageFlags,
    ) -> Result<ImageId, ErrorKind> {
        let info = ImageInfo::new(flags, width, height, format);

        self.images.alloc(&mut self.renderer, info)
    }

    /// Allocates an image that wraps the given backend-specific texture.
    /// Use this function to import native textures into the rendering of a scene
    /// with femtovg.
    ///
    /// It is necessary to call `[Self::delete_image`] to free femtovg specific
    /// book-keeping data structures, the underlying backend-specific texture memory
    /// will not be freed. It is the caller's responsible to delete it.
    pub fn create_image_from_native_texture(
        &mut self,
        texture: T::NativeTexture,
        info: ImageInfo,
    ) -> Result<ImageId, ErrorKind> {
        self.images.register_native_texture(&mut self.renderer, texture, info)
    }

    /// Allocates an image that wraps the given backend-specific texture.
    /// Use this function to import native textures marked as external into the
    /// rendering of a scene with femtovg.
    ///
    /// It is necessary to call `[Self::delete_image`] to free femtovg specific
    /// book-keeping data structures, the underlying backend-specific texture memory
    /// will not be freed. It is the caller's responsible to delete it.
    pub fn create_image_from_external_texture(
        &mut self,
        texture: T::ExternalTexture,
        info: ImageInfo,
    ) -> Result<ImageId, ErrorKind> {
        self.images.register_external_texture(&mut self.renderer, texture, info)
    }

    /// Creates image from specified image data.
    pub fn create_image<'a, S: Into<ImageSource<'a>>>(
        &mut self,
        src: S,
        flags: ImageFlags,
    ) -> Result<ImageId, ErrorKind> {
        let src = src.into();
        let size = src.dimensions();
        let id = self.create_image_empty(size.width, size.height, src.format(), flags)?;
        self.images.update(&mut self.renderer, id, src, 0, 0)?;
        Ok(id)
    }

    /// Returns the native texture of an image given its ID.
    pub fn get_native_texture(&self, id: ImageId) -> Result<T::NativeTexture, ErrorKind> {
        self.get_image(id)
            .ok_or(ErrorKind::ImageIdNotFound)
            .and_then(|image| self.renderer.get_native_texture(image))
    }

    /// Retrieves a reference to the image with the specified ID.
    pub fn get_image(&self, id: ImageId) -> Option<&T::Image> {
        self.images.get(id)
    }

    /// Retrieves a mutable reference to the image with the specified ID.
    pub fn get_image_mut(&mut self, id: ImageId) -> Option<&mut T::Image> {
        self.images.get_mut(id)
    }

    /// Resizes an image to the new provided dimensions.
    pub fn realloc_image(
        &mut self,
        id: ImageId,
        width: usize,
        height: usize,
        format: PixelFormat,
        flags: ImageFlags,
    ) -> Result<(), ErrorKind> {
        let info = ImageInfo::new(flags, width, height, format);
        self.images.realloc(&mut self.renderer, id, info)
    }

    /// Decode an image from file
    #[cfg(feature = "image-loading")]
    pub fn load_image_file<P: AsRef<FilePath>>(
        &mut self,
        filename: P,
        flags: ImageFlags,
    ) -> Result<ImageId, ErrorKind> {
        let image = ::image::open(filename)?;

        let src = ImageSource::try_from(&image)?;

        self.create_image(src, flags)
    }

    /// Decode an image from memory
    #[cfg(feature = "image-loading")]
    pub fn load_image_mem(&mut self, data: &[u8], flags: ImageFlags) -> Result<ImageId, ErrorKind> {
        let image = ::image::load_from_memory(data)?;

        let src = ImageSource::try_from(&image)?;

        self.create_image(src, flags)
    }

    /// Updates image data specified by image handle.
    pub fn update_image<'a, S: Into<ImageSource<'a>>>(
        &mut self,
        id: ImageId,
        src: S,
        x: usize,
        y: usize,
    ) -> Result<(), ErrorKind> {
        self.images.update(&mut self.renderer, id, src.into(), x, y)
    }

    /// Deletes created image.
    pub fn delete_image(&mut self, id: ImageId) {
        self.images.remove(&mut self.renderer, id);
    }

    /// Returns image info
    pub fn image_info(&self, id: ImageId) -> Result<ImageInfo, ErrorKind> {
        if let Some(info) = self.images.info(id) {
            Ok(info)
        } else {
            Err(ErrorKind::ImageIdNotFound)
        }
    }

    /// Returns the size in pixels of the image for the specified id.
    pub fn image_size(&self, id: ImageId) -> Result<(usize, usize), ErrorKind> {
        let info = self.image_info(id)?;
        Ok((info.width(), info.height()))
    }

    /// Renders the given `source_image` into `target_image` while applying a filter effect.
    ///
    /// The target image must have the same size as the source image. The filtering is recorded
    /// as a drawing command and run by the renderer when [`Self::flush()`] is called.
    ///
    /// The filtering does not take any transformation set on the Canvas into account nor does it
    /// change the current rendering target.
    pub fn filter_image(&mut self, target_image: ImageId, filter: ImageFilter, source_image: ImageId) {
        let Ok((image_width, image_height)) = self.image_size(source_image) else {
            return;
        };

        // The renderer will receive a RenderFilteredImage command with two triangles attached that
        // cover the image and the source image.
        let mut cmd = Command::new(CommandType::RenderFilteredImage { target_image, filter });
        cmd.image = Some(source_image);

        let vertex_offset = self.verts.len();

        let image_width = image_width as f32;
        let image_height = image_height as f32;

        let quad_x0 = 0.0;
        let quad_y0 = -image_height;
        let quad_x1 = image_width;
        let quad_y1 = image_height;

        let texture_x0 = -(image_width / 2.);
        let texture_y0 = -(image_height / 2.);
        let texture_x1 = (image_width) / 2.;
        let texture_y1 = (image_height) / 2.;

        self.verts.push(Vertex::new(quad_x0, quad_y0, texture_x0, texture_y0));
        self.verts.push(Vertex::new(quad_x1, quad_y1, texture_x1, texture_y1));
        self.verts.push(Vertex::new(quad_x1, quad_y0, texture_x1, texture_y0));
        self.verts.push(Vertex::new(quad_x0, quad_y0, texture_x0, texture_y0));
        self.verts.push(Vertex::new(quad_x0, quad_y1, texture_x0, texture_y1));
        self.verts.push(Vertex::new(quad_x1, quad_y1, texture_x1, texture_y1));

        cmd.triangles_verts = Some((vertex_offset, 6));

        self.append_cmd(cmd)
    }

    // Transforms

    /// Resets current transform to a identity matrix.
    pub fn reset_transform(&mut self) {
        self.state_mut().transform = Transform2D::identity();
    }

    #[allow(clippy::many_single_char_names)]
    /// Premultiplies current coordinate system by specified transform.
    pub fn set_transform(&mut self, transform: &Transform2D) {
        self.state_mut().transform.premultiply(transform);
    }

    /// Translates the current coordinate system.
    pub fn translate(&mut self, x: f32, y: f32) {
        let t = Transform2D::translation(x, y);
        self.state_mut().transform.premultiply(&t);
    }

    /// Rotates the current coordinate system. Angle is specified in radians.
    pub fn rotate(&mut self, angle: f32) {
        let t = Transform2D::rotation(angle);
        self.state_mut().transform.premultiply(&t);
    }

    /// Scales the current coordinate system.
    pub fn scale(&mut self, x: f32, y: f32) {
        let t = Transform2D::scaling(x, y);
        self.state_mut().transform.premultiply(&t);
    }

    /// Skews the current coordinate system along X axis. Angle is specified in radians.
    pub fn skew_x(&mut self, angle: f32) {
        let mut t = Transform2D::identity();
        t.skew_x(angle);
        self.state_mut().transform.premultiply(&t);
    }

    /// Skews the current coordinate system along Y axis. Angle is specified in radians.
    pub fn skew_y(&mut self, angle: f32) {
        let mut t = Transform2D::identity();
        t.skew_y(angle);
        self.state_mut().transform.premultiply(&t);
    }

    /// Returns the current transformation matrix
    pub fn transform(&self) -> Transform2D {
        self.state().transform
    }

    // Scissoring

    /// Sets the current scissor rectangle.
    ///
    /// The scissor rectangle is transformed by the current transform.
    pub fn scissor(&mut self, x: f32, y: f32, w: f32, h: f32) {
        let state = self.state_mut();

        let w = w.max(0.0);
        let h = h.max(0.0);

        let mut transform = Transform2D::translation(x + w * 0.5, y + h * 0.5);
        transform *= state.transform;
        state.scissor.transform = transform;

        state.scissor.extent = Some([w * 0.5, h * 0.5]);
    }

    /// Intersects current scissor rectangle with the specified rectangle.
    ///
    /// The scissor rectangle is transformed by the current transform.
    /// Note: in case the rotation of previous scissor rect differs from
    /// the current one, the intersection will be done between the specified
    /// rectangle and the previous scissor rectangle transformed in the current
    /// transform space. The resulting shape is always rectangle.
    pub fn intersect_scissor(&mut self, x: f32, y: f32, w: f32, h: f32) {
        let state = self.state_mut();

        // If no previous scissor has been set, set the scissor as current scissor.
        if state.scissor.extent.is_none() {
            self.scissor(x, y, w, h);
            return;
        }

        let extent = state.scissor.extent.unwrap();

        // Transform the current scissor rect into current transform space.
        // If there is difference in rotation, this will be approximation.

        let Transform2D([a, b, c, d, tx, ty]) = state.scissor.transform / state.transform;

        let ex = extent[0];
        let ey = extent[1];

        let tex = ex * a.abs() + ey * c.abs();
        let tey = ex * b.abs() + ey * d.abs();

        let rect = Rect::new(tx - tex, ty - tey, tex * 2.0, tey * 2.0);
        let res = rect.intersect(Rect::new(x, y, w, h));

        self.scissor(res.x, res.y, res.w, res.h);
    }

    /// Reset and disables scissoring.
    pub fn reset_scissor(&mut self) {
        self.state_mut().scissor = Scissor::default();
    }

    // Paths

    /// Returns true if the specified point (x,y) is in the provided path, and false otherwise.
    pub fn contains_point(&self, path: &Path, x: f32, y: f32, fill_rule: FillRule) -> bool {
        let transform = self.state().transform;

        // The path cache saves a flattened and transformed version of the path.
        let path_cache = path.cache(&transform, self.tess_tol, self.dist_tol);

        // Early out if path is outside the canvas bounds
        if path_cache.bounds.maxx < 0.0
            || path_cache.bounds.minx > self.width() as f32
            || path_cache.bounds.maxy < 0.0
            || path_cache.bounds.miny > self.height() as f32
        {
            return false;
        }

        path_cache.contains_point(x, y, fill_rule)
    }

    /// Return the bounding box for a Path
    pub fn path_bbox(&self, path: &Path) -> Bounds {
        let transform = self.state().transform;

        // The path cache saves a flattened and transformed version of the path.
        let path_cache = path.cache(&transform, self.tess_tol, self.dist_tol);

        path_cache.bounds
    }

    /// Fills the provided Path with the specified Paint.
    pub fn fill_path(&mut self, path: &Path, paint: &Paint) {
        self.fill_path_internal(path, &paint.flavor, paint.shape_anti_alias, paint.fill_rule);
    }

    fn fill_path_internal(&mut self, path: &Path, paint_flavor: &PaintFlavor, anti_alias: bool, fill_rule: FillRule) {
        let mut paint_flavor = paint_flavor.clone();
        let transform = self.state().transform;

        // The path cache saves a flattened and transformed version of the path.
        let mut path_cache = path.cache(&transform, self.tess_tol, self.dist_tol);

        let canvas_width = self.width();
        let canvas_height = self.height();

        // Early out if path is outside the canvas bounds
        if path_cache.bounds.maxx < 0.0
            || path_cache.bounds.minx > canvas_width as f32
            || path_cache.bounds.maxy < 0.0
            || path_cache.bounds.miny > canvas_height as f32
        {
            return;
        }

        // Apply global alpha
        paint_flavor.mul_alpha(self.state().alpha);

        let scissor = self.state().scissor;

        // Calculate fill vertices.
        // expand_fill will fill path_cache.contours[].{stroke, fill} with vertex data for the GPU
        // fringe_with is the size of the strip of triangles generated at the path border used for AA
        let fringe_width = if anti_alias { self.fringe_width } else { 0.0 };
        path_cache.expand_fill(fringe_width, LineJoin::Miter, 2.4);

        // Detect if this path fill is in fact just an unclipped image copy

        if let (Some(path_rect), Some(scissor_rect), true) = (
            path_cache.path_fill_is_rect(),
            scissor.as_rect(canvas_width as f32, canvas_height as f32),
            paint_flavor.is_straight_tinted_image(anti_alias),
        ) {
            if scissor_rect.contains_rect(&path_rect) {
                self.render_unclipped_image_blit(&path_rect, &transform, &paint_flavor);
            } else if let Some(intersection) = path_rect.intersection(&scissor_rect) {
                self.render_unclipped_image_blit(&intersection, &transform, &paint_flavor);
            }

            return;
        }

        // GPU uniforms
        let flavor = if path_cache.contours.len() == 1 && path_cache.contours[0].convexity == Convexity::Convex {
            let params = Params::new(
                &self.images,
                &transform,
                &paint_flavor,
                &GlyphTexture::default(),
                &scissor,
                self.fringe_width,
                self.fringe_width,
                -1.0,
            );

            CommandType::ConvexFill { params }
        } else {
            let stencil_params = Params {
                stroke_thr: -1.0,
                shader_type: ShaderType::Stencil,
                ..Params::default()
            };

            let fill_params = Params::new(
                &self.images,
                &transform,
                &paint_flavor,
                &GlyphTexture::default(),
                &scissor,
                self.fringe_width,
                self.fringe_width,
                -1.0,
            );

            CommandType::ConcaveFill {
                stencil_params,
                fill_params,
            }
        };

        // GPU command
        let mut cmd = Command::new(flavor);
        cmd.fill_rule = fill_rule;
        cmd.composite_operation = self.state().composite_operation;

        if let PaintFlavor::Image { id, .. } = paint_flavor {
            cmd.image = Some(id);
        } else if let Some(paint::GradientColors::MultiStop { stops }) = paint_flavor.gradient_colors() {
            cmd.image = self
                .gradients
                .lookup_or_add(stops, &mut self.images, &mut self.renderer)
                .ok();
        }

        // All verts from all shapes are kept in a single buffer here in the canvas.
        // Drawable struct is used to describe the range of vertices each draw call will operate on
        let mut offset = self.verts.len();

        cmd.drawables.reserve_exact(path_cache.contours.len());
        for contour in &path_cache.contours {
            let mut drawable = Drawable::default();

            // Fill commands can have both fill and stroke vertices. Fill vertices are used to fill
            // the body of the shape while stroke vertices are used to prodice antialiased edges

            if !contour.fill.is_empty() {
                drawable.fill_verts = Some((offset, contour.fill.len()));
                self.verts.extend_from_slice(&contour.fill);
                offset += contour.fill.len();
            }

            if !contour.stroke.is_empty() {
                drawable.stroke_verts = Some((offset, contour.stroke.len()));
                self.verts.extend_from_slice(&contour.stroke);
                offset += contour.stroke.len();
            }

            cmd.drawables.push(drawable);
        }

        if let CommandType::ConcaveFill { .. } = cmd.cmd_type {
            // Concave shapes are first filled by writing to a stencil buffer and then drawing a quad
            // over the shape area with stencil test enabled to produce the final fill. These are
            // the verts needed for the covering quad
            self.verts.push(Vertex::new(
                path_cache.bounds.maxx + fringe_width,
                path_cache.bounds.maxy + fringe_width,
                0.5,
                1.0,
            ));
            self.verts.push(Vertex::new(
                path_cache.bounds.maxx + fringe_width,
                path_cache.bounds.miny - fringe_width,
                0.5,
                1.0,
            ));
            self.verts.push(Vertex::new(
                path_cache.bounds.minx - fringe_width,
                path_cache.bounds.maxy + fringe_width,
                0.5,
                1.0,
            ));
            self.verts.push(Vertex::new(
                path_cache.bounds.minx - fringe_width,
                path_cache.bounds.miny,
                0.5,
                1.0,
            ));

            cmd.triangles_verts = Some((offset, 4));
        }

        self.append_cmd(cmd);
    }

    /// Strokes the provided Path with the specified Paint.
    pub fn stroke_path(&mut self, path: &Path, paint: &Paint) {
        self.stroke_path_internal(path, &paint.flavor, paint.shape_anti_alias, &paint.stroke);
    }

    fn stroke_path_internal(
        &mut self,
        path: &Path,
        paint_flavor: &PaintFlavor,
        anti_alias: bool,
        stroke: &StrokeSettings,
    ) {
        let mut paint_flavor = paint_flavor.clone();
        let transform = self.state().transform;

        if !stroke.line_dash.is_empty() {
            let dashed_path = path.dashed_with_tolerance(&stroke.line_dash, stroke.line_dash_offset, self.tess_tol);
            if dashed_path.is_empty() {
                return;
            }

            let mut solid_stroke = stroke.clone();
            solid_stroke.line_dash.clear();
            solid_stroke.line_dash_offset = 0.0;
            self.stroke_path_internal(&dashed_path, &paint_flavor, anti_alias, &solid_stroke);
            return;
        }

        // The path cache saves a flattened and transformed version of the path.
        let mut path_cache = path.cache(&transform, self.tess_tol, self.dist_tol);

        // Early out if path is outside the canvas bounds
        if path_cache.bounds.maxx < 0.0
            || path_cache.bounds.minx > self.width() as f32
            || path_cache.bounds.maxy < 0.0
            || path_cache.bounds.miny > self.height() as f32
        {
            return;
        }

        let scissor = self.state().scissor;

        // Scale stroke width by current transform scale.
        // Note: I don't know why the original author clamped the max stroke width to 200, but it didn't
        // look correct when zooming in. There was probably a good reson for doing so and I may have
        // introduced a bug by removing the upper bound.
        //paint.set_stroke_width((paint.stroke_width() * transform.average_scale()).max(0.0).min(200.0));
        let mut line_width = (stroke.line_width * transform.average_scale()).max(0.0);

        if line_width < self.fringe_width {
            // If the stroke width is less than pixel size, use alpha to emulate coverage.
            // Since coverage is area, scale by alpha*alpha.
            let alpha = (line_width / self.fringe_width).clamp(0.0, 1.0);

            paint_flavor.mul_alpha(alpha * alpha);
            line_width = self.fringe_width;
        }

        // Apply global alpha
        paint_flavor.mul_alpha(self.state().alpha);

        // Calculate stroke vertices.
        // expand_stroke will fill path_cache.contours[].stroke with vertex data for the GPU
        let fringe_with = if anti_alias { self.fringe_width } else { 0.0 };
        path_cache.expand_stroke(
            line_width * 0.5,
            fringe_with,
            stroke.line_cap_start,
            stroke.line_cap_end,
            stroke.line_join,
            stroke.miter_limit,
            self.tess_tol,
        );

        // GPU uniforms
        let params = Params::new(
            &self.images,
            &transform,
            &paint_flavor,
            &GlyphTexture::default(),
            &scissor,
            line_width,
            self.fringe_width,
            -1.0,
        );

        let flavor = if stroke.stencil_strokes {
            let params2 = Params::new(
                &self.images,
                &transform,
                &paint_flavor,
                &GlyphTexture::default(),
                &scissor,
                line_width,
                self.fringe_width,
                1.0 - 0.5 / 255.0,
            );

            CommandType::StencilStroke {
                params1: params,
                params2,
            }
        } else {
            CommandType::Stroke { params }
        };

        // GPU command
        let mut cmd = Command::new(flavor);
        cmd.composite_operation = self.state().composite_operation;

        if let PaintFlavor::Image { id, .. } = paint_flavor {
            cmd.image = Some(id);
        } else if let Some(paint::GradientColors::MultiStop { stops }) = paint_flavor.gradient_colors() {
            cmd.image = self
                .gradients
                .lookup_or_add(stops, &mut self.images, &mut self.renderer)
                .ok();
        }

        // All verts from all shapes are kept in a single buffer here in the canvas.
        // Drawable struct is used to describe the range of vertices each draw call will operate on
        let mut offset = self.verts.len();

        cmd.drawables.reserve_exact(path_cache.contours.len());
        for contour in &path_cache.contours {
            let mut drawable = Drawable::default();

            if !contour.stroke.is_empty() {
                drawable.stroke_verts = Some((offset, contour.stroke.len()));
                self.verts.extend_from_slice(&contour.stroke);
                offset += contour.stroke.len();
            }

            cmd.drawables.push(drawable);
        }

        self.append_cmd(cmd);
    }

    fn render_unclipped_image_blit(&mut self, target_rect: &Rect, transform: &Transform2D, paint_flavor: &PaintFlavor) {
        let scissor = self.state().scissor;

        let mut params = Params::new(
            &self.images,
            transform,
            paint_flavor,
            &GlyphTexture::default(),
            &scissor,
            0.,
            0.,
            -1.0,
        );
        params.shader_type = ShaderType::TextureCopyUnclipped;

        let mut cmd = Command::new(CommandType::Triangles { params });
        cmd.composite_operation = self.state().composite_operation;

        let x0 = target_rect.x;
        let y0 = target_rect.y;
        let x1 = x0 + target_rect.w;
        let y1 = y0 + target_rect.h;

        let (p0, p1) = (x0, y0);
        let (p2, p3) = (x1, y0);
        let (p4, p5) = (x1, y1);
        let (p6, p7) = (x0, y1);

        // Apply the same mapping from vertex coordinates to texture coordinates as in the fragment shader,
        // but now ahead of time.
        let mut to_texture_space_transform = Transform2D::scaling(1. / params.extent[0], 1. / params.extent[1]);
        to_texture_space_transform.premultiply(&Transform2D([
            params.paint_mat[0],
            params.paint_mat[1],
            params.paint_mat[4],
            params.paint_mat[5],
            params.paint_mat[8],
            params.paint_mat[9],
        ]));

        let (s0, t0) = to_texture_space_transform.transform_point(target_rect.x, target_rect.y);
        let (s1, t1) =
            to_texture_space_transform.transform_point(target_rect.x + target_rect.w, target_rect.y + target_rect.h);

        let verts = [
            Vertex::new(p0, p1, s0, t0),
            Vertex::new(p4, p5, s1, t1),
            Vertex::new(p2, p3, s1, t0),
            Vertex::new(p0, p1, s0, t0),
            Vertex::new(p6, p7, s0, t1),
            Vertex::new(p4, p5, s1, t1),
        ];

        if let &PaintFlavor::Image { id, .. } = paint_flavor {
            cmd.image = Some(id);
        }

        cmd.triangles_verts = Some((self.verts.len(), verts.len()));
        self.append_cmd(cmd);

        self.verts.extend_from_slice(&verts);
    }

    // Text

    /// Adds a font file to the canvas
    #[cfg(feature = "textlayout")]
    pub fn add_font<P: AsRef<FilePath>>(&mut self, file_path: P) -> Result<FontId, ErrorKind> {
        self.text_context.borrow_mut().add_font_file(file_path)
    }

    /// Adds a font to the canvas by reading it from the specified chunk of memory.
    #[cfg(feature = "textlayout")]
    pub fn add_font_mem(&mut self, data: &[u8]) -> Result<FontId, ErrorKind> {
        self.text_context.borrow_mut().add_font_mem(data)
    }

    /// Adds all .ttf files from a directory
    #[cfg(feature = "textlayout")]
    pub fn add_font_dir<P: AsRef<FilePath>>(&mut self, dir_path: P) -> Result<Vec<FontId>, ErrorKind> {
        self.text_context.borrow_mut().add_font_dir(dir_path)
    }

    /// Returns the variation axes available for the specified font.
    ///
    /// For variable fonts, this returns information about each axis (e.g. weight, width).
    /// For static fonts, this returns an empty vector.
    ///
    /// Axes are returned in the order they appear in the font's OpenType
    /// `fvar` table. This is the same order that [`Canvas::fill_glyph_run`]
    /// and [`Canvas::stroke_glyph_run`] expect for their normalized
    /// coordinate slices: the i-th coordinate corresponds to the i-th axis.
    pub fn font_variation_axes(&self, font_id: FontId) -> Result<Vec<VariationAxisInfo>, ErrorKind> {
        let ctx = self.text_context.borrow();
        let font = ctx.font(font_id).ok_or(ErrorKind::NoFontFound)?;
        Ok(font.variation_axes())
    }

    /// Returns information on how the provided text will be drawn with the specified paint.
    #[cfg(feature = "textlayout")]
    pub fn measure_text<S: AsRef<str>>(
        &self,
        x: f32,
        y: f32,
        text: S,
        paint: &Paint,
    ) -> Result<TextMetrics, ErrorKind> {
        let scale = self.font_scale() * self.device_px_ratio;

        let mut text_settings = paint.text.clone();
        text_settings.font_size *= scale;
        text_settings.letter_spacing *= scale;

        let scale = self.font_scale() * self.device_px_ratio;
        let invscale = 1.0 / scale;

        self.text_context
            .borrow_mut()
            .measure_text(x * scale, y * scale, text, &text_settings)
            .map(|mut metrics| {
                metrics.scale(invscale);
                metrics
            })
    }

    /// Returns font metrics for a particular Paint.
    #[cfg(feature = "textlayout")]
    pub fn measure_font(&self, paint: &Paint) -> Result<FontMetrics, ErrorKind> {
        let scale = self.font_scale() * self.device_px_ratio;

        self.text_context.borrow_mut().measure_font(
            paint.text.font_size * scale,
            &paint.text.font_ids,
            &paint.text.font_variations,
        )
    }

    /// Returns the maximum index-th byte of text that will fit inside `max_width`.
    ///
    /// The retuned index will always lie at the start and/or end of a UTF-8 code point sequence or at the start or end of the text
    #[cfg(feature = "textlayout")]
    pub fn break_text<S: AsRef<str>>(&self, max_width: f32, text: S, paint: &Paint) -> Result<usize, ErrorKind> {
        let scale = self.font_scale() * self.device_px_ratio;

        let mut text_settings = paint.text.clone();
        text_settings.font_size *= scale;
        text_settings.letter_spacing *= scale;

        let max_width = max_width * scale;

        self.text_context
            .borrow_mut()
            .break_text(max_width, text, &text_settings)
    }

    /// Returnes a list of ranges representing each line of text that will fit inside `max_width`
    #[cfg(feature = "textlayout")]
    pub fn break_text_vec<S: AsRef<str>>(
        &self,
        max_width: f32,
        text: S,
        paint: &Paint,
    ) -> Result<Vec<Range<usize>>, ErrorKind> {
        let scale = self.font_scale() * self.device_px_ratio;

        let mut text_settings = paint.text.clone();
        text_settings.font_size *= scale;
        text_settings.letter_spacing *= scale;

        let max_width = max_width * scale;

        self.text_context
            .borrow_mut()
            .break_text_vec(max_width, text, &text_settings)
    }

    /// Fills the provided string with the specified Paint.
    #[cfg(feature = "textlayout")]
    pub fn fill_text<S: AsRef<str>>(
        &mut self,
        x: f32,
        y: f32,
        text: S,
        paint: &Paint,
    ) -> Result<TextMetrics, ErrorKind> {
        self.draw_text(x, y, text.as_ref(), paint, RenderMode::Fill)
    }

    /// Strokes the provided string with the specified Paint.
    #[cfg(feature = "textlayout")]
    pub fn stroke_text<S: AsRef<str>>(
        &mut self,
        x: f32,
        y: f32,
        text: S,
        paint: &Paint,
    ) -> Result<TextMetrics, ErrorKind> {
        self.draw_text(x, y, text.as_ref(), paint, RenderMode::Stroke)
    }

    /// Fills the provided glyphs with the specified Paint.
    ///
    /// `normalized_coords` specifies variation axis positions for variable
    /// fonts as `i16` values in F2DOT14 format (the OpenType normalized
    /// coordinate representation, range \[-1.0, 1.0\] mapped to
    /// \[-16384, 16384\]), one per axis in `fvar` order. Pass an empty slice
    /// for the font's default instance. These coordinates are typically
    /// obtained from a text shaper (e.g. rustybuzz, harfbuzz, parley).
    /// See [`Canvas::font_variation_axes`] to query the available axes.
    pub fn fill_glyph_run(
        &mut self,
        font_id: FontId,
        normalized_coords: &[i16],
        glyphs: impl IntoIterator<Item = PositionedGlyph>,
        paint: &Paint,
    ) -> Result<(), ErrorKind> {
        self.draw_glyph_run(glyphs, paint, font_id, normalized_coords, RenderMode::Fill)
    }

    /// Strokes the provided glyphs with the specified Paint.
    ///
    /// `normalized_coords` specifies variation axis positions for variable
    /// fonts as `i16` values in F2DOT14 format (the OpenType normalized
    /// coordinate representation, range \[-1.0, 1.0\] mapped to
    /// \[-16384, 16384\]), one per axis in `fvar` order. Pass an empty slice
    /// for the font's default instance. These coordinates are typically
    /// obtained from a text shaper (e.g. rustybuzz, harfbuzz, parley).
    /// See [`Canvas::font_variation_axes`] to query the available axes.
    pub fn stroke_glyph_run(
        &mut self,
        font_id: FontId,
        normalized_coords: &[i16],
        glyphs: impl IntoIterator<Item = PositionedGlyph>,
        paint: &Paint,
    ) -> Result<(), ErrorKind> {
        self.draw_glyph_run(glyphs, paint, font_id, normalized_coords, RenderMode::Stroke)
    }

    /// Dispatch an explicit set of `GlyphDrawCommands` to the renderer. Use this only if you are
    /// using a custom font rasterizer/layout.
    pub fn draw_glyph_commands(&mut self, draw_commands: GlyphDrawCommands, paint: &Paint) {
        let transform = self.state().transform;
        let create_vertices = |quads: &Vec<text::Quad>| {
            let mut verts = Vec::with_capacity(quads.len() * 6);

            for quad in quads {
                let left = quad.x0;
                let right = quad.x1;
                let top = quad.y0;
                let bottom = quad.y1;

                let (p0, p1) = transform.transform_point(left, top);
                let (p2, p3) = transform.transform_point(right, top);
                let (p4, p5) = transform.transform_point(right, bottom);
                let (p6, p7) = transform.transform_point(left, bottom);

                verts.push(Vertex::new(p0, p1, quad.s0, quad.t0));
                verts.push(Vertex::new(p4, p5, quad.s1, quad.t1));
                verts.push(Vertex::new(p2, p3, quad.s1, quad.t0));
                verts.push(Vertex::new(p0, p1, quad.s0, quad.t0));
                verts.push(Vertex::new(p6, p7, quad.s0, quad.t1));
                verts.push(Vertex::new(p4, p5, quad.s1, quad.t1));
            }
            verts
        };

        // Apply global alpha
        let mut paint_flavor = paint.flavor.clone();
        paint_flavor.mul_alpha(self.state().alpha);

        for cmd in draw_commands.alpha_glyphs {
            let verts = create_vertices(&cmd.quads);

            self.render_triangles(&verts, &transform, &paint_flavor, GlyphTexture::AlphaMask(cmd.image_id));
        }

        for cmd in draw_commands.color_glyphs {
            let verts = create_vertices(&cmd.quads);

            self.render_triangles(
                &verts,
                &transform,
                &paint_flavor,
                GlyphTexture::ColorTexture(cmd.image_id),
            );
        }
    }

    // Private

    #[cfg(feature = "textlayout")]
    fn draw_text(
        &mut self,
        x: f32,
        y: f32,
        text: &str,
        paint: &Paint,
        render_mode: RenderMode,
    ) -> Result<TextMetrics, ErrorKind> {
        use itertools::Itertools;

        let scale = self.font_scale() * self.device_px_ratio;
        let invscale = 1.0 / scale;

        let mut text_settings = paint.text.clone();
        text_settings.font_size *= scale;
        text_settings.letter_spacing *= scale;

        let mut layout = text::shape(
            x * scale,
            y * scale,
            &mut self.text_context.borrow_mut(),
            &text_settings,
            text,
            None,
        )?;

        let normalized_coords = {
            let text_context = self.text_context.borrow();
            text::normalize_variations(&text_context, &paint.text.font_ids, &paint.text.font_variations)
        };

        // Captured in scaled shaping space; decorations hang off it below.
        let baseline_scaled = run_baseline(&layout.glyphs);

        for (font_id, glyph_run) in &layout
            .glyphs
            .iter()
            .filter(|shaped_glyph| !shaped_glyph.c.is_control())
            .chunk_by(|g| g.font_id)
        {
            self.draw_glyph_run(
                glyph_run.map(|shaped_glyph| PositionedGlyph {
                    x: shaped_glyph.x * invscale,
                    y: shaped_glyph.y * invscale,
                    glyph_id: shaped_glyph.glyph_id,
                }),
                paint,
                font_id,
                &normalized_coords,
                render_mode,
            )?;
        }

        layout.scale(invscale);

        // Text decorations are an SVG/CSS extension (Canvas 2D has none). They are
        // emitted as plain filled rectangles in user space — the same coordinate
        // space as the `* invscale` glyph positions handed to `draw_glyph_run` —
        // so `fill_path` runs them through the identical canvas transform the
        // glyph runs use. That keeps the lines aligned with the glyphs across the
        // direct-outline, atlas, and scale-baked-atlas paths alike.
        if !paint.text.text_decoration.is_none() {
            if let Some(baseline_scaled) = baseline_scaled {
                self.draw_text_decorations(paint, baseline_scaled * invscale, layout.x, layout.width());
            }
        }

        Ok(layout)
    }

    /// Emits the enabled text-decoration lines for a run as filled rectangles in
    /// user space. `baseline` is the run baseline (user space, +y down), `x` the
    /// run's left edge, and `width` its advance width.
    #[cfg(feature = "textlayout")]
    fn draw_text_decorations(&mut self, paint: &Paint, baseline: f32, x: f32, width: f32) {
        let decoration = paint.text.text_decoration;

        // Metrics in user-space units (scaled for the unscaled font size) so the
        // offsets match the user-space baseline. `measure_font` reads the primary
        // font with the same variations the run was shaped with.
        let metrics = {
            let text_context = self.text_context.borrow();
            text_context.measure_font(paint.text.font_size, &paint.text.font_ids, &paint.text.font_variations)
        };
        let Ok(metrics) = metrics else {
            return;
        };

        // The decoration takes the text paint's color, matching SVG where the
        // decoration uses the text fill. The full paint flavor (gradient/image)
        // is reused as-is so a gradient-filled run gets a gradient-filled line.
        let line_paint = paint.clone();

        let emit = |this: &mut Self, center_y: f32, thickness: f32| {
            let thickness = thickness.max(1.0);
            let mut path = Path::new();
            path.rect(x, center_y - thickness / 2.0, width, thickness);
            this.fill_path(&path, &line_paint);
        };

        // OpenType position values measure from the baseline with +y pointing up,
        // while canvas y grows downward, so a line's center is `baseline - pos`.
        if decoration.underline {
            emit(
                self,
                baseline - metrics.underline_position(),
                metrics.underline_thickness(),
            );
        }
        if decoration.strikethrough {
            emit(
                self,
                baseline - metrics.strikeout_position(),
                metrics.strikeout_thickness(),
            );
        }
        if decoration.overline {
            // No dedicated metric; sit the line at the ascent with the underline
            // thickness, nudged up by half its thickness so it clears the glyphs.
            let thickness = metrics.underline_thickness().max(1.0);
            emit(self, baseline - metrics.ascender() - thickness / 2.0, thickness);
        }
    }

    fn draw_glyph_run(
        &mut self,
        glyphs: impl IntoIterator<Item = PositionedGlyph>,
        paint: &Paint,
        font_id: FontId,
        normalized_coords: &[i16],
        render_mode: RenderMode,
    ) -> Result<(), ErrorKind> {
        let scale = self.font_scale() * self.device_px_ratio;

        let mut stroke = paint.stroke.clone();
        stroke.line_width *= scale;

        // TODO: Early out if text is outside the canvas bounds, or maybe even check for each character in layout.

        let text_context = self.text_context.clone();
        let mut text_context = text_context.borrow_mut();

        // How this glyph run is rasterized for the current canvas transform.
        #[derive(Clone, Copy)]
        enum Rasterization {
            Path,
            Atlas,
            ScaledAtlas { scale: f32, translation: (f32, f32) },
        }

        // Classify the canvas transform. 1e-3 epsilon: tight enough to catch any
        // intentional transform, loose enough to tolerate matrix-op drift.
        let rasterization = match self.state().transform.as_uniform_scale_translation(1e-3) {
            // Rotation / skew / non-uniform / negative scale: outline rendering.
            None => Rasterization::Path,
            Some((scale, tx, ty)) => {
                // Quantize the baked scale so small animation steps don't churn the
                // atlas; 1/16 steps (≈6%) are imperceptible at typical zoom levels.
                let scale = geometry::quantize(scale, 1.0 / 16.0).max(1.0 / 16.0);
                if paint.text.font_size * scale > 92.0 {
                    // Cached bitmap would be too large.
                    Rasterization::Path
                } else if scale == 1.0 {
                    // Pure translation (within a quantization step): nothing to bake.
                    Rasterization::Atlas
                } else if matches!(paint.flavor, PaintFlavor::Color(_)) {
                    Rasterization::ScaledAtlas {
                        scale,
                        translation: (tx, ty),
                    }
                } else {
                    // Gradients/images map their coordinates through the canvas
                    // transform that the atlas path swaps out for a translation,
                    // which would shift them; keep those direct.
                    Rasterization::Path
                }
            }
        };

        let need_direct_rendering = matches!(rasterization, Rasterization::Path);
        let effective_scale = match rasterization {
            Rasterization::ScaledAtlas { scale, .. } => scale,
            _ => 1.0,
        };
        let effective_font_size = paint.text.font_size * effective_scale;

        let Some(font) = text_context.font_mut(font_id) else {
            return Err(ErrorKind::NoFontFound);
        };

        let font_face = font.face_ref_with_normalized_coords(normalized_coords);

        // TODO: create on demand

        let mut color_glyphs = Vec::new();

        let glyphs_it = glyphs.into_iter();
        let non_color_glyphs = glyphs_it
            .filter(|glyph| {
                if font
                    .glyph(&font_face, glyph.glyph_id, normalized_coords)
                    .is_some_and(|glyph| glyph.path.is_none())
                {
                    color_glyphs.push(glyph.clone());

                    false
                } else {
                    true
                }
            })
            .collect::<Vec<_>>();

        // When baking scale into the rasterization, pre-multiply glyph positions
        // by `effective_scale` so that under a translation-only canvas transform
        // they still land at the original screen position.
        let scaled = |g: &PositionedGlyph| PositionedGlyph {
            x: g.x * effective_scale,
            y: g.y * effective_scale,
            glyph_id: g.glyph_id,
        };

        let mut draw_commands = if need_direct_rendering {
            text::render_direct(
                self,
                font,
                non_color_glyphs.into_iter(),
                &paint.flavor,
                paint.shape_anti_alias,
                &stroke,
                paint.text.font_size,
                render_mode,
                normalized_coords,
            )?;
            GlyphDrawCommands::default()
        } else {
            self.glyph_atlas.clone().render_atlas(
                self,
                font_id,
                font,
                &font_face,
                non_color_glyphs.iter().map(scaled),
                effective_font_size,
                paint.stroke.line_width,
                render_mode,
                normalized_coords,
            )?
        };

        if !color_glyphs.is_empty() {
            let color_commands = {
                let atlas = if need_direct_rendering {
                    self.ephemeral_glyph_atlas
                        .get_or_insert_with(|| Rc::new(GlyphAtlas::new(&self.text_context)))
                        .clone()
                } else {
                    self.glyph_atlas.clone()
                };

                // Color glyphs on the atlas path follow the same scale baking.
                // On the direct path we leave them at the original font_size —
                // that already matches today's behavior.
                if need_direct_rendering {
                    atlas.render_atlas(
                        self,
                        font_id,
                        font,
                        &font_face,
                        color_glyphs.into_iter(),
                        paint.text.font_size,
                        paint.stroke.line_width,
                        render_mode,
                        normalized_coords,
                    )?
                } else {
                    atlas.render_atlas(
                        self,
                        font_id,
                        font,
                        &font_face,
                        color_glyphs.iter().map(scaled),
                        effective_font_size,
                        paint.stroke.line_width,
                        render_mode,
                        normalized_coords,
                    )?
                }
            };

            draw_commands.alpha_glyphs.extend(color_commands.alpha_glyphs);
            draw_commands.color_glyphs.extend(color_commands.color_glyphs);
        }

        // For the scaled-atlas path, present the pre-scaled glyph quads with a
        // translation-only transform so the bitmap shows at its on-screen pixel
        // size. render_atlas already emitted quads in the scaled glyph space, so
        // only draw_glyph_commands (which applies the canvas transform) needs the
        // swap — and since it is infallible, the transform is always restored even
        // though the fallible rendering above used `?`.
        match rasterization {
            Rasterization::ScaledAtlas {
                translation: (tx, ty), ..
            } => {
                let saved = self.state().transform;
                self.state_mut().transform = Transform2D::translation(tx, ty);
                self.draw_glyph_commands(draw_commands, paint);
                self.state_mut().transform = saved;
            }
            _ => self.draw_glyph_commands(draw_commands, paint),
        }

        Ok(())
    }

    fn render_triangles(
        &mut self,
        verts: &[Vertex],
        transform: &Transform2D,
        paint_flavor: &PaintFlavor,
        glyph_texture: GlyphTexture,
    ) {
        let scissor = self.state().scissor;

        let params = Params::new(
            &self.images,
            transform,
            paint_flavor,
            &glyph_texture,
            &scissor,
            1.0,
            1.0,
            -1.0,
        );

        let mut cmd = Command::new(CommandType::Triangles { params });
        cmd.composite_operation = self.state().composite_operation;
        cmd.glyph_texture = glyph_texture;

        if let &PaintFlavor::Image { id, .. } = paint_flavor {
            cmd.image = Some(id);
        } else if let Some(paint::GradientColors::MultiStop { stops }) = paint_flavor.gradient_colors() {
            cmd.image = self
                .gradients
                .lookup_or_add(stops, &mut self.images, &mut self.renderer)
                .ok();
        }

        cmd.triangles_verts = Some((self.verts.len(), verts.len()));
        self.append_cmd(cmd);

        self.verts.extend_from_slice(verts);
    }

    fn font_scale(&self) -> f32 {
        let avg_scale = self.state().transform.average_scale();

        geometry::quantize(avg_scale, 0.1).min(7.0)
    }

    //

    fn state(&self) -> &State {
        self.state_stack.last().unwrap()
    }

    fn state_mut(&mut self) -> &mut State {
        self.state_stack.last_mut().unwrap()
    }

    /// Get a list of all font textures.
    #[cfg(feature = "debug_inspector")]
    pub fn debug_inspector_get_font_textures(&self) -> Vec<ImageId> {
        self.glyph_atlas
            .glyph_textures
            .borrow()
            .iter()
            .map(|t| t.image_id)
            .collect()
    }

    /// Draws an image with the specified `id` on the whole canvas.
    #[cfg(feature = "debug_inspector")]
    pub fn debug_inspector_draw_image(&mut self, id: ImageId) {
        if let Ok(size) = self.image_size(id) {
            let width = size.0 as f32;
            let height = size.1 as f32;
            let mut path = Path::new();
            path.rect(0f32, 0f32, width, height);
            self.fill_path(&path, &Paint::image(id, 0f32, 0f32, width, height, 0f32, 1f32));
        }
    }
}

impl<T> Canvas<T>
where
    T: SurfacelessRenderer,
{
    /// Tells the renderer to execute all drawing commands and clears the current internal state
    ///
    /// Call this at the end of each frame.
    pub fn flush(&mut self) {
        self.renderer
            .render_surfaceless(&mut self.images, &self.verts, std::mem::take(&mut self.commands));
        self.verts.clear();
        self.gradients
            .release_old_gradients(&mut self.images, &mut self.renderer);
        if let Some(atlas) = self.ephemeral_glyph_atlas.take() {
            atlas.clear(self);
        }
    }
}

impl<T: Renderer> Drop for Canvas<T> {
    fn drop(&mut self) {
        self.images.clear(&mut self.renderer);
    }
}

/// This struct holds the parameter needs to draw a single glyph using the low-level `fill_glyphs`
/// and `stroke_glyphs` API.
#[derive(Clone, Debug)]
pub struct PositionedGlyph {
    /// The glyph will be drawn at the specified x position.
    pub x: f32,
    /// The glyph will be drawn at the specified x position.
    pub y: f32,
    /// The TrueType glyph id to use when rendering the glyph. This is specific
    /// to the font registered under the `font_id` field.
    pub glyph_id: u16,
}

// re-exports
#[cfg(feature = "image-loading")]
pub use ::image as img;

pub use imgref;
pub use rgb;

/// Internal structure that implements the Renderer trait for unit testing.
#[cfg(test)]
#[derive(Default, Debug)]
pub struct RecordingRenderer {
    /// Vector of the last commands submitted to the renderer.
    pub last_commands: Rc<RefCell<Vec<renderer::Command>>>,
    /// Vertex buffer that accompanied the last submitted commands.
    pub last_verts: Rc<RefCell<Vec<renderer::Vertex>>>,
}

#[cfg(test)]
impl Renderer for RecordingRenderer {
    type Image = DummyImage;
    type NativeTexture = ();
    type ExternalTexture = ();
    type RenderOutput = ();
    type CommandBuffer = ();

    fn set_size(&mut self, _width: u32, _height: u32, _dpi: f32) {}

    fn render(
        &mut self,
        _output: impl Into<Self::RenderOutput>,
        _images: &mut ImageStore<Self::Image>,
        verts: &[renderer::Vertex],
        commands: Vec<renderer::Command>,
    ) {
        *self.last_commands.borrow_mut() = commands;
        *self.last_verts.borrow_mut() = verts.to_vec();
    }

    fn alloc_image(&mut self, info: crate::ImageInfo) -> Result<Self::Image, ErrorKind> {
        Ok(Self::Image { info })
    }

    fn create_image_from_native_texture(
        &mut self,
        _native_texture: Self::NativeTexture,
        _info: crate::ImageInfo,
    ) -> Result<Self::Image, ErrorKind> {
        Err(ErrorKind::UnsupportedImageFormat)
    }

    fn create_image_from_external_texture(
        &mut self,
        _external_texture: Self::ExternalTexture,
        _info: crate::ImageInfo,
    ) -> Result<Self::Image, ErrorKind> {
        Err(ErrorKind::UnsupportedImageFormat)
    }

    fn update_image(
        &mut self,
        image: &mut Self::Image,
        data: crate::ImageSource,
        x: usize,
        y: usize,
    ) -> Result<(), ErrorKind> {
        let size = data.dimensions();

        if x + size.width > image.info.width() {
            return Err(ErrorKind::ImageUpdateOutOfBounds);
        }

        if y + size.height > image.info.height() {
            return Err(ErrorKind::ImageUpdateOutOfBounds);
        }

        Ok(())
    }

    fn delete_image(&mut self, _image: Self::Image, _image_id: crate::ImageId) {}

    fn screenshot(&mut self) -> Result<imgref::ImgVec<rgb::RGBA8>, ErrorKind> {
        Ok(imgref::ImgVec::new(Vec::new(), 0, 0))
    }
}

/// Dummy image type used for tests.
#[cfg(test)]
#[derive(Debug)]
pub struct DummyImage {
    info: ImageInfo,
}

#[test]
fn test_image_blit_fast_path() {
    use renderer::{Command, CommandType};

    let renderer = RecordingRenderer::default();
    let recorded_commands = renderer.last_commands.clone();
    let mut canvas = Canvas::new(renderer).unwrap();
    canvas.set_size(100, 100, 1.);
    let mut path = Path::new();
    path.rect(10., 10., 50., 50.);
    let image = canvas
        .create_image_empty(30, 30, PixelFormat::Rgba8, ImageFlags::empty())
        .unwrap();
    let paint = Paint::image(image, 0., 0., 30., 30., 0., 0.).with_anti_alias(false);
    canvas.fill_path(&path, &paint);
    canvas.flush_to_output(());

    let commands = recorded_commands.borrow();
    let mut commands = commands.iter();
    assert!(matches!(
        commands.next(),
        Some(Command {
            cmd_type: CommandType::SetRenderTarget(..),
            ..
        })
    ));
    assert!(matches!(
        commands.next(),
        Some(Command {
            cmd_type: CommandType::Triangles {
                params: Params {
                    shader_type: renderer::ShaderType::TextureCopyUnclipped,
                    ..
                }
            },
            ..
        })
    ));
}

/// Text rendering picks one of two strategies depending on the canvas transform
/// and paint: cached atlas bitmaps (emitting a `Triangles` command that samples a
/// glyph texture) or direct outline rendering (emitting plain path fills with no
/// glyph texture). Verify each canvas use is routed to the expected strategy.
#[cfg(feature = "textlayout")]
#[test]
fn fill_text_selects_atlas_or_path_rendering() {
    use crate::paint::GlyphTexture;
    use renderer::CommandType;

    #[derive(Clone, Copy)]
    enum PaintKind {
        Solid,
        BigSolid,
        Gradient,
    }

    #[derive(Debug, PartialEq)]
    enum Expect {
        Atlas,
        Path,
    }

    // A fresh canvas per case so the persistent glyph atlas (or any other state)
    // built by one case can't influence another. A large viewport plus a
    // near-origin draw position keeps even the heavily scaled cases on-screen —
    // off-screen geometry is culled, which would hide the commands we inspect.
    let make_canvas = || {
        let renderer = RecordingRenderer::default();
        let recorded = renderer.last_commands.clone();
        let mut canvas = Canvas::new(renderer).unwrap();
        canvas.set_size(4000, 4000, 1.0);
        let font = canvas
            .add_font_mem(include_bytes!("../examples/assets/amiri-regular.ttf"))
            .expect("failed to load test font");
        (canvas, recorded, font)
    };

    // (description, canvas transform, paint, expected strategy)
    let cases = [
        // Pure translation: cached atlas bitmaps, nothing baked.
        (
            "pure translation",
            Transform2D::translation(10.0, 20.0),
            PaintKind::Solid,
            Expect::Atlas,
        ),
        // Uniform scale + solid color: the scale is baked into the atlas bitmap.
        (
            "uniform scale, solid",
            Transform2D::scaling(2.0, 2.0),
            PaintKind::Solid,
            Expect::Atlas,
        ),
        // A scale that quantizes back to 1.0 still uses the atlas.
        (
            "near-unit scale, solid",
            Transform2D::scaling(1.02, 1.02),
            PaintKind::Solid,
            Expect::Atlas,
        ),
        // Gradients can't bake scale (their coords map through the swapped-out
        // transform), so a scaled gradient falls back to outlines.
        (
            "uniform scale, gradient",
            Transform2D::scaling(2.0, 2.0),
            PaintKind::Gradient,
            Expect::Path,
        ),
        // Rotation isn't a uniform scale + translation: outlines.
        (
            "rotation",
            Transform2D::rotation(std::f32::consts::FRAC_PI_4),
            PaintKind::Solid,
            Expect::Path,
        ),
        // Effective size over the 92px atlas cap: outlines.
        (
            "oversized scale",
            Transform2D::scaling(20.0, 20.0),
            PaintKind::Solid,
            Expect::Path,
        ),
        (
            "oversized font",
            Transform2D::identity(),
            PaintKind::BigSolid,
            Expect::Path,
        ),
    ];

    for (description, transform, paint_kind, expect) in cases {
        let (mut canvas, recorded, font) = make_canvas();
        let paint = match paint_kind {
            PaintKind::Solid => Paint::color(Color::black()).with_font(&[font]),
            PaintKind::BigSolid => Paint::color(Color::black()).with_font(&[font]).with_font_size(100.0),
            PaintKind::Gradient => {
                Paint::linear_gradient(0.0, 0.0, 100.0, 0.0, Color::black(), Color::white()).with_font(&[font])
            }
        };

        // A fresh canvas starts at the identity transform.
        canvas.set_transform(&transform);
        canvas.fill_text(10.0, 40.0, "Hello", &paint).unwrap();
        canvas.flush_to_output(());

        let commands = recorded.borrow();
        // Atlas rendering blits glyphs from a glyph texture; outline rendering only
        // ever emits plain path fills (note: atlas cache misses also emit path fills
        // while rasterizing into the atlas, so the glyph texture is the reliable
        // discriminator, not the absence of fills).
        let used_atlas = commands.iter().any(|c| !matches!(c.glyph_texture, GlyphTexture::None));
        let filled_outlines = commands.iter().any(|c| {
            matches!(c.glyph_texture, GlyphTexture::None)
                && matches!(
                    c.cmd_type,
                    CommandType::ConvexFill { .. } | CommandType::ConcaveFill { .. }
                )
        });

        match expect {
            Expect::Atlas => assert!(used_atlas, "expected atlas rendering for case: {description}"),
            Expect::Path => assert!(
                filled_outlines && !used_atlas,
                "expected outline rendering for case: {description} (used_atlas={used_atlas}, filled_outlines={filled_outlines})"
            ),
        }
    }
}

/// Collects the screen-space filled rectangles that text decoration emits.
///
/// A decoration line is a solid `ConvexFill` drawn to the screen with no glyph
/// texture. (Atlas glyph rasterization also emits `ConvexFill`s, but those run
/// while the render target is the atlas image, so tracking the active target
/// discriminates them.) Returns the vertical `[min_y, max_y]` span of each such
/// fill, in screen space.
#[cfg(all(test, feature = "textlayout"))]
fn recorded_decoration_spans(commands: &[renderer::Command], verts: &[renderer::Vertex]) -> Vec<(f32, f32)> {
    use crate::paint::GlyphTexture;
    use renderer::{CommandType, RenderTarget};

    let mut target = RenderTarget::Screen;
    let mut spans = Vec::new();

    for cmd in commands {
        match &cmd.cmd_type {
            CommandType::SetRenderTarget(new_target) => target = *new_target,
            CommandType::ConvexFill { .. }
                if target == RenderTarget::Screen && matches!(cmd.glyph_texture, GlyphTexture::None) =>
            {
                let mut min_y = f32::INFINITY;
                let mut max_y = f32::NEG_INFINITY;
                for drawable in &cmd.drawables {
                    if let Some((offset, len)) = drawable.fill_verts {
                        for v in &verts[offset..offset + len] {
                            min_y = min_y.min(v.y);
                            max_y = max_y.max(v.y);
                        }
                    }
                }
                if min_y.is_finite() {
                    spans.push((min_y, max_y));
                }
            }
            _ => {}
        }
    }

    spans
}

/// With a decoration enabled, `fill_text` emits exactly one extra solid rect per
/// enabled line, positioned from the font's own metrics: underline below the
/// baseline, strikethrough above it (through the text), overline near the ascent.
/// With no decoration, no such rect is emitted.
#[cfg(feature = "textlayout")]
#[test]
fn fill_text_emits_decoration_rects() {
    let make_canvas = || {
        let renderer = RecordingRenderer::default();
        let commands = renderer.last_commands.clone();
        let verts = renderer.last_verts.clone();
        let mut canvas = Canvas::new(renderer).unwrap();
        canvas.set_size(1000, 1000, 1.0);
        let font = canvas
            .add_font_mem(include_bytes!("../examples/assets/RobotoFlex-VariableFont.ttf"))
            .expect("failed to load test font");
        (canvas, commands, verts, font)
    };

    // Baseline::Alphabetic places the baseline exactly at the draw y, so the
    // metric offsets are easy to reason about. A pure-translation transform keeps
    // text on the cached-atlas path.
    let baseline_y = 200.0_f32;

    // Reference metrics for this font/size, in user space.
    let metrics = {
        let (canvas, _, _, font) = make_canvas();
        let paint = Paint::color(Color::black()).with_font(&[font]).with_font_size(40.0);
        canvas.measure_font(&paint).expect("metrics")
    };
    assert!(metrics.underline_thickness() > 0.0);
    assert!(metrics.strikeout_thickness() > 0.0);

    let base_paint = || {
        Paint::color(Color::black())
            .with_font_size(40.0)
            .with_text_baseline(Baseline::Alphabetic)
    };

    // No decoration: no screen-space solid rects at all.
    {
        let (mut canvas, commands, verts, font) = make_canvas();
        canvas
            .fill_text(50.0, baseline_y, "Hello", &base_paint().with_font(&[font]))
            .unwrap();
        canvas.flush_to_output(());
        let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
        assert!(spans.is_empty(), "expected no decoration rect, got {spans:?}");
    }

    // Underline: one rect, centered below the baseline at -underline_position.
    {
        let (mut canvas, commands, verts, font) = make_canvas();
        let paint = base_paint()
            .with_font(&[font])
            .with_text_decoration_lines(true, false, false);
        canvas.fill_text(50.0, baseline_y, "Hello", &paint).unwrap();
        canvas.flush_to_output(());
        let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
        assert_eq!(spans.len(), 1, "expected exactly one underline rect, got {spans:?}");
        let (min_y, max_y) = spans[0];
        let center = (min_y + max_y) / 2.0;
        let expected = baseline_y - metrics.underline_position();
        assert!(center > baseline_y, "underline should sit below the baseline");
        assert!(
            (center - expected).abs() <= 1.0,
            "underline center {center} should be near {expected}"
        );
        assert!(
            (max_y - min_y - metrics.underline_thickness()).abs() <= 1.0,
            "underline thickness {} should be near {}",
            max_y - min_y,
            metrics.underline_thickness()
        );
    }

    // Strikethrough: one rect, above the baseline at -strikeout_position.
    {
        let (mut canvas, commands, verts, font) = make_canvas();
        let paint = base_paint()
            .with_font(&[font])
            .with_text_decoration_lines(false, true, false);
        canvas.fill_text(50.0, baseline_y, "Hello", &paint).unwrap();
        canvas.flush_to_output(());
        let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
        assert_eq!(spans.len(), 1, "expected exactly one strikethrough rect, got {spans:?}");
        let (min_y, max_y) = spans[0];
        let center = (min_y + max_y) / 2.0;
        let expected = baseline_y - metrics.strikeout_position();
        assert!(center < baseline_y, "strikethrough should sit above the baseline");
        assert!(
            (center - expected).abs() <= 1.0,
            "strikethrough center {center} should be near {expected}"
        );
    }

    // Overline: one rect, above the ascent.
    {
        let (mut canvas, commands, verts, font) = make_canvas();
        let paint = base_paint()
            .with_font(&[font])
            .with_text_decoration_lines(false, false, true);
        canvas.fill_text(50.0, baseline_y, "Hello", &paint).unwrap();
        canvas.flush_to_output(());
        let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
        assert_eq!(spans.len(), 1, "expected exactly one overline rect, got {spans:?}");
        let (_, max_y) = spans[0];
        assert!(
            max_y <= baseline_y - metrics.ascender() + 1.0,
            "overline (bottom {max_y}) should sit at/above the ascent {}",
            baseline_y - metrics.ascender()
        );
    }

    // All three at once: three distinct rects.
    {
        let (mut canvas, commands, verts, font) = make_canvas();
        let paint = base_paint()
            .with_font(&[font])
            .with_text_decoration_lines(true, true, true);
        canvas.fill_text(50.0, baseline_y, "Hello", &paint).unwrap();
        canvas.flush_to_output(());
        let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
        assert_eq!(spans.len(), 3, "expected three decoration rects, got {spans:?}");
    }
}

/// Under a uniform-scale (scale-baked atlas) transform, the decoration rect must
/// still line up with the glyphs: it is emitted in user space and run through the
/// same canvas transform, so its screen-space center scales with the baseline.
#[cfg(feature = "textlayout")]
#[test]
fn decoration_rect_tracks_scaled_atlas_transform() {
    let renderer = RecordingRenderer::default();
    let commands = renderer.last_commands.clone();
    let verts = renderer.last_verts.clone();
    let mut canvas = Canvas::new(renderer).unwrap();
    canvas.set_size(2000, 2000, 1.0);
    let font = canvas
        .add_font_mem(include_bytes!("../examples/assets/RobotoFlex-VariableFont.ttf"))
        .expect("failed to load test font");

    let baseline_y = 150.0_f32;
    let scale = 2.0_f32;

    let metrics = {
        let paint = Paint::color(Color::black()).with_font(&[font]).with_font_size(24.0);
        canvas.measure_font(&paint).expect("metrics")
    };

    let paint = Paint::color(Color::black())
        .with_font(&[font])
        .with_font_size(24.0)
        .with_text_baseline(Baseline::Alphabetic)
        .with_text_decoration_lines(true, false, false);

    canvas.scale(scale, scale);
    canvas.fill_text(40.0, baseline_y, "Scaled", &paint).unwrap();
    canvas.flush_to_output(());

    let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
    assert_eq!(spans.len(), 1, "expected one underline rect, got {spans:?}");
    let (min_y, max_y) = spans[0];
    let center = (min_y + max_y) / 2.0;
    // User-space underline center is baseline - underline_position; on screen the
    // whole thing is multiplied by the canvas scale.
    let expected = (baseline_y - metrics.underline_position()) * scale;
    assert!(
        (center - expected).abs() <= 2.0,
        "scaled underline center {center} should be near {expected}"
    );
}

/// The decoration baseline must be the shared run baseline, independent of the
/// first drawable glyph's GPOS y-offset. `layout` bakes that offset into
/// `glyph.y`, so a run beginning with a combining mark (non-zero `offset_y`)
/// would otherwise drag every decoration line up or down with the mark.
///
/// This unit-tests `run_baseline` — the exact policy `draw_text` uses to anchor
/// decorations — with a synthetic run whose first glyph carries an `offset_y`.
/// The captured baseline must match the run baseline computed without the offset
/// (i.e. the second, zero-offset glyph's `y`), not the first glyph's shifted `y`.
#[cfg(feature = "textlayout")]
#[test]
fn run_baseline_ignores_leading_glyph_offset() {
    // A real FontId is needed to populate the synthetic glyphs; `run_baseline`
    // never reads it, but ShapedGlyph requires one.
    let text_context = TextContext::default();
    let font_id = text_context
        .add_font_mem(include_bytes!("../examples/assets/RobotoFlex-VariableFont.ttf"))
        .expect("failed to load test font");

    // The shared run baseline both glyphs are positioned against.
    let run_y = 200.0_f32;

    let make_glyph = |c: char, offset_y: f32| text::ShapedGlyph {
        // `layout` stores `glyph.y = run_baseline + glyph.offset_y`; mirror that.
        x: 0.0,
        y: run_y + offset_y,
        c,
        byte_index: 0,
        font_id,
        glyph_id: 0,
        width: 0.0,
        height: 0.0,
        advance_x: 0.0,
        advance_y: 0.0,
        offset_x: 0.0,
        offset_y,
    };

    // First drawable glyph carries a large positive y-offset (a combining mark
    // pushed below the baseline); the second sits exactly on the baseline.
    let offset = 15.0_f32;
    let with_offset = [make_glyph('a', offset), make_glyph('b', 0.0)];
    // Same run, but the leading glyph has no offset.
    let without_offset = [make_glyph('a', 0.0), make_glyph('b', 0.0)];

    let captured = run_baseline(&with_offset).expect("run has a drawable glyph");
    let reference = run_baseline(&without_offset).expect("run has a drawable glyph");

    // The capture must equal the true run baseline, not the shifted first glyph.
    assert_eq!(
        captured, run_y,
        "captured baseline {captured} should equal the shared run baseline {run_y}"
    );
    assert_eq!(
        captured, reference,
        "leading glyph offset must not shift the captured baseline ({captured} vs {reference})"
    );
    assert!(
        (captured - with_offset[0].y).abs() > offset - 1.0,
        "captured baseline {captured} must not follow the offset glyph y {}",
        with_offset[0].y
    );

    // A leading control glyph (skipped by the drawable filter) must not become
    // the baseline source either.
    let with_control = [make_glyph('\n', 99.0), make_glyph('b', 0.0)];
    assert_eq!(
        run_baseline(&with_control),
        Some(run_y),
        "control glyphs must be skipped when capturing the baseline"
    );

    // Empty / all-control runs have no baseline.
    assert_eq!(run_baseline(&[]), None);
    assert_eq!(run_baseline(&[make_glyph('\t', 0.0)]), None);
}

/// Rebuilds a sfnt/TrueType font byte buffer with the named 4-byte tables
/// removed, so the fallback metric paths can be exercised on real assets.
#[cfg(all(test, feature = "textlayout"))]
fn font_without_tables(data: &[u8], drop_tags: &[&[u8; 4]]) -> Vec<u8> {
    let read_u16 = |buf: &[u8], at: usize| u16::from_be_bytes([buf[at], buf[at + 1]]);
    let read_u32 =
        |buf: &[u8], at: usize| u32::from_be_bytes([buf[at], buf[at + 1], buf[at + 2], buf[at + 3]]) as usize;

    let num_tables = read_u16(data, 4) as usize;

    // Collect (tag, offset, length) for the tables we keep, in directory order.
    let mut kept: Vec<([u8; 4], usize, usize)> = Vec::new();
    for i in 0..num_tables {
        let rec = 12 + i * 16;
        let tag = [data[rec], data[rec + 1], data[rec + 2], data[rec + 3]];
        if drop_tags.iter().any(|d| **d == tag) {
            continue;
        }
        let offset = read_u32(data, rec + 8);
        let length = read_u32(data, rec + 12);
        kept.push((tag, offset, length));
    }

    let new_num = kept.len();
    let mut out = Vec::new();
    // Offset table header: keep the original sfnt version, fix up the table count
    // and the binary-search hint fields for the new count.
    out.extend_from_slice(&data[0..4]);
    out.extend_from_slice(&(new_num as u16).to_be_bytes());
    let max_pow2: u16 = 1 << (15 - (new_num.max(1) as u16).leading_zeros());
    out.extend_from_slice(&(max_pow2 * 16).to_be_bytes());
    out.extend_from_slice(&(15 - max_pow2.leading_zeros() as u16).to_be_bytes());
    out.extend_from_slice(&((new_num as u16 * 16).wrapping_sub(max_pow2 * 16)).to_be_bytes());

    let mut data_offset = 12 + new_num * 16;
    let mut records = Vec::new();
    let mut blobs = Vec::new();
    for (tag, offset, length) in kept {
        let padded = (length + 3) & !3;
        let mut blob = data[offset..offset + length].to_vec();
        blob.resize(padded, 0);
        let mut rec = Vec::new();
        rec.extend_from_slice(&tag);
        rec.extend_from_slice(&0u32.to_be_bytes()); // checksum (ignored by ttf-parser)
        rec.extend_from_slice(&(data_offset as u32).to_be_bytes());
        rec.extend_from_slice(&(length as u32).to_be_bytes());
        records.push(rec);
        blobs.push(blob);
        data_offset += padded;
    }
    for rec in records {
        out.extend_from_slice(&rec);
    }
    for blob in blobs {
        out.extend_from_slice(&blob);
    }
    out
}

/// A font without an OS/2 table (so no strikeout metric) and without a post
/// table (so no underline metric) must still yield sensible, finite, positive
/// decoration metrics via the ascender/descender-derived fallbacks — and never
/// panic when drawing.
#[cfg(feature = "textlayout")]
#[test]
fn decoration_metrics_fall_back_without_os2_and_post() {
    let original = include_bytes!("../examples/assets/amiri-regular.ttf");

    // Sanity: ttf-parser sees no strikeout/underline once the tables are gone.
    let stripped = font_without_tables(original, &[b"OS/2", b"post"]);
    let face = ttf_parser::Face::parse(&stripped, 0).expect("stripped font should still parse");
    assert!(
        face.strikeout_metrics().is_none(),
        "OS/2 strikeout should be absent after stripping"
    );
    assert!(
        face.underline_metrics().is_none(),
        "post underline should be absent after stripping"
    );

    let text_context = TextContext::default();
    let font_id = text_context.add_font_mem(&stripped).expect("stripped font should load");
    let paint = Paint::default().with_font(&[font_id]).with_font_size(20.0);

    let metrics = text_context.measure_font(&paint).expect("metrics");

    assert!(
        metrics.strikeout_thickness() > 0.0 && metrics.strikeout_thickness().is_finite(),
        "fallback strikeout thickness must be positive and finite, got {}",
        metrics.strikeout_thickness()
    );
    assert!(
        metrics.strikeout_position() > 0.0 && metrics.strikeout_position().is_finite(),
        "fallback strikeout should sit above the baseline, got {}",
        metrics.strikeout_position()
    );
    assert!(
        metrics.underline_thickness() > 0.0 && metrics.underline_thickness().is_finite(),
        "fallback underline thickness must be positive and finite, got {}",
        metrics.underline_thickness()
    );
    assert!(
        metrics.underline_position() < 0.0 && metrics.underline_position().is_finite(),
        "fallback underline should sit below the baseline, got {}",
        metrics.underline_position()
    );

    // Drawing with the fallback font must not panic and must still emit the rects.
    let renderer = RecordingRenderer::default();
    let commands = renderer.last_commands.clone();
    let verts = renderer.last_verts.clone();
    let mut canvas = Canvas::new(renderer).unwrap();
    canvas.set_size(1000, 1000, 1.0);
    let font = canvas
        .add_font_mem(&font_without_tables(original, &[b"OS/2", b"post"]))
        .expect("stripped font should load into canvas");
    let paint = Paint::color(Color::black())
        .with_font(&[font])
        .with_font_size(20.0)
        .with_text_baseline(Baseline::Alphabetic)
        .with_text_decoration_lines(true, true, false);
    canvas.fill_text(20.0, 100.0, "fallback", &paint).unwrap();
    canvas.flush_to_output(());
    let spans = recorded_decoration_spans(&commands.borrow(), &verts.borrow());
    assert_eq!(
        spans.len(),
        2,
        "expected underline + strikethrough rects, got {spans:?}"
    );
}
