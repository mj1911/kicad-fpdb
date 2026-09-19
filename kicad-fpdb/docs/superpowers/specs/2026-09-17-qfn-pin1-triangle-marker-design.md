# QFN pin-1 triangle marker

Date: 2026-09-17

## Problem

Every generated footprint's pin-1 indicator is a filled circle placed
directly above pad 1 (`kicad_fpdb.pipeline._add_outline`, see
`docs/superpowers/specs/2026-09-14-pin1-circle-marker-design.md`). Real
KiCad's own QFN reference footprints (`Package_DFN_QFN.pretty`) don't
use this convention at all: they draw a filled *triangle* pointing
outward from pad 1, on whichever side of the body pad 1 actually sits
(QFN's pin 1 is always the first pad on the left side, not the top),
not a circle above it. This project's QFN family should match that
convention instead of inheriting the DIP/SOIC/SOT/LQFP circle
convention it wasn't designed around.

## Investigation

Extracted the `F.SilkS` `fp_poly` pin-1 marker and pad 1's own
`at`/`size` from every sampled real QFN reference file —
QFN-12/16/20/24/28/32/40/44/48/64/80, spanning 0.4mm and 0.5mm pitch,
square and custom pad shapes. The geometry is a fixed constant in
every sample (verified to 0.01mm):

- The triangle's apex sits `courtyard_margin_x` (or `_y`, whichever
  axis is pad 1's own outward axis) `+ 0.01mm` beyond pad 1's own
  outward edge — i.e. just past where the courtyard line on that side
  already sits. Reuses the family's existing courtyard margin rather
  than a new constant.
- The triangle's depth (apex to base, along the outward axis) is a
  fixed `0.33mm` in every sample.
- The base spans `±0.24mm` (fixed) along the perpendicular axis,
  centered on pad 1's own center.

Example (`QFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm.kicad_mod`): pad 1 at
`(-3.4375, -2.75)`, size `(0.875, 0.25)` (a wide, short pad — a
left-side pad by the same width>height convention `_quad_side_groups`
already uses). Real triangle: `(-4.14, -2.75), (-4.47, -2.51), (-4.47,
-2.99)` — apex at `x = -3.4375 - 0.4375 - 0.25 - 0.01 = -4.14` (pad's
own left edge, minus `courtyard_margin_x`, minus `0.01`), base at
`x = -4.14 - 0.33 = -4.47`, spread `-2.75 ± 0.24`.

This held across every sample regardless of pin count, pitch, pad
size, or pad shape (including one custom-shaped pad 1).

Also noted: the real files' corner-mark bracket leg on that same
corner is shortened (~0.02mm instead of the usual ~0.45mm), apparently
to leave room for the triangle. Explicitly out of scope for this
change — see Non-goals.

## Design

**New param on `_add_outline`:** `pin1_marker_style: str = "circle"`.
Existing behavior for every other family is the default and is
unchanged. QFN's yaml root sets `pin1_marker_style: triangle`.

**New constants** (`kicad_fpdb/pipeline.py`, alongside the existing
`PIN1_MARKER_MM`/`PIN1_MARKER_CLEARANCE_MM`):

```python
PIN1_TRIANGLE_DEPTH_MM = 0.33
PIN1_TRIANGLE_HALF_HEIGHT_MM = 0.24
PIN1_TRIANGLE_SILK_OFFSET_MM = 0.01
```

**Triangle branch**, replacing the circle branch when
`pin1_marker_style == "triangle"`:

1. Determine pad 1's orientation and outward direction the same way
   `_quad_side_groups` already classifies pads: `size[0] > size[1]` →
   pad 1 is on the left or right side (outward axis = X, sign
   determined by `pad1.at[0]`'s sign); otherwise pad 1 is on the top
   or bottom side (outward axis = Y, sign from `pad1.at[1]`).
2. Apex = pad 1's own outward edge on that axis, offset further
   outward by the matching `courtyard_margin_x`/`courtyard_margin_y`
   value (falling back to `COURTYARD_MARGIN_MM` if the family doesn't
   declare one, consistent with how the courtyard itself already
   falls back) plus `PIN1_TRIANGLE_SILK_OFFSET_MM`; the perpendicular
   coordinate is pad 1's own center on that axis.
3. Base = two points `PIN1_TRIANGLE_DEPTH_MM` further outward than the
   apex, spread `±PIN1_TRIANGLE_HALF_HEIGHT_MM` along the perpendicular
   axis around pad 1's center.
4. Emit as a filled `Poly` (reusing the existing `Poly` geometry type
   already used for the `F.Fab` chamfer outline) on `F.SilkS`.

This generalizes beyond QFN's current left-side-only convention (any
of the four sides) using the same side-detection approach already
established in `_quad_side_groups`, so a future family with pin 1 on a
different side gets correct geometry for free — consistent with how
much of the rest of `_add_outline` is already written (generic
mechanism plus per-family param, not per-family special-cased code).

**Data change:** `data/kicad-fpdb.yaml` — add `pin1_marker_style:
triangle` to the `QFN` root's `params` block only. No other family's
yaml changes.

**Corner-mark bracket:** left untouched. The ~0.02mm shortened leg in
the real files is not reproduced — visually indistinguishable at any
normal zoom level, and QFN's corner marks already carry a documented,
larger approximation (`CORNER_MARK_MM = 0.3` vs. real 0.475-0.725mm).

## Non-goals

- Shortening the corner-mark bracket leg at pin 1's corner to match
  the real ~0.02mm exactly.
- Changing the pin-1 marker for any other family (DIP, SOIC, SOT,
  LQFP, R/C, etc.) — all keep the existing circle convention.
- QFN's `_ThermalVias` siblings or multi-EP variants — unrelated,
  already tracked separately in `CLAUDE.md`'s TODO.

## Verification

- Extend `tests/test_pipeline_regression.py`'s existing per-case
  comparison: for QFN cases, parse the real file's `F.SilkS` `fp_poly`
  pin-1 marker and compare against the generated triangle's three
  points (reusing the same tolerance convention already used
  elsewhere in that file).
- Visual review via `python -m kicad_fpdb.visual_compare` — regenerate
  `renders/review.html` and confirm the triangle renders correctly
  and doesn't overlap adjacent silk/courtyard geometry on the smallest
  (QFN-12) and largest (QFN-80) variants.
