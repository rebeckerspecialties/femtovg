# Blend interaction probes

Hand-written cases for a blend's interaction with the clip, mask, layer and
filter stacks (femtovg/femtovg#355, #356): a blending element inside a
clipped group (an isolating group, per CSS Compositing: the blend sees only
the group's content), a clip on the blending group itself, inside a mask,
blurred before blending, nested blends, inside an opacity group with a clip
over a translucent backdrop, `feBlend` after a blur in one chain, and a flood
`feBlend` chain on a clipped group with opacity. References are Chromium 131
through `harness/make_ref.py`.
