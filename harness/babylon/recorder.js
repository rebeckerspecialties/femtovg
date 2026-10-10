// Records what a page draws on its 2D canvases and writes each canvas's drawing as SVG.
//
// Load it before anything draws. Every CanvasRenderingContext2D then keeps, beside the pixels it draws, the
// drawing in SVG: a path is kept in device space as it is built (canvas transforms each point when it is added)
// and written in the user space of the fill or stroke that paints it, with that transform; fill and stroke
// styles, gradients, text, images, clips, global alpha, shadows and blend modes come from the context's own state
// at the call. A clearRect over the whole canvas starts the drawing over; what SVG cannot say (a partial clear, a
// Porter-Duff operator, a pattern) is drawn as the nearest thing and listed in the warnings.
//
//   CanvasRecorder.canvases()         the canvases drawn on, in the order they were first drawn on
//   CanvasRecorder.svg(canvas)        { svg, warnings, ops }
//   CanvasRecorder.restart(canvas)    forget what a canvas holds (its next full redraw is recorded afresh)
(function () {
  'use strict';
  const P = CanvasRenderingContext2D.prototype;
  const real = {};
  for (const k of Object.getOwnPropertyNames(P)) {
    const d = Object.getOwnPropertyDescriptor(P, k);
    if (typeof d.value === 'function') real[k] = d.value;
  }
  const records = new Map(); // canvas -> record
  const order = [];
  const gradients = new WeakMap(); // CanvasGradient -> {kind, args, stops}
  const paths2d = new WeakMap(); // Path2D -> segments in the Path2D's own space
  let nextId = 0;

  const num = (v) => {
    const r = Math.round(v * 1000) / 1000;
    return Object.is(r, -0) ? '0' : String(r);
  };
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  function record(ctx) {
    const canvas = ctx.canvas;
    let r = records.get(canvas);
    if (!r) {
      r = { canvas, items: [], defs: [], saves: [], open: 0, clips: [], path: [], warnings: new Set(), ops: 0 };
      records.set(canvas, r);
      order.push(canvas);
    }
    return r;
  }

  // Segments: ['M', x, y] ['L', x, y] ['C', x1, y1, x2, y2, x, y] ['Z'], in device space for a context's path.
  const apply = (m, x, y) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
  function current(segs) {
    for (let i = segs.length - 1; i >= 0; i--) {
      const s = segs[i];
      if (s[0] !== 'Z') return [s[s.length - 2], s[s.length - 1]];
      for (let j = i - 1; j >= 0; j--) if (segs[j][0] === 'M') return [segs[j][1], segs[j][2]];
    }
    return null;
  }
  // An arc of the ellipse (cx, cy, rx, ry, rotation) from a0 to a1, as cubics, mapped by m.
  function arcSegs(segs, m, cx, cy, rx, ry, rot, a0, a1, ccw, lineFirst) {
    let sweep = a1 - a0;
    const tau = Math.PI * 2;
    if (!ccw && sweep < 0) sweep = sweep <= -tau ? tau : (sweep % tau) + tau;
    if (ccw && sweep > 0) sweep = sweep >= tau ? -tau : (sweep % tau) - tau;
    if (!ccw && sweep > tau) sweep = tau;
    if (ccw && sweep < -tau) sweep = -tau;
    const cr = Math.cos(rot), sr = Math.sin(rot);
    const pt = (a) => {
      const x = rx * Math.cos(a), y = ry * Math.sin(a);
      return apply(m, cx + x * cr - y * sr, cy + x * sr + y * cr);
    };
    const d = (a) => {
      const x = -rx * Math.sin(a), y = ry * Math.cos(a);
      return [x * cr - y * sr, x * sr + y * cr];
    };
    const start = pt(a0);
    if (lineFirst && current(segs)) segs.push(['L', start[0], start[1]]);
    else segs.push(['M', start[0], start[1]]);
    const n = Math.max(1, Math.ceil(Math.abs(sweep) / (Math.PI / 2) - 1e-9));
    const step = sweep / n, k = (4 / 3) * Math.tan(step / 4);
    let a = a0;
    for (let i = 0; i < n; i++) {
      const b = a + step;
      const p0 = [rx * Math.cos(a), ry * Math.sin(a)], p3 = [rx * Math.cos(b), ry * Math.sin(b)];
      const t0 = [-rx * Math.sin(a), ry * Math.cos(a)], t3 = [-rx * Math.sin(b), ry * Math.cos(b)];
      const loc = (x, y) => apply(m, cx + x * cr - y * sr, cy + x * sr + y * cr);
      const c1 = loc(p0[0] + k * t0[0], p0[1] + k * t0[1]);
      const c2 = loc(p3[0] - k * t3[0], p3[1] - k * t3[1]);
      const e = loc(p3[0], p3[1]);
      segs.push(['C', c1[0], c1[1], c2[0], c2[1], e[0], e[1]]);
      a = b;
    }
    void d;
  }
  function roundRectSegs(segs, m, x, y, w, h, radii) {
    let r = radii === undefined ? [0] : Array.isArray(radii) ? radii : [radii];
    r = r.map((v) => (typeof v === 'number' ? { x: v, y: v } : { x: v.x || 0, y: v.y || 0 }));
    let [tl, tr, br, bl] = r.length === 1 ? [r[0], r[0], r[0], r[0]] : r.length === 2 ? [r[0], r[1], r[0], r[1]]
      : r.length === 3 ? [r[0], r[1], r[2], r[1]] : r;
    // A negative width or height flips the rectangle, and its corners with it (the HTML roundRect steps).
    if (w < 0) { x += w; w = -w; [tl, tr, bl, br] = [tr, tl, br, bl]; }
    if (h < 0) { y += h; h = -h; [tl, bl, tr, br] = [bl, tl, br, tr]; }
    const s = Math.min(1, Math.abs(w) / Math.max(tl.x + tr.x, bl.x + br.x, 1e-9), Math.abs(h) / Math.max(tl.y + bl.y, tr.y + br.y, 1e-9));
    const R = [tl, tr, br, bl].map((c) => ({ x: c.x * s, y: c.y * s }));
    const p = (px, py) => apply(m, px, py);
    let q = p(x + R[0].x, y);
    segs.push(['M', q[0], q[1]]);
    q = p(x + w - R[1].x, y); segs.push(['L', q[0], q[1]]);
    if (R[1].x || R[1].y) arcSegs(segs, m, x + w - R[1].x, y + R[1].y, R[1].x, R[1].y, 0, -Math.PI / 2, 0, false, true);
    q = p(x + w, y + h - R[2].y); segs.push(['L', q[0], q[1]]);
    if (R[2].x || R[2].y) arcSegs(segs, m, x + w - R[2].x, y + h - R[2].y, R[2].x, R[2].y, 0, 0, Math.PI / 2, false, true);
    q = p(x + R[3].x, y + h); segs.push(['L', q[0], q[1]]);
    if (R[3].x || R[3].y) arcSegs(segs, m, x + R[3].x, y + h - R[3].y, R[3].x, R[3].y, 0, Math.PI / 2, Math.PI, false, true);
    q = p(x, y + R[0].y); segs.push(['L', q[0], q[1]]);
    if (R[0].x || R[0].y) arcSegs(segs, m, x + R[0].x, y + R[0].y, R[0].x, R[0].y, 0, Math.PI, Math.PI * 1.5, false, true);
    segs.push(['Z']);
  }
  function arcToSegs(segs, m, x1, y1, x2, y2, radius) {
    // arcTo's points are in user space; its current point is the last device point mapped back.
    const cur = current(segs);
    const inv = m.inverse();
    const p1 = apply(m, x1, y1);
    if (!cur) { segs.push(['M', p1[0], p1[1]]); return; }
    const [x0, y0] = apply(inv, cur[0], cur[1]);
    const v0 = [x0 - x1, y0 - y1], v2 = [x2 - x1, y2 - y1];
    const l0 = Math.hypot(...v0), l2 = Math.hypot(...v2);
    const cross = v0[0] * v2[1] - v0[1] * v2[0];
    if (radius === 0 || l0 === 0 || l2 === 0 || Math.abs(cross) < 1e-9) { segs.push(['L', p1[0], p1[1]]); return; }
    const cos = (v0[0] * v2[0] + v0[1] * v2[1]) / (l0 * l2);
    const half = Math.acos(Math.max(-1, Math.min(1, cos))) / 2;
    const t = radius / Math.tan(half);
    const ta = [x1 + (v0[0] / l0) * t, y1 + (v0[1] / l0) * t], tb = [x1 + (v2[0] / l2) * t, y1 + (v2[1] / l2) * t];
    const bis = [v0[0] / l0 + v2[0] / l2, v0[1] / l0 + v2[1] / l2], bl = Math.hypot(...bis);
    const dc = radius / Math.sin(half);
    const c = [x1 + (bis[0] / bl) * dc, y1 + (bis[1] / bl) * dc];
    // The shorter way round between the tangent points, as canvas draws it.
    const a0 = Math.atan2(ta[1] - c[1], ta[0] - c[0]);
    let sweep = Math.atan2(tb[1] - c[1], tb[0] - c[0]) - a0;
    while (sweep > Math.PI) sweep -= 2 * Math.PI;
    while (sweep <= -Math.PI) sweep += 2 * Math.PI;
    arcSegs(segs, m, c[0], c[1], radius, radius, 0, a0, a0 + sweep, sweep < 0, true);
  }

  // SVG path data as segments (in its own space): what a Path2D built from a string holds.
  function parsePathData(str) {
    const segs = [];
    const toks = str.match(/[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g) || [];
    const I = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 };
    let i = 0, cmd = '', x = 0, y = 0, sx = 0, sy = 0, cx = null, cy = null, qx = null, qy = null;
    const n = () => parseFloat(toks[i++]);
    const flag = () => { const t = toks[i]; if (t.length > 1 && /^[01]/.test(t)) { toks[i] = t.slice(1); return +t[0]; } i++; return +t; };
    while (i < toks.length) {
      if (/[A-Za-z]/.test(toks[i])) cmd = toks[i++];
      const rel = cmd === cmd.toLowerCase() && cmd !== 'z' ? 1 : 0;
      const ox = rel ? x : 0, oy = rel ? y : 0;
      switch (cmd.toUpperCase()) {
        case 'M': x = ox + n(); y = oy + n(); segs.push(['M', x, y]); sx = x; sy = y; cmd = rel ? 'l' : 'L'; cx = qx = null; break;
        case 'L': x = ox + n(); y = oy + n(); segs.push(['L', x, y]); cx = qx = null; break;
        case 'H': x = ox + n(); segs.push(['L', x, y]); cx = qx = null; break;
        case 'V': y = oy + n(); segs.push(['L', x, y]); cx = qx = null; break;
        case 'C': { const x1 = ox + n(), y1 = oy + n(), x2 = ox + n(), y2 = oy + n(); x = ox + n(); y = oy + n(); segs.push(['C', x1, y1, x2, y2, x, y]); cx = x2; cy = y2; qx = null; break; }
        case 'S': { const x1 = cx === null ? x : 2 * x - cx, y1 = cy === null ? y : 2 * y - cy; const x2 = ox + n(), y2 = oy + n(); x = ox + n(); y = oy + n(); segs.push(['C', x1, y1, x2, y2, x, y]); cx = x2; cy = y2; qx = null; break; }
        case 'Q': case 'T': {
          let x1, y1;
          if (cmd.toUpperCase() === 'Q') { x1 = ox + n(); y1 = oy + n(); } else { x1 = qx === null ? x : 2 * x - qx; y1 = qy === null ? y : 2 * y - qy; }
          const ex = ox + n(), ey = oy + n();
          segs.push(['C', x + (2 / 3) * (x1 - x), y + (2 / 3) * (y1 - y), ex + (2 / 3) * (x1 - ex), ey + (2 / 3) * (y1 - ey), ex, ey]);
          x = ex; y = ey; qx = x1; qy = y1; cx = null; break;
        }
        case 'A': {
          let rx = Math.abs(n()), ry = Math.abs(n()); const phi = (n() * Math.PI) / 180, large = flag(), sweep = flag();
          const ex = ox + n(), ey = oy + n();
          if (!rx || !ry) { segs.push(['L', ex, ey]); x = ex; y = ey; cx = qx = null; break; }
          const cp = Math.cos(phi), sp = Math.sin(phi);
          const dx = (x - ex) / 2, dy = (y - ey) / 2, x1p = cp * dx + sp * dy, y1p = -sp * dx + cp * dy;
          const lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
          if (lam > 1) { rx *= Math.sqrt(lam); ry *= Math.sqrt(lam); }
          let k = Math.sqrt(Math.max(0, (rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p) / (rx * rx * y1p * y1p + ry * ry * x1p * x1p)));
          if (large === sweep) k = -k;
          const cxp = (k * rx * y1p) / ry, cyp = (-k * ry * x1p) / rx;
          const ccx = cp * cxp - sp * cyp + (x + ex) / 2, ccy = sp * cxp + cp * cyp + (y + ey) / 2;
          const ang = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
          const a0 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry);
          let da = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
          if (!sweep && da > 0) da -= 2 * Math.PI;
          if (sweep && da < 0) da += 2 * Math.PI;
          arcSegs(segs, I, ccx, ccy, rx, ry, phi, a0, a0 + da, !sweep, true);
          x = ex; y = ey; cx = qx = null; break;
        }
        case 'Z': segs.push(['Z']); x = sx; y = sy; cx = qx = null; break;
        default: i++;
      }
    }
    return segs;
  }

  function d(segs, inv) {
    const out = [];
    for (const s of segs) {
      if (s[0] === 'Z') { out.push('Z'); continue; }
      const pts = [];
      for (let i = 1; i < s.length; i += 2) {
        const [x, y] = inv ? apply(inv, s[i], s[i + 1]) : [s[i], s[i + 1]];
        pts.push(num(x) + ' ' + num(y));
      }
      out.push(s[0] + pts.join(' '));
    }
    return out.join('');
  }
  const matrix = (m) => `matrix(${[m.a, m.b, m.c, m.d, m.e, m.f].map(num).join(' ')})`;
  const identity = (m) => m.a === 1 && m.b === 0 && m.c === 0 && m.d === 1 && m.e === 0 && m.f === 0;

  function color(c) {
    // Computed canvas colours are '#rrggbb' or 'rgba(r, g, b, a)'.
    const m = /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/.exec(c);
    if (m) return { value: `rgb(${m[1]},${m[2]},${m[3]})`, alpha: parseFloat(m[4]) };
    return { value: c, alpha: 1 };
  }
  function paint(r, ctx, style, kind) {
    if (typeof style === 'string') {
      const c = color(style);
      return `${kind}="${c.value}"` + (c.alpha < 1 ? ` ${kind}-opacity="${num(c.alpha)}"` : '');
    }
    const g = gradients.get(style);
    if (!g) {
      r.warnings.add('pattern paint drawn as black');
      return `${kind}="#000"`;
    }
    const id = `g${nextId++}`;
    const stops = g.stops.map(([o, c]) => {
      const cc = color(c);
      return `<stop offset="${num(o)}" stop-color="${cc.value}"${cc.alpha < 1 ? ` stop-opacity="${num(cc.alpha)}"` : ''}/>`;
    }).join('');
    if (g.kind === 'linear') {
      const [x0, y0, x1, y1] = g.args;
      r.defs.push(`<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${num(x0)}" y1="${num(y0)}" x2="${num(x1)}" y2="${num(y1)}">${stops}</linearGradient>`);
    } else if (g.kind === 'radial') {
      const [fx, fy, fr, cx, cy, cr] = g.args;
      r.defs.push(`<radialGradient id="${id}" gradientUnits="userSpaceOnUse" cx="${num(cx)}" cy="${num(cy)}" r="${num(cr)}" fx="${num(fx)}" fy="${num(fy)}" fr="${num(fr)}">${stops}</radialGradient>`);
    } else {
      r.warnings.add(`${g.kind} gradient drawn as its first stop`);
      return `${kind}="${g.stops.length ? color(g.stops[0][1]).value : '#000'}"`;
    }
    return `${kind}="url(#${id})"`;
  }
  const BLENDS = new Set(['multiply', 'screen', 'overlay', 'darken', 'lighten', 'color-dodge', 'color-burn', 'hard-light',
    'soft-light', 'difference', 'exclusion', 'hue', 'saturation', 'color', 'luminosity']);
  function common(r, ctx) {
    let a = '';
    if (ctx.globalAlpha < 1) a += ` opacity="${num(ctx.globalAlpha)}"`;
    const op = ctx.globalCompositeOperation;
    if (BLENDS.has(op)) a += ` style="mix-blend-mode:${op}"`;
    else if (op !== 'source-over') r.warnings.add(`${op} drawn as source-over`);
    return a;
  }
  // An element, inside groups carrying the context's filter and its shadow when it has them (in device space, as
  // canvas draws both).
  function emit(r, ctx, el) {
    if (ctx.filter && ctx.filter !== 'none') {
      const blur = /^blur\(\s*([\d.]+)px\s*\)$/.exec(ctx.filter);
      if (blur) {
        const id = `f${nextId++}`;
        r.defs.push(`<filter id="${id}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="${num(parseFloat(blur[1]))}"/></filter>`);
        el = `<g filter="url(#${id})">${el}</g>`;
      } else {
        r.warnings.add(`filter ${ctx.filter} left out`);
      }
    }
    const sc = color(ctx.shadowColor);
    if (sc.alpha > 0 && (ctx.shadowBlur > 0 || ctx.shadowOffsetX || ctx.shadowOffsetY)) {
      const id = `s${nextId++}`;
      r.defs.push(`<filter id="${id}" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB">` +
        `<feGaussianBlur in="SourceAlpha" stdDeviation="${num(ctx.shadowBlur / 2)}"/>` +
        `<feOffset dx="${num(ctx.shadowOffsetX)}" dy="${num(ctx.shadowOffsetY)}" result="o"/>` +
        `<feFlood flood-color="${sc.value}" flood-opacity="${num(sc.alpha)}"/><feComposite in2="o" operator="in"/>` +
        `<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>`);
      el = `<g filter="url(#${id})">${el}</g>`;
    }
    r.items.push(el);
  }
  function strokeAttrs(ctx) {
    let a = ` stroke-width="${num(ctx.lineWidth)}"`;
    if (ctx.lineCap !== 'butt') a += ` stroke-linecap="${ctx.lineCap}"`;
    if (ctx.lineJoin !== 'miter') a += ` stroke-linejoin="${ctx.lineJoin}"`;
    else if (ctx.miterLimit !== 10) a += ` stroke-miterlimit="${num(ctx.miterLimit)}"`;
    const dash = ctx.getLineDash();
    if (dash.length) {
      a += ` stroke-dasharray="${dash.map(num).join(' ')}"`;
      if (ctx.lineDashOffset) a += ` stroke-dashoffset="${num(ctx.lineDashOffset)}"`;
    }
    return a;
  }
  // The segments a fill, stroke or clip paints: a Path2D's in its own space (mapped by m), or the context's.
  function pathOf(r, ctx, arg) {
    if (typeof Path2D !== 'undefined' && arg instanceof Path2D) {
      const local = paths2d.get(arg) || [];
      const m = ctx.getTransform();
      return local.map((s) => {
        if (s[0] === 'Z') return s;
        const o = [s[0]];
        for (let i = 1; i < s.length; i += 2) o.push(...apply(m, s[i], s[i + 1]));
        return o;
      });
    }
    return r.path;
  }
  function paintPath(r, ctx, segs, mode, rule) {
    if (!segs.length) return;
    const m = ctx.getTransform();
    const inv = identity(m) ? null : m.inverse();
    const t = inv ? ` transform="${matrix(m)}"` : '';
    const data = d(segs, inv);
    if (mode === 'fill') {
      emit(r, ctx, `<path d="${data}"${t} ${paint(r, ctx, ctx.fillStyle, 'fill')}${rule === 'evenodd' ? ' fill-rule="evenodd"' : ''}${common(r, ctx)}/>`);
    } else {
      emit(r, ctx, `<path d="${data}"${t} fill="none" ${paint(r, ctx, ctx.strokeStyle, 'stroke')}${strokeAttrs(ctx)}${common(r, ctx)}/>`);
    }
  }


  const fontKeys = /^(italic|oblique|normal|small-caps|bold|bolder|lighter|[1-9]00)$/;
  function fontAttrs(font) {
    const parts = font.match(/("[^"]*"|'[^']*'|\S+)/g) || [];
    let i = 0, style = '', weight = '', size = '16px';
    for (; i < parts.length; i++) {
      const p = parts[i];
      if (/^[\d.]+(px|pt|em|rem|%)(\/.*)?$/.test(p)) { size = p.split('/')[0]; i++; break; }
      if (/^(italic|oblique)$/.test(p)) style = p;
      else if (/^(bold|bolder|lighter|[1-9]00)$/.test(p)) weight = p;
      else if (!fontKeys.test(p)) break;
    }
    const family = parts.slice(i).join(' ');
    return ` font-family="${esc(family)}" font-size="${size}"` + (weight ? ` font-weight="${weight}"` : '') + (style ? ` font-style="${style}"` : '');
  }
  const ANCHOR = { start: 'start', left: 'start', center: 'middle', end: 'end', right: 'end' };
  const BASELINE = { alphabetic: '', top: 'text-before-edge', hanging: 'hanging', middle: 'central', ideographic: 'ideographic', bottom: 'text-after-edge' };
  function text(r, ctx, mode, str, x, y, maxWidth) {
    const m = ctx.getTransform();
    const t = identity(m) ? '' : ` transform="${matrix(m)}"`;
    let a = fontAttrs(ctx.font);
    const anchor = ANCHOR[ctx.textAlign] || 'start';
    if (anchor !== 'start') a += ` text-anchor="${anchor}"`;
    const base = BASELINE[ctx.textBaseline];
    if (base) a += ` dominant-baseline="${base}"`;
    if (ctx.letterSpacing && ctx.letterSpacing !== '0px') a += ` letter-spacing="${ctx.letterSpacing}"`;
    if (maxWidth !== undefined) {
      const w = real.measureText.call(ctx, String(str)).width;
      if (w > maxWidth) a += ` textLength="${num(maxWidth)}" lengthAdjust="spacingAndGlyphs"`;
    }
    const p = mode === 'fill' ? paint(r, ctx, ctx.fillStyle, 'fill') : `fill="none" ${paint(r, ctx, ctx.strokeStyle, 'stroke')}${strokeAttrs(ctx)}`;
    emit(r, ctx, `<text x="${num(x)}" y="${num(y)}"${t}${a} ${p}${common(r, ctx)} xml:space="preserve">${esc(str)}</text>`);
  }
  function imageHref(r, img) {
    try {
      if (img instanceof HTMLCanvasElement) return img.toDataURL('image/png');
      const c = document.createElement('canvas');
      c.width = img.naturalWidth || img.videoWidth || img.width;
      c.height = img.naturalHeight || img.videoHeight || img.height;
      real.drawImage.call(c.getContext('2d'), img, 0, 0);
      return c.toDataURL('image/png');
    } catch (e) {
      r.warnings.add('an image the page may not read is linked by URL');
      return img.currentSrc || img.src || '';
    }
  }
  function image(r, ctx, img, args) {
    const iw = img.naturalWidth || img.videoWidth || img.width, ih = img.naturalHeight || img.videoHeight || img.height;
    let sx = 0, sy = 0, sw = iw, sh = ih, dx, dy, dw = iw, dh = ih;
    if (args.length === 2) [dx, dy] = args;
    else if (args.length === 4) [dx, dy, dw, dh] = args;
    else [sx, sy, sw, sh, dx, dy, dw, dh] = args;
    const m = ctx.getTransform();
    const t = identity(m) ? '' : ` transform="${matrix(m)}"`;
    const smooth = ctx.imageSmoothingEnabled ? '' : ' image-rendering="pixelated"';
    emit(r, ctx, `<g${t}${common(r, ctx)}><svg x="${num(dx)}" y="${num(dy)}" width="${num(dw)}" height="${num(dh)}" viewBox="${num(sx)} ${num(sy)} ${num(sw)} ${num(sh)}" preserveAspectRatio="none" overflow="hidden">` +
      `<image width="${iw}" height="${ih}" href="${imageHref(r, img)}"${smooth}/></svg></g>`);
  }

  function wrap(name, fn) {
    P[name] = function (...args) {
      const r = record(this);
      r.ops++;
      try { fn.call(this, r, ...args); } catch (e) { r.warnings.add(`${name}: ${e.message}`); }
      return real[name].apply(this, args);
    };
  }
  // Path building, in device space as the context sees it.
  wrap('beginPath', (r) => { r.path = []; });
  wrap('moveTo', function (r, x, y) { const p = apply(this.getTransform(), x, y); r.path.push(['M', p[0], p[1]]); });
  wrap('lineTo', function (r, x, y) {
    const p = apply(this.getTransform(), x, y);
    r.path.push([current(r.path) ? 'L' : 'M', p[0], p[1]]);
  });
  wrap('closePath', (r) => { if (r.path.length) r.path.push(['Z']); });
  wrap('bezierCurveTo', function (r, x1, y1, x2, y2, x, y) {
    const m = this.getTransform();
    if (!current(r.path)) { const p = apply(m, x1, y1); r.path.push(['M', p[0], p[1]]); }
    r.path.push(['C', ...apply(m, x1, y1), ...apply(m, x2, y2), ...apply(m, x, y)]);
  });
  wrap('quadraticCurveTo', function (r, x1, y1, x, y) {
    const m = this.getTransform();
    const cur = current(r.path);
    if (!cur) { const p = apply(m, x1, y1); r.path.push(['M', p[0], p[1]]); return; }
    const q = apply(m, x1, y1), e = apply(m, x, y);
    r.path.push(['C', cur[0] + (2 / 3) * (q[0] - cur[0]), cur[1] + (2 / 3) * (q[1] - cur[1]), e[0] + (2 / 3) * (q[0] - e[0]), e[1] + (2 / 3) * (q[1] - e[1]), e[0], e[1]]);
  });
  wrap('arc', function (r, x, y, rad, a0, a1, ccw) { arcSegs(r.path, this.getTransform(), x, y, rad, rad, 0, a0, a1, !!ccw, true); });
  wrap('ellipse', function (r, x, y, rx, ry, rot, a0, a1, ccw) { arcSegs(r.path, this.getTransform(), x, y, rx, ry, rot, a0, a1, !!ccw, true); });
  wrap('arcTo', function (r, x1, y1, x2, y2, rad) { arcToSegs(r.path, this.getTransform(), x1, y1, x2, y2, rad); });
  wrap('rect', function (r, x, y, w, h) {
    const m = this.getTransform();
    const pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([px, py]) => apply(m, px, py));
    r.path.push(['M', ...pts[0]], ['L', ...pts[1]], ['L', ...pts[2]], ['L', ...pts[3]], ['Z']);
  });
  if (real.roundRect) wrap('roundRect', function (r, x, y, w, h, radii) { roundRectSegs(r.path, this.getTransform(), x, y, w, h, radii); });

  // Painting.
  wrap('fill', function (r, a, b) {
    const rule = typeof a === 'string' ? a : b;
    paintPath(r, this, pathOf(r, this, a), 'fill', rule);
  });
  wrap('stroke', function (r, a) { paintPath(r, this, pathOf(r, this, a), 'stroke'); });
  wrap('fillRect', function (r, x, y, w, h) {
    const m = this.getTransform();
    const pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([px, py]) => apply(m, px, py));
    paintPath(r, this, [['M', ...pts[0]], ['L', ...pts[1]], ['L', ...pts[2]], ['L', ...pts[3]], ['Z']], 'fill');
  });
  wrap('strokeRect', function (r, x, y, w, h) {
    const m = this.getTransform();
    const pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([px, py]) => apply(m, px, py));
    paintPath(r, this, [['M', ...pts[0]], ['L', ...pts[1]], ['L', ...pts[2]], ['L', ...pts[3]], ['Z']], 'stroke');
  });
  wrap('fillText', function (r, s, x, y, w) { text(r, this, 'fill', s, x, y, w); });
  wrap('strokeText', function (r, s, x, y, w) { text(r, this, 'stroke', s, x, y, w); });
  wrap('drawImage', function (r, img, ...args) { image(r, this, img, args); });
  wrap('putImageData', (r) => { r.warnings.add('putImageData left out'); });
  wrap('clearRect', function (r, x, y, w, h) {
    const m = this.getTransform();
    const pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([px, py]) => apply(m, px, py));
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const c = this.canvas;
    if (Math.min(...xs) <= 0 && Math.min(...ys) <= 0 && Math.max(...xs) >= c.width && Math.max(...ys) >= c.height) {
      // The whole canvas: what was drawn is gone, the clips in force stay.
      r.items = r.clips.map((id) => `<g clip-path="url(#${id})">`);
      r.defs = r.defs.filter((def) => r.clips.some((id) => def.includes(`id="${id}"`)));
    } else {
      r.warnings.add(`a partial clearRect left out (${[x, y, w, h].map(num).join(',')} of ${c.width}x${c.height})`);
    }
  });

  // State: a clip opens a group that the restore matching its save closes.
  wrap('save', (r) => { r.saves.push(r.clips.length); });
  wrap('restore', (r) => {
    if (!r.saves.length) return;
    const keep = r.saves.pop();
    while (r.clips.length > keep) { r.clips.pop(); r.items.push('</g>'); }
  });
  wrap('clip', function (r, a, b) {
    const rule = typeof a === 'string' ? a : b;
    const segs = pathOf(r, this, a);
    const id = `c${nextId++}`;
    r.defs.push(`<clipPath id="${id}"><path d="${d(segs)}"${rule === 'evenodd' ? ' clip-rule="evenodd"' : ''}/></clipPath>`);
    r.clips.push(id);
    r.items.push(`<g clip-path="url(#${id})">`);
  });
  if (real.reset) wrap('reset', (r) => { r.items = []; r.defs = []; r.clips = []; r.saves = []; r.path = []; });

  // Gradients and Path2D objects keep their own record.
  const realLinear = real.createLinearGradient, realRadial = real.createRadialGradient, realConic = real.createConicGradient;
  P.createLinearGradient = function (...args) { const g = realLinear.apply(this, args); gradients.set(g, { kind: 'linear', args, stops: [] }); return g; };
  P.createRadialGradient = function (...args) { const g = realRadial.apply(this, args); gradients.set(g, { kind: 'radial', args, stops: [] }); return g; };
  if (realConic) P.createConicGradient = function (...args) { const g = realConic.apply(this, args); gradients.set(g, { kind: 'conic', args, stops: [] }); return g; };
  const addStop = CanvasGradient.prototype.addColorStop;
  CanvasGradient.prototype.addColorStop = function (o, c) {
    addStop.call(this, o, c);
    const g = gradients.get(this);
    if (g) {
      // The colour as the canvas computes it.
      const probe = document.createElement('canvas').getContext('2d');
      probe.fillStyle = c;
      g.stops.push([o, probe.fillStyle]);
    }
  };
  if (typeof Path2D !== 'undefined') {
    const RealPath2D = window.Path2D;
    window.Path2D = function Path2D(a) {
      const p = a === undefined ? new RealPath2D() : new RealPath2D(a);
      if (typeof a === 'string') paths2d.set(p, parsePathData(a));
      else if (a instanceof RealPath2D && paths2d.has(a)) paths2d.set(p, paths2d.get(a).slice());
      return p;
    };
    window.Path2D.prototype = RealPath2D.prototype;
    const I = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0, inverse() { return this; } };
    const P2 = Path2D.prototype;
    const segsOf = (p) => { let s = paths2d.get(p); if (!s) { s = []; paths2d.set(p, s); } return s; };
    const realP2 = {};
    for (const k of ['moveTo', 'lineTo', 'closePath', 'bezierCurveTo', 'quadraticCurveTo', 'arc', 'ellipse', 'arcTo', 'rect', 'roundRect']) {
      if (P2[k]) realP2[k] = P2[k];
    }
    const pw = (k, fn) => { if (realP2[k]) P2[k] = function (...a) { try { fn(segsOf(this), ...a); } catch (e) { /* recorded best-effort */ } return realP2[k].apply(this, a); }; };
    pw('moveTo', (s, x, y) => s.push(['M', x, y]));
    pw('lineTo', (s, x, y) => s.push([current(s) ? 'L' : 'M', x, y]));
    pw('closePath', (s) => { if (s.length) s.push(['Z']); });
    pw('bezierCurveTo', (s, x1, y1, x2, y2, x, y) => { if (!current(s)) s.push(['M', x1, y1]); s.push(['C', x1, y1, x2, y2, x, y]); });
    pw('quadraticCurveTo', (s, x1, y1, x, y) => {
      const c = current(s);
      if (!c) { s.push(['M', x1, y1]); return; }
      s.push(['C', c[0] + (2 / 3) * (x1 - c[0]), c[1] + (2 / 3) * (y1 - c[1]), x + (2 / 3) * (x1 - x), y + (2 / 3) * (y1 - y), x, y]);
    });
    pw('arc', (s, x, y, rad, a0, a1, ccw) => arcSegs(s, I, x, y, rad, rad, 0, a0, a1, !!ccw, true));
    pw('ellipse', (s, x, y, rx, ry, rot, a0, a1, ccw) => arcSegs(s, I, x, y, rx, ry, rot, a0, a1, !!ccw, true));
    pw('arcTo', (s, x1, y1, x2, y2, rad) => arcToSegs(s, I, x1, y1, x2, y2, rad));
    pw('rect', (s, x, y, w, h) => s.push(['M', x, y], ['L', x + w, y], ['L', x + w, y + h], ['L', x, y + h], ['Z']));
    pw('roundRect', (s, x, y, w, h, radii) => roundRectSegs(s, I, x, y, w, h, radii));
    const realAddPath = P2.addPath;
    if (realAddPath) P2.addPath = function (other, t) {
      try {
        const m = t ? { a: t.a ?? 1, b: t.b ?? 0, c: t.c ?? 0, d: t.d ?? 1, e: t.e ?? 0, f: t.f ?? 0 } : I;
        const own = segsOf(this);
        for (const sg of paths2d.get(other) || []) {
          if (sg[0] === 'Z') { own.push(sg); continue; }
          const o = [sg[0]];
          for (let k = 1; k < sg.length; k += 2) o.push(...apply(m, sg[k], sg[k + 1]));
          own.push(o);
        }
      } catch (e) { /* recorded best-effort */ }
      return realAddPath.call(this, other, t);
    };
  }

  window.CanvasRecorder = {
    canvases: () => order.filter((c) => records.get(c).items.length),
    restart(canvas) {
      const r = records.get(canvas);
      if (r) { r.items = r.clips.map((id) => `<g clip-path="url(#${id})">`); r.defs = []; r.warnings = new Set(); }
    },
    svg(canvas) {
      const r = records.get(canvas);
      if (!r) return null;
      const open = r.items.filter((i) => i.startsWith('<g clip-path')).length - r.items.filter((i) => i === '</g>').length;
      const body = r.items.join('\n') + '</g>'.repeat(Math.max(0, open));
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}">\n` +
        (r.defs.length ? `<defs>\n${r.defs.join('\n')}\n</defs>\n` : '') + body + '\n</svg>\n';
      return { svg, warnings: [...r.warnings], ops: r.ops };
    },
  };
})();
