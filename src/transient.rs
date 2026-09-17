//! The pool of transient offscreen images: layer backing stores, filtered
//! results, filter-chain scratches and shadow coverage.
//!
//! A transient is live from its acquire until the pool deletes it. Between
//! a release and the next acquire it is free for any acquire of the same
//! size and flags, so a frame's peak transient memory is what is live at
//! once - nesting depth times layer size - not the sum over every layer,
//! chain and shadow it draws. The flush keeps the released transients for
//! the frames to come instead of deleting them: a frame that draws the same
//! layers and shadows as the last one - every frame of an animation at one
//! zoom - creates no image at all, and a store's render-target companions
//! (the wgpu backend's stencil buffer per texture) survive with it. What no
//! frame has taken for [`RETAIN_FRAMES`] consecutive frames is deleted at
//! the flush, and what this frame has not taken is evicted, least recently
//! used first, when an acquire would otherwise pass the budget: the budget
//! bounds the live transients with the retained ones counted, and retention
//! never costs a layer its admission. Deleting only what no recorded
//! command reads is what keeps this safe: a transient taken or released this
//! frame may be read by a command the flush has yet to execute, so it lives
//! at least until then; one untouched since the last flush is referenced by
//! nothing. A layer open across the flush holds its images: they stay live,
//! in use and out of the free list until the layer ends or is discarded.
//! Reuse needs no synchronization: commands execute in order, so a later
//! layer drawing into an image an earlier layer's composite reads is
//! well-defined, and each consumer clears or fully overwrites the image it
//! takes.

use crate::image::ImageStore;
use crate::renderer::Renderer;
use crate::{ErrorKind, ImageFlags, ImageId, ImageInfo, PixelFormat};

/// Default cap on live transient memory. A Raspberry Pi Zero's GPU share is
/// 64-128 MB in total, so integrations targeting it set a smaller budget; see
/// [`crate::Canvas::set_transient_image_budget`].
pub(crate) const DEFAULT_BUDGET: usize = 256 * 1024 * 1024;

/// Consecutive frames a released transient may go untaken before the flush
/// deletes it: a store no frame took for this many frames is gone at the
/// last of them. Two keeps a layer drawn every other frame, and a size class
/// a zoom step leaves and returns to, from re-creating their stores; under a
/// continuous zoom, where every frame is a new size class, it holds the two
/// previous frames' stores alongside the current frame's until the budget
/// evicts them.
pub(crate) const RETAIN_FRAMES: u64 = 2;

/// Layer stores round up to this many pixels per axis. Sibling layers whose
/// scissors or blur reaches differ by a few pixels then request the same
/// size and share one pooled store instead of each holding its own; the cost
/// is at most 63 px per axis (a tenth of a 1080 px layer) and the extra area
/// is clipped away at the composite.
pub(crate) const LAYER_GRANULARITY: usize = 64;

/// Shadow coverage rounds more finely. Shadows are many, small and
/// differently sized (text, icons), and their coverage images are cleared and
/// blurred over their whole area: modelled on a frame of 600 glyph-sized
/// shadows, exact sizes allocate 650 images per frame, 8 px rounding 60 (for
/// 18 % more fill), 64 px rounding 8 (for 235 % more fill).
pub(crate) const SHADOW_GRANULARITY: usize = 8;

pub(crate) fn round_up(n: usize, granularity: usize) -> usize {
    n.div_ceil(granularity) * granularity
}

/// A live transient and when a frame last touched it.
#[derive(Debug)]
pub(crate) struct Transient {
    pub(crate) id: ImageId,
    /// The frame of its last acquire or release: the last frame whose
    /// commands may read it.
    last_used: u64,
    bytes: usize,
}

#[derive(Debug)]
pub(crate) struct TransientPool {
    /// Every live transient: taken this frame, held by an open layer, or
    /// retained from an earlier frame.
    pub(crate) images: Vec<Transient>,
    /// Transients whose last consumer command has been recorded; a subset of
    /// `images`, taken by the next acquire of the same size and flags, this
    /// frame or a later one.
    pub(crate) free: Vec<ImageId>,
    /// Bytes held by `images`, against `budget`.
    bytes: usize,
    budget: usize,
    /// Flushes so far: the current frame, stamped on every acquire and
    /// release.
    frame: u64,
}

impl TransientPool {
    pub(crate) fn new(budget: usize) -> Self {
        Self {
            images: Vec::new(),
            free: Vec::new(),
            bytes: 0,
            budget,
            frame: 0,
        }
    }

    pub(crate) fn bytes(&self) -> usize {
        self.bytes
    }

    /// Takes effect at the next acquire or flush, which evict down to it.
    pub(crate) fn set_budget(&mut self, bytes: usize) {
        self.budget = bytes;
    }

    /// A pooled image of exactly `width` x `height` with `flags` if one is
    /// free, otherwise a fresh RGBA8 image counted against the budget - after
    /// evicting retained images this frame has not touched, if that is what
    /// it takes to fit.
    pub(crate) fn acquire<T: Renderer>(
        &mut self,
        images: &mut ImageStore<T::Image>,
        renderer: &mut T,
        width: usize,
        height: usize,
        flags: ImageFlags,
    ) -> Result<ImageId, ErrorKind> {
        let reusable = self.free.iter().position(|&id| {
            images
                .info(id)
                .is_some_and(|info| info.width() == width && info.height() == height && info.flags() == flags)
        });
        if let Some(at) = reusable {
            let id = self.free.swap_remove(at);
            self.touch(id);
            // A budget lowered since the last flush is enforced here too.
            self.evict_untouched(images, renderer, self.budget);
            return Ok(id);
        }
        let bytes = width.saturating_mul(height).saturating_mul(4);
        if bytes > self.budget {
            return Err(ErrorKind::TransientImageBudgetExceeded);
        }
        self.evict_untouched(images, renderer, self.budget - bytes);
        if self.bytes.saturating_add(bytes) > self.budget {
            return Err(ErrorKind::TransientImageBudgetExceeded);
        }
        let id = images.alloc(renderer, ImageInfo::new(flags, width, height, PixelFormat::Rgba8))?;
        self.bytes = self.bytes.saturating_add(bytes);
        self.images.push(Transient {
            id,
            last_used: self.frame,
            bytes,
        });
        Ok(id)
    }

    /// Returns an image to the pool once every command that reads it has
    /// been recorded. Whoever takes it next must clear or fully overwrite it,
    /// as layers and filter passes do.
    pub(crate) fn release(&mut self, id: ImageId) {
        debug_assert!(
            self.images.iter().any(|t| t.id == id),
            "released image is not a transient"
        );
        debug_assert!(!self.free.contains(&id), "transient released twice");
        self.touch(id);
        self.free.push(id);
    }

    /// The flush. Retains every released transient for the frames to come,
    /// deletes those no frame took for [`RETAIN_FRAMES`] frames and any never
    /// released (nothing will release it now), then evicts the least recently
    /// used down to the budget should it have been lowered. The images in
    /// `held` (of layers still open across the flush) stay live and in use.
    pub(crate) fn end_frame<T: Renderer>(
        &mut self,
        images: &mut ImageStore<T::Image>,
        renderer: &mut T,
        held: &[ImageId],
    ) {
        self.frame += 1;
        let stale: Vec<ImageId> = self
            .images
            .iter()
            .filter(|t| !held.contains(&t.id))
            .filter(|t| !self.free.contains(&t.id) || self.frame - t.last_used > RETAIN_FRAMES)
            .map(|t| t.id)
            .collect();
        for id in stale {
            self.delete(images, renderer, id);
        }
        self.evict_untouched(images, renderer, self.budget);
    }

    fn touch(&mut self, id: ImageId) {
        if let Some(transient) = self.images.iter_mut().find(|t| t.id == id) {
            transient.last_used = self.frame;
        }
    }

    /// Deletes free transients no command of this frame reads - those
    /// untouched since the last flush - least recently used first, until the
    /// pool holds at most `target` bytes or none is left.
    fn evict_untouched<T: Renderer>(&mut self, images: &mut ImageStore<T::Image>, renderer: &mut T, target: usize) {
        if self.bytes <= target {
            return;
        }
        let mut candidates: Vec<(u64, ImageId)> = self
            .images
            .iter()
            .filter(|t| t.last_used < self.frame && self.free.contains(&t.id))
            .map(|t| (t.last_used, t.id))
            .collect();
        candidates.sort_unstable();
        for (_, id) in candidates {
            if self.bytes <= target {
                break;
            }
            self.delete(images, renderer, id);
        }
    }

    fn delete<T: Renderer>(&mut self, images: &mut ImageStore<T::Image>, renderer: &mut T, id: ImageId) {
        if let Some(at) = self.images.iter().position(|t| t.id == id) {
            let transient = self.images.swap_remove(at);
            self.bytes = self.bytes.saturating_sub(transient.bytes);
        }
        if let Some(at) = self.free.iter().position(|&free| free == id) {
            self.free.swap_remove(at);
        }
        images.remove(renderer, id);
    }
}
