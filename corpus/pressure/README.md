# Pressure probes

- `hole-strip-{nonzero,evenodd}.svg` and their `hole-*.svg` controls: a square
  with a hole plus a 0.001-unit strip along the hole's first edge. Browsers
  ink nothing for the strip; the hole must render as in the control.
- `wide-masked-shadow.svg`: a 2048 px wide masked group under a σ 8 drop
  shadow with a caster crossing the right edge. Render at
  `FRAME_W=2048 FRAME_H=256 BOX=2048 BOX_X=0 BOX_Y=0`, and with
  `MAX_TEXTURE_SIZE=2048` to model a VideoCore IV's texture limit.
