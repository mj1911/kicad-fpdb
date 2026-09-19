# Extend the pin-1 triangle marker to SOT-23-6/-8 (and TSOT-23-6/-8)

Date: 2026-09-17

## Problem

The pin-1 triangle marker (`pin1_marker_style: triangle`) covers QFN,
SOIC, and LQFP so far. SOT-23's real reference footprints also carry a
triangle marker, but SOT-23 and SOT-23-5 currently have
`pin1_marker: false` — their asymmetric pin layouts (2+1, 3+2) can
only be placed one physical way, so no pin-1 indicator is functionally
needed there, unlike SOT-23-6/-8 (3+3, 4+4), which are symmetric and
could be placed rotated 180° incorrectly. Per direction: keep that
policy exactly as-is (only symmetric, backwards-placeable packages get
a marker at all) — this spec only covers giving SOT-23-6/-8 (and their
byte-identical TSOT-23-6/-8 aliases) the triangle style instead of the
circle they draw today. SOT-23/SOT-23-5 stay untouched
(`pin1_marker: false`, no marker of any style).

## Investigation

Extracted pad 1 and the real `F.SilkS` triangle from SOT-23-6 and
SOT-23-8's reference files and compared against the formulas already
established for QFN (`axis="x"`) and SOIC/LQFP (`axis="y"`,
body-anchored). Both variants match the **SOIC-narrow formula and
constants exactly** — no new geometry, size class, or anchor constant
needed:

- `SOT-23-6`: pad 1 at `(-1.1375, -0.95)`, size `(1.325, 0.6)`. Real
  triangle apex `(-1.45, -1.51)`, base `(-1.69, -1.84)` / `(-1.21,
  -1.84)`. Extension axis Y: `apex_y = (py - ph/2) - courtyard_margin_y
  - 0.01 = (-0.95 - 0.3) - 0.25 - 0.01 = -1.51` — **exact**. Depth
  `|-1.84 - (-1.51)| = 0.33mm`, half-width `|-1.69 - (-1.45)| = 0.24mm`
  — the existing "small" size class. Perpendicular anchor:
  `courtyard_body_size = [1.6, 2.9]` (SOT declares this as a
  `[width, height]` tuple, not a scalar like QFN/LQFP), body half-width
  `1.6 / 2 = 0.8`; `apex_x = -(0.8 + anchor) = -1.45` gives
  `anchor = 0.65mm` — **the same constant SOIC's narrow class already
  uses**.
- `SOT-23-8`: pad 1 at `(-1.1375, -0.975)`, size `(1.325, 0.5)`. Real
  triangle apex `(-1.45, -1.49)`, base `(-1.69, -1.82)` / `(-1.21,
  -1.82)`. Same formula: predicted apex_y `= (-0.975 - 0.25) - 0.25 -
  0.01 = -1.485`, real `-1.49` (0.005mm residual, same rounding-noise
  category already accepted elsewhere). Depth `0.33mm`, half-width
  `0.24mm` — small. Anchor: body half-width `0.8` (same
  `courtyard_body_size`, shared with SOT-23-6 via the existing
  `SOT-23-5-6-8` yaml node), `apex_x = -1.45` gives `anchor = 0.65mm`
  — exact match again.

TSOT-23-6/-8 are confirmed byte-identical geometry to SOT-23-6/-8
(already established when TSOT was added — see `CLAUDE.md`), so the
same formula applies without separate verification.

**One real code fix is needed**, not a new mechanism: the existing
body-anchor calculation
(`kicad_fpdb/pipeline.py`, the `pin1_triangle_anchor_mm is not None`
branch) computes `body_half` as `courtyard_body_width / 2` or
`courtyard_body_size / 2` — the latter assumes `courtyard_body_size`
is a plain number (true for QFN/LQFP). SOT declares it as a
`[width, height]` tuple (a non-square true body, per the
`asymmetric_dual_row` design), so dividing it directly by 2 would
raise `TypeError`. Needs a tuple-aware branch taking index `0` (width)
for this perpendicular-axis calculation.

## Design

**No new params or constants.** Reuses `pin1_marker_style: triangle`,
`pin1_triangle_axis: y`, `pin1_triangle_size: small` (already the
default), and `pin1_triangle_anchor_mm: 0.65` — the exact same values
SOIC's narrow class already declares.

**Code fix** in `kicad_fpdb/pipeline.py`'s triangle branch: change

```python
body_half = (
    courtyard_body_width / 2 if courtyard_body_width is not None else courtyard_body_size / 2
)
```

to handle a tuple `courtyard_body_size` (take index `0`, the width) in
addition to the existing scalar case.

**Data change** (`data/kicad-fpdb.yaml`): add to the `SOT-23-5-6-8`
intermediate node's shared params (`&sot_5_6_8_shared`, already the
node `courtyard_body_size` and `fab_chamfer` are shared from):

```yaml
pin1_marker_style: triangle
pin1_triangle_axis: y
pin1_triangle_size: small
pin1_triangle_anchor_mm: 0.65
```

This single edit point covers all 6 downstream descriptors (SOT-23-5,
SOT-23-6, SOT-23-8, and TSOT-23-5/-6/-8 via the existing
`*sot_5_6_8_shared` yaml alias) — SOT-23-5 and TSOT-23-5 stay
marker-less because their own `pin1_marker: false` override still
takes precedence (a `pin1_marker_style` value is irrelevant when
`pin1_marker` itself is false; nothing to change there). Plain SOT-23
(3-pin, a sibling node, not part of `SOT-23-5-6-8`) is untouched
entirely.

## Non-goals

- SOT-23 and SOT-23-5 stay `pin1_marker: false` — no marker of any
  style, unchanged.
- No change to any other family.

## Verification

- Add unit tests to `tests/test_pipeline_outline.py` for the tuple-body
  anchor fix (direct `_add_outline` call with a tuple
  `courtyard_body_size`), following the same pattern as the SOIC/LQFP
  triangle tests.
- Add structural presence tests (`generate_footprint("SOT-23-6", ...)`)
  mirroring the existing SOIC-8/LQFP-32 ones.
- `kicad_fpdb.footprint_diff.TRIANGLE_MARKER_FAMILIES` gains both
  `"SOT"` and `"TSOT"` (`"TSOT-23-6".split()[0].split("-")[0]` is
  `"TSOT"`, a distinct family head from `"SOT"`) so the regression
  suite and `verify_library.py` check SOT-23-6/-8/TSOT-23-6/-8 against
  their real files; SOT-23/SOT-23-5/TSOT-23-5 correctly report no
  triangle from either side (both `pin1_marker: false`) even though
  `family in TRIANGLE_MARKER_FAMILIES` is now true for them too —
  `diff_footprint`'s existing "both real and generated have none"
  fallthrough (no `elif`/`else` branch fires when `parse_silk_triangle`
  returns `None` on both sides) already handles this correctly without
  any extra logic, but worth a regression test making that explicit.
- Run `python -m kicad_fpdb.verify_library --family SOT TSOT` for a
  full report.
- Visual review via `python -m kicad_fpdb.render_png --family SOT
  TSOT`.
