//! Shared helpers for the headless OpenGL tests: a surfaceless EGL context
//! (no window or display server; Mesa's llvmpipe works) and an offscreen
//! render that returns tightly packed RGBA8 rows, top row first — the same
//! contract as `common::render_rgba` for the WGPU tests.
//!
//! Tests run once per [`GlFlavor`] the host can create. Mesa reports its
//! newest GLES version whatever was asked for, so the GLES 2 flavor (and the
//! backend's `is_opengles_2_0` paths) only runs under
//! `MESA_GLES_VERSION_OVERRIDE=2.0`, which in turn hides GLES 3; a full pass
//! is one run with the variable and one without.
//!
//! A flavor that cannot be created is skipped. `FEMTOVG_REQUIRE_GL` turns
//! skips into failures, as `FEMTOVG_REQUIRE_GPU` does for the WGPU tests: a
//! comma-separated list of flavors that must run (`desktop`, `gles3`,
//! `gles2`), or `1`/`any` to require at least one.
//!
//! GL errors fail the test that caused them: the context is a debug context
//! whose KHR_debug output is collected and checked after every render.
#![allow(dead_code)]

use std::cell::RefCell;
use std::ffi::CStr;

use femtovg::{renderer::OpenGl, Canvas, Color};
use glow::HasContext;
use glutin::api::egl::{device::Device, display::Display};
use glutin::config::{Api, ConfigSurfaceTypes, ConfigTemplateBuilder};
use glutin::context::{ContextApi, ContextAttributesBuilder, GlProfile, Version};
use glutin::display::GlDisplay;
use glutin::prelude::PossiblyCurrentGlContext;

/// The context flavors the GL backend ships to: desktop GL (core profile),
/// OpenGL ES 3 (most mobile/embedded GPUs) and OpenGL ES 2 (e.g. VideoCore
/// IV, where the backend takes its `is_opengles_2_0` code paths).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GlFlavor {
    DesktopCore,
    Gles3,
    Gles2,
}

pub const ALL_FLAVORS: [GlFlavor; 3] = [GlFlavor::DesktopCore, GlFlavor::Gles3, GlFlavor::Gles2];

impl GlFlavor {
    fn env_name(self) -> &'static str {
        match self {
            GlFlavor::DesktopCore => "desktop",
            GlFlavor::Gles3 => "gles3",
            GlFlavor::Gles2 => "gles2",
        }
    }
}

/// The flavors `FEMTOVG_REQUIRE_GL` names, or `Some(empty)` for "at least one".
fn gl_requirement() -> Option<Vec<String>> {
    let value = std::env::var("FEMTOVG_REQUIRE_GL").ok()?;
    let value = value.trim().to_ascii_lowercase();
    match value.as_str() {
        "" => None,
        "1" | "true" | "any" => Some(Vec::new()),
        list => Some(list.split(',').map(|name| name.trim().to_owned()).collect()),
    }
}

thread_local! {
    /// GL errors the driver reported through KHR_debug on this thread. The
    /// callback runs synchronously on the thread that issued the failing call,
    /// so each test thread sees exactly its own context's errors.
    static GL_ERRORS: RefCell<Vec<String>> = const { RefCell::new(Vec::new()) };
}

fn skip(flavor: GlFlavor, why: String) -> Option<HeadlessGl> {
    if let Some(required) = gl_requirement() {
        assert!(
            !required.iter().any(|name| name == flavor.env_name()),
            "FEMTOVG_REQUIRE_GL requires {} but {why}",
            flavor.env_name()
        );
    }
    eprintln!("skipping {flavor:?}: {why}");
    None
}

/// A current, surfaceless EGL context with an RGBA8 + depth/stencil
/// framebuffer object bound as the canvas "screen".
pub struct HeadlessGl {
    // Field order matters for drop: the GL objects die with the context.
    gl: glow::Context,
    fbo: glow::Framebuffer,
    renderbuffers: [glow::Renderbuffer; 2],
    width: u32,
    height: u32,
    pub flavor: GlFlavor,
    pub version: String,
    _context: glutin::api::egl::context::PossiblyCurrentContext,
    _display: Display,
}

impl HeadlessGl {
    pub fn new(flavor: GlFlavor, width: u32, height: u32) -> Option<Self> {
        let devices = match Device::query_devices() {
            Ok(devices) => devices.collect::<Vec<_>>(),
            Err(err) => return skip(flavor, format!("no EGL devices ({err})")),
        };
        // Prefer a software device: its output is deterministic across hosts,
        // and on a headless box it is often the only one that works.
        let device = devices
            .iter()
            .find(|d| d.extensions().contains("EGL_MESA_device_software"))
            .or(devices.first());
        let Some(device) = device else {
            return skip(flavor, "no EGL devices".into());
        };
        let display = match unsafe { Display::with_device(device, None) } {
            Ok(display) => display,
            Err(err) => return skip(flavor, format!("EGL display creation failed ({err})")),
        };

        let (api, context_api, profile) = match flavor {
            GlFlavor::DesktopCore => (
                Api::OPENGL,
                ContextApi::OpenGl(Some(Version::new(3, 3))),
                Some(GlProfile::Core),
            ),
            GlFlavor::Gles3 => (Api::GLES3, ContextApi::Gles(Some(Version::new(3, 0))), None),
            GlFlavor::Gles2 => (Api::GLES2, ContextApi::Gles(Some(Version::new(2, 0))), None),
        };
        let template = ConfigTemplateBuilder::new()
            .with_surface_type(ConfigSurfaceTypes::empty())
            .with_api(api)
            .build();
        let config = match unsafe { display.find_configs(template) }.map(|mut c| c.next()) {
            Ok(Some(config)) => config,
            Ok(None) => return skip(flavor, format!("no EGL config for {flavor:?}")),
            Err(err) => return skip(flavor, format!("EGL config query for {flavor:?} failed ({err})")),
        };
        let mut attributes = ContextAttributesBuilder::new()
            .with_context_api(context_api)
            .with_debug(true);
        if let Some(profile) = profile {
            attributes = attributes.with_profile(profile);
        }
        let context = match unsafe { display.create_context(&config, &attributes.build(None)) } {
            Ok(context) => context,
            Err(err) => return skip(flavor, format!("{flavor:?} context creation failed ({err})")),
        };
        let context = match context.make_current_surfaceless() {
            Ok(context) => context,
            Err(err) => return skip(flavor, format!("{flavor:?} surfaceless make-current failed ({err})")),
        };
        debug_assert!(context.is_current());

        let mut gl = unsafe { glow::Context::from_loader_function_cstr(|s: &CStr| display.get_proc_address(s).cast()) };
        // The backend checks glGetError only in debug builds and then merely
        // logs, so an invalid call would pass a test unnoticed. Route the
        // driver's own error reports into the test instead.
        let debug_output = gl.supports_debug();
        if debug_output {
            unsafe {
                gl.enable(glow::DEBUG_OUTPUT);
                gl.enable(glow::DEBUG_OUTPUT_SYNCHRONOUS);
                gl.debug_message_callback(|_source, kind, id, severity, message| {
                    if kind == glow::DEBUG_TYPE_ERROR || severity == glow::DEBUG_SEVERITY_HIGH {
                        let entry = format!("GL debug error (id {id}): {message}");
                        GL_ERRORS.with(|errors| errors.borrow_mut().push(entry));
                    }
                });
            }
        }
        let version = unsafe { gl.get_parameter_string(glow::VERSION) };
        // Mesa hands back its highest compatible ES version when 2.0 is
        // requested; the backend keys its ES 2 paths off the version string.
        if flavor == GlFlavor::Gles2 && !version.starts_with("OpenGL ES 2.") {
            return skip(
                flavor,
                format!("asked for OpenGL ES 2 but got \"{version}\" (Mesa: set MESA_GLES_VERSION_OVERRIDE=2.0)"),
            );
        }

        let (fbo, renderbuffers) = unsafe {
            let color = gl.create_renderbuffer().expect("color renderbuffer");
            gl.bind_renderbuffer(glow::RENDERBUFFER, Some(color));
            gl.renderbuffer_storage(glow::RENDERBUFFER, glow::RGBA8, width as i32, height as i32);
            let depth_stencil = gl.create_renderbuffer().expect("depth/stencil renderbuffer");
            gl.bind_renderbuffer(glow::RENDERBUFFER, Some(depth_stencil));
            gl.renderbuffer_storage(glow::RENDERBUFFER, glow::DEPTH24_STENCIL8, width as i32, height as i32);
            gl.bind_renderbuffer(glow::RENDERBUFFER, None);

            let fbo = gl.create_framebuffer().expect("framebuffer");
            gl.bind_framebuffer(glow::FRAMEBUFFER, Some(fbo));
            gl.framebuffer_renderbuffer(
                glow::FRAMEBUFFER,
                glow::COLOR_ATTACHMENT0,
                glow::RENDERBUFFER,
                Some(color),
            );
            // ES 2 has no combined attachment point: attach the packed buffer twice.
            for attachment in [glow::DEPTH_ATTACHMENT, glow::STENCIL_ATTACHMENT] {
                gl.framebuffer_renderbuffer(glow::FRAMEBUFFER, attachment, glow::RENDERBUFFER, Some(depth_stencil));
            }
            let status = gl.check_framebuffer_status(glow::FRAMEBUFFER);
            assert_eq!(
                status,
                glow::FRAMEBUFFER_COMPLETE,
                "{flavor:?} test framebuffer incomplete"
            );
            (fbo, [color, depth_stencil])
        };

        static ANNOUNCE: std::sync::Once = std::sync::Once::new();
        ANNOUNCE.call_once(|| {
            let renderer = unsafe { gl.get_parameter_string(glow::RENDERER) };
            eprintln!("EGL device renderer: {renderer} (KHR_debug error capture: {debug_output})");
        });

        Some(Self {
            gl,
            fbo,
            renderbuffers,
            width,
            height,
            flavor,
            version,
            _context: context,
            _display: display,
        })
    }

    /// A femtovg renderer on this context whose "screen" is the test FBO.
    pub fn renderer(&self) -> OpenGl {
        let mut renderer = unsafe {
            OpenGl::new_from_function_cstr(|s| self._display.get_proc_address(s).cast()).expect("OpenGl renderer")
        };
        renderer.set_screen_target(Some(self.fbo));
        renderer
    }

    /// Reads the test FBO back as RGBA8 rows, top row first. GL's origin is
    /// the bottom-left, and the backend draws the screen y-down into it (the
    /// canvas's top row is the framebuffer's last row), so rows are reversed.
    pub fn read_rgba(&self) -> Vec<u8> {
        let (w, h) = (self.width as usize, self.height as usize);
        let mut bottom_up = vec![0u8; w * h * 4];
        unsafe {
            // Anything the renderer left in the error flag is a renderer bug,
            // not a readback failure: report it as such.
            let pending = self.gl.get_error();
            assert_eq!(
                pending,
                glow::NO_ERROR,
                "{:?}: GL error 0x{pending:x} pending after rendering",
                self.flavor
            );
            self.gl.bind_framebuffer(glow::FRAMEBUFFER, Some(self.fbo));
            self.gl.pixel_store_i32(glow::PACK_ALIGNMENT, 1);
            self.gl.read_pixels(
                0,
                0,
                w as i32,
                h as i32,
                glow::RGBA,
                glow::UNSIGNED_BYTE,
                glow::PixelPackData::Slice(Some(&mut bottom_up)),
            );
            let err = self.gl.get_error();
            assert_eq!(err, glow::NO_ERROR, "glReadPixels failed: 0x{err:x}");
        }
        bottom_up.chunks_exact(w * 4).rev().flatten().copied().collect()
    }

    /// Renders `draw` on a fresh canvas cleared to `clear` and returns the
    /// RGBA8 pixels, rows tightly packed, top row first.
    pub fn render_rgba(&self, clear: Color, draw: impl FnOnce(&mut Canvas<OpenGl>)) -> Vec<u8> {
        let mut canvas = Canvas::new(self.renderer()).expect("canvas");
        canvas.set_size(self.width, self.height, 1.0);
        canvas.clear_rect(0, 0, self.width, self.height, clear);
        draw(&mut canvas);
        canvas.flush();
        drop(canvas);
        // The driver's messages name the failing call; check them before the
        // readback's own glGetError, which can only report a code.
        self.assert_no_gl_errors();
        self.read_rgba()
    }

    /// Fails the test if the driver reported any GL error since the last call.
    pub fn assert_no_gl_errors(&self) {
        let errors = GL_ERRORS.with(|errors| std::mem::take(&mut *errors.borrow_mut()));
        assert!(
            errors.is_empty(),
            "{:?}: the renderer issued invalid GL calls:\n{}",
            self.flavor,
            errors.join("\n")
        );
    }
}

impl Drop for HeadlessGl {
    fn drop(&mut self) {
        unsafe {
            self.gl.delete_framebuffer(self.fbo);
            for rb in self.renderbuffers {
                self.gl.delete_renderbuffer(rb);
            }
        }
    }
}

/// Runs `f` once per GL flavor this host can create, returning how many ran.
/// The ES 2 flavor is only exercised where the driver reports ES 2 exactly.
pub fn for_each_flavor(width: u32, height: u32, mut f: impl FnMut(&HeadlessGl)) -> usize {
    let mut ran = 0;
    for flavor in ALL_FLAVORS {
        if let Some(gl) = HeadlessGl::new(flavor, width, height) {
            eprintln!("-- {flavor:?}: {}", gl.version);
            f(&gl);
            ran += 1;
        }
    }
    assert!(
        ran > 0 || gl_requirement().is_none(),
        "FEMTOVG_REQUIRE_GL is set but no GL flavor could be created"
    );
    ran
}
