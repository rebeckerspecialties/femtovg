//! Fills thinner than a pixel, drawn through coverage masks. A fill's fringe
//! antialiases each edge for itself, so two edges closer than a pixel each
//! add their ramp: a sliver a sixth of a pixel wide comes out at about a
//! pixel and a half of ink for each pixel of its length (#327). Such a fill
//! is rasterized on the CPU instead, by the clip masks' exact coverage, into
//! one atlas, and drawn as a quad that reads its mask as a glyph's is read:
//! the paint, the scissor and every clip apply to it as they do to text.
//! Skia's Graphite does the same for small paths (`RasterPathAtlas`, at
//! most 256 of them a flush).

use std::collections::HashMap;

use super::mask::MaskKey;
use crate::{text::Atlas, ImageId};

/// A fill is thin when twice its area over its perimeter - its mean width -
/// is under this, in device pixels.
pub(crate) const THIN_FILL_WIDTH: f32 = 1.0;

/// The most pixels a thin fill's bounds may span to be drawn through a mask.
pub(crate) const THIN_FILL_SPAN: f32 = 65_536.0;

/// The atlas's side in pixels: a byte each, four megabytes, more than the
/// thin fills of any corpus frame at 1080p took (1.9 MB).
pub(crate) const ATLAS_SIZE: usize = 2048;

/// The most masks rasterized in a frame, as Skia's 256 a flush: past it a
/// thin fill is filled as any other, so that a scene whose thin fills move
/// every frame does not rasterize and upload them all again each time.
const MASKS_A_FRAME: usize = 256;

/// The most requests remembered bit for bit.
const ASKED_KEPT: usize = 4096;

/// Where a mask lies in the atlas and the rect of the target it covers.
#[derive(Clone, Copy, Debug)]
pub(crate) struct PlacedMask {
    pub(crate) atlas: [u32; 2],
    pub(crate) rect: [i32; 4],
}

/// The atlas and what it holds.
#[derive(Debug)]
pub(crate) struct FillMasks {
    enabled: bool,
    pub(crate) image: Option<ImageId>,
    packer: Atlas,
    masks: HashMap<MaskKey, [u32; 2]>,
    /// The masks of requests asked for bit for bit as before: the path's
    /// words, the transform and the target's size.
    asked: HashMap<Vec<u32>, PlacedMask>,
    made: usize,
    full: bool,
    pub(crate) coverage: super::coverage::Coverage,
    /// Every mask rasterized, for the tests.
    #[cfg(test)]
    pub(crate) rasterized: usize,
}

impl Default for FillMasks {
    fn default() -> Self {
        Self {
            enabled: true,
            image: None,
            packer: Atlas::new(ATLAS_SIZE, ATLAS_SIZE),
            masks: HashMap::new(),
            asked: HashMap::new(),
            made: 0,
            full: false,
            coverage: Default::default(),
            #[cfg(test)]
            rasterized: 0,
        }
    }
}

impl FillMasks {
    pub(crate) fn enabled(&self) -> bool {
        self.enabled
    }

    pub(crate) fn set_enabled(&mut self, enabled: bool) {
        self.enabled = enabled;
    }

    pub(crate) fn asked(&self, request: &[u32]) -> Option<PlacedMask> {
        self.asked.get(request).copied()
    }

    pub(crate) fn remember(&mut self, request: Vec<u32>, mask: PlacedMask) {
        // A scene moved by whole pixels finds its masks by their outlines,
        // and asks anew every frame.
        if self.asked.len() >= ASKED_KEPT {
            self.asked.clear();
        }
        self.asked.insert(request, mask);
    }

    pub(crate) fn get(&self, key: &MaskKey) -> Option<[u32; 2]> {
        self.masks.get(key).copied()
    }

    /// A place in the atlas for a new mask of `size`, if the frame has not
    /// made its share of masks and the atlas has room; a mask that does not
    /// fit marks the atlas full, to start over once the frame is drawn.
    pub(crate) fn place(&mut self, size: [usize; 2]) -> Option<[u32; 2]> {
        if self.made >= MASKS_A_FRAME || self.full || size[0] > ATLAS_SIZE || size[1] > ATLAS_SIZE {
            return None;
        }
        let Some((x, y)) = self.packer.add_rect(size[0], size[1]) else {
            self.full = true;
            return None;
        };
        self.made += 1;
        #[cfg(test)]
        {
            self.rasterized += 1;
        }
        Some([x as u32, y as u32])
    }

    pub(crate) fn keep(&mut self, key: MaskKey, at: [u32; 2]) {
        self.masks.insert(key, at);
    }

    /// The frame is drawn: an atlas that filled starts over, its masks made
    /// again as the frames that follow ask for them.
    pub(crate) fn end_frame(&mut self) {
        self.made = 0;
        if self.full {
            self.full = false;
            self.packer.reset(ATLAS_SIZE, ATLAS_SIZE);
            self.masks.clear();
            self.asked.clear();
        }
    }
}
