# SOT-23 Family — Design Spec

Date: 2026-09-15

## Background

SOT-23 packages (JEDEC TO-236 for the 3-pin base package, MO-178 for the
5/6/8-pin variants) have an asymmetric pin layout no existing generator
supports: 2 pins on one side and 1 on the other (base SOT-23), or uneven
splits like 3+2 (SOT-23-5). `dual_row_grid` requires an even `pin_count`
split evenly between two symmetric columns.

Investigated 4 real reference footprints in
`Package_TO_SOT_SMD.pretty/`: SOT-23, SOT-23-5, SOT-23-6, SOT-23-8.
SOT-23-6 and SOT-23-8 have even, symmetric splits (3+3, 4+4) and would
already fit `dual_row_grid` — but their pin *positions* don't follow a
simple evenly-spaced-from-center formula when a variant has fewer pins
than the family's full lead-frame grid (SOT-23-5's right column uses only
the two *outer* positions of a 3-position grid, skipping the middle one,
rather than being independently re-centered with its own pitch). All four
variants are therefore driven by explicit per-pin Y-offset lists rather
than a `pin_count`-derived formula, consistent with this project's
existing convention for genuinely irregular real geometry (e.g.
`silk_y`/`silk_half_length` on chip passives).

## Goals

- New generator producing exact, verified pad geometry for asymmetric
  two-column layouts (2+1, 3+2, 3+3, 4+4 confirmed; general enough for
  any left/right counts).
- Real stepped F.CrtYd courtyard for these 4 variants, reusing the
  existing `union_outline` machinery.
- Real notched-body F.SilkS outline for these 4 variants.
- Pin-1 marker (this project's own circle convention) and F.Fab
  reference text (rotated 90°, matching real KiCad for this tall/narrow
  package), consistent with every other family.

## Investigation: courtyard is the existing union model, no new code needed

Verified numerically against all 4 real files: SOT-23's courtyard
(16 segments) and SOT-23-5's (as-verified, same shape family) both
resolve exactly to **the union of the true physical body rect and every
individual pad's own bounding box**, each independently expanded by a
flat 0.25mm margin — the same union-of-rectangles model already built for
SOIC/QFP in `kicad_fpdb/rect_union.py`.

The one refinement: SOT's asymmetric columns can leave a *gap* between
two pins on the same side (SOT-23-5's right column populates only 2 of a
3-position grid). Grouping "all pads on one side" into a single rect (as
the existing QFP code does via `_quad_side_groups`) would incorrectly
bridge that gap. Using **one rect per individual pad** instead (dropping
the grouping step entirely) handles this automatically — verified that
adjacent same-side pads still merge into one continuous arm wherever
their margin-expanded boxes overlap (true whenever pitch is smaller than
2× the margin, true for every pad pitch in this project so far), while a
genuine gap (SOT-23-5's skipped middle position) correctly stays open.
This is a strict generalization of the existing QFP model, not a
different one — QFP is left untouched since its own per-side grouping
already produces the identical result for its own (always fully
populated) pin layout.

## Investigation: silk needs a new "explicit segment list" escape hatch

Real silk is a body rectangle with **notches cut out** wherever pads
cross the left/right edges (subtractive), the opposite topology from the
courtyard's additive union — not expressible with `union_outline`.
Reverse-engineering a general notch-subtraction algorithm isn't
justified for 4 variants; instead, hand-copy each variant's exact real
segment list, the same "no shared formula, verified per-variant"
convention chip-passive silk already uses. A new generic
`silk_segments` param on `_add_outline` (a literal list of `(start,
end)` line pairs, emitted verbatim to F.SilkS, bypassing every formula
branch) makes this a reusable escape hatch for any future family with
similarly irregular silk, not a SOT-specific special case.

Real KiCad also draws a small pin-1 *triangle* (`fp_poly`) on these SOT
footprints — not matched; this project already has its own pin-1 circle
marker convention (`docs/superpowers/specs/2026-09-14-pin1-circle-
marker-design.md`), used here unchanged like every other family.

## Design

### `kicad_fpdb/generators/asymmetric_dual_row.py` (new)

```python
def asymmetric_dual_row(left_offsets: list[float], right_offsets: list[float],
                         row_spacing: float, pad_size: tuple[float, float],
                         pad_shape: str, pad_type: str,
                         drill: float | None = None) -> FootprintGeometry:
```

Pins 1..len(left_offsets) at `(-row_spacing/2, left_offsets[i])`, then
pins len(left_offsets)+1..end at `(row_spacing/2, right_offsets[j])` —
same left-then-right, explicit-position numbering convention every
other generator already uses, just reading Y positions from the given
lists instead of deriving them from a pitch formula. `roundrect_rratio`
uses the existing shared `clamped_roundrect_rratio`.

### `kicad_fpdb/pipeline._add_outline` changes

Two new params:

- `courtyard_body_size: tuple[float, float] | None` (reusing the name
  already used for QFP's *square* case — QFP passes a scalar today;
  widen it to accept `(w, h)` for a non-square true body, backward
  compatible since QFP's own `courtyard_body_size: 7.0` stays a plain
  float and squares are handled as `w == h`).
- `silk_segments: list[tuple[tuple[float,float],tuple[float,float]]] |
  None`: when given, emits each pair verbatim as an F.SilkS `Line` and
  skips every other silk branch.

Courtyard block, new elif branch (checked before the existing QFP
`courtyard_body_size` branch, since QFP's own generator never has
per-pad gaps to worry about and keeps its current per-side-group code
unchanged): when `courtyard_body_size` is a 2-tuple, build
`rects = [body_rect] + [pad_bounding_box([pad]) for pad in geometry.pads]`
(one rect per individual pad, no grouping), each independently expanded
by `(mx, my)`, then `union_outline`.

Silk block, new branch checked first: `if silk_segments is not None:`
emit each segment as a `Line(layer="F.SilkS")` and return early from the
silk dispatch (skip `body_width`/`body_size`/`silk_y`/`no_silk`
branches).

`generate_footprint` pops and threads both new params the same way as
every existing outline param.

### `data/kicad-fpdb.yaml`

```yaml
SOT-23:
  generator: asymmetric_dual_row
  variant_param: pin_count
  children:
    SOT-23:
      params: {left_offsets: [-0.95, 0.95], right_offsets: [0], row_spacing: 1.875,
               pad_size: [1.475, 0.6], pad_shape: roundrect, pad_type: smd,
               courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, courtyard_body_size: [1.8, 3.4],
               silk_segments: [...],  # 6 pairs, copied verbatim from the real file
               fab_reference_font_size: 0.72, fab_reference_thickness: 0.11, fab_reference_rotation: 90}
    SOT-23-5: {params: {left_offsets: [-0.95, 0, 0.95], right_offsets: [0.95, -0.95], row_spacing: 2.275,
               pad_size: [1.325, 0.6], ..., courtyard_body_size: [2.1, 3.4], silk_segments: [...] (7 pairs)}}
    SOT-23-6: {params: {left_offsets: [-0.95, 0, 0.95], right_offsets: [0.95, 0, -0.95], row_spacing: 2.275,
               pad_size: [1.325, 0.6], ..., courtyard_body_size: [2.1, 3.4], silk_segments: [...] (6 pairs)}}
    SOT-23-8: {params: {left_offsets: [-0.975, -0.325, 0.325, 0.975], right_offsets: [0.975, 0.325, -0.325, -0.975],
               row_spacing: 2.275, pad_size: [1.325, 0.5], ..., courtyard_body_size: [2.1, 3.4], silk_segments: [...] (6 pairs)}}
```

(Illustrative shape — exact per-variant values are hand-verified against
the real files during implementation, not re-derived here.)

`pin1_marker` is not declared (defaults `true`, same as SOIC/QFP) since
SOT-23 has no pad shape of its own that already indicates pin 1.

## Non-goals

- General notch-subtraction geometry algorithm — explicitly deferred;
  `silk_segments` is a verbatim escape hatch, not a formula.
- Matching real KiCad's pin-1 triangle marker — this project's own
  circle convention is used instead, per existing precedent.
- TSOT-23 variants (identical pad geometry to SOT-23-5/6/8, per
  investigation) or SOT-23W — future follow-up, not this batch.
- Any change to QFP's existing courtyard code — the per-pad-rect
  approach is additive (SOT's own new branch), QFP's own branch and its
  `_quad_side_groups` helper are untouched.

## Testing

- Unit tests on `asymmetric_dual_row` for pad count/position (all 4
  variants).
- `tests/test_pipeline_regression.py` (via `reference_cases.py`
  additions) for exact pad-geometry match against all 4 real files —
  the functionally critical check.
- `tests/test_pipeline_outline.py` exact-coordinate assertions for
  courtyard and silk on each variant.
- Regenerate `renders/review.html` and visually confirm.
