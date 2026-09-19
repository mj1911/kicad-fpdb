# THT Axial Resistor Design Spec

Date: 2026-09-15

## Background

All resistors in this project so far are SMD chip passives. Investigated
real `Resistor_THT.pretty/R_Axial_DIN0204/0207/0309/0414_*_Horizontal`
reference footprints (4 body sizes, one representative pitch each) to add
through-hole axial resistor coverage.

## Investigation

**Pads:** 2 round `thru_hole` pads at `(0, 0)` and `(pitch, 0)` — not
symmetric about `x=0` like SMD chip passives. `two_pad_chip` had no
`pad_type`/`drill` support and always centered pads; extended with
`pad_type`, `drill`, `centered` params (all defaulting to the existing
SMD-centered behavior).

**Silk:** an oversized body rectangle — reuses the *existing*
`body_width`/`body_margin` dual-row mechanism unchanged: with both pads
at `y=0`, `_pad_center_extent`'s Y range collapses to a single point, so
`body_margin` becomes a flat half-height "for free." Additionally, two
short lead lines run from each pad's own edge (+ a fixed 0.24mm
clearance, verified constant across all 4 body sizes) to the body
rectangle's edge — a new `silk_leads` flag.

**F.Fab:** the *true* body size is exactly `[L, D]` from the part's own
name (e.g. DIN0207 → `[6.3, 2.5]`) — no fudge factor at all, unlike
every oversized-silk family. Reuses the existing `fab_body_size`
mechanism unchanged. Leads here start exactly at the pad center (no
clearance) — a new `fab_leads` flag.

**Courtyard:** *not* the stepped union model SOIC/QFP/SOT use. Verified
by checking whether a specific point inside the real courtyard's
bounding box would be covered by the union of two separately-margined
rects (pad bbox and true body, each independently expanded 0.25mm) — it
would not be, yet the real courtyard is a single unbroken rectangle
covering that exact point. The real model is simpler: combine the raw
(unexpanded) pad bbox and true body bbox into one bounding box first,
*then* apply one flat 0.25mm margin. This happens to always produce a
plain rectangle for axial resistors because the pad bbox dominates in X
while the body dominates in Y. New `courtyard_includes_body` flag,
reusing the already-computed `fab_body_rect`.

Verified all of the above exactly (courtyard, true body, lead
clearance) against all 4 body sizes (DIN0204/0207/0309/0414); the 0.24mm
lead clearance and the flat-combined-bbox courtyard model both held with
zero deviation, not just the usual ~0.005mm rounding tolerance.

## Design

### `kicad_fpdb/generators/two_pad.py`

New `pad_type: str = "smd"`, `drill: float | None = None`,
`centered: bool = True` params.

### `kicad_fpdb/pipeline._add_outline`

Three new params, each reusing an existing mechanism rather than adding
a new geometry model:

- `silk_leads: bool` — inside the existing `body_width`/`body_margin`
  branch, draws 2 additional `Line`s from each extreme pad
  (`LEAD_CLEARANCE_MM = 0.24`, a new module constant) to the already-
  computed body rect edge.
- `fab_leads: bool` — inside the existing F.Fab body-drawing block,
  draws 2 additional `Line`s from each extreme pad's own center to the
  already-computed `fab_body_rect` edge.
- `courtyard_includes_body: bool` — in the existing flat-margin
  courtyard fallback (`else` branch), combines the raw pad bbox with
  `fab_body_rect` (moved earlier in the function so both the courtyard
  and F.Fab blocks can use it) before applying the flat margin, instead
  of using the pad bbox alone.

### `data/kicad-fpdb.yaml`

New `R-AXIAL0204`, `R-AXIAL0207`, `R-AXIAL0309`, `R-AXIAL0414` children
under the existing `R` root (inherits `pin1_marker: false`), each with
`generator: two_pad_chip`, `pad_type: thru_hole`, `centered: false`,
`silk_leads: true`, `fab_leads: true`, `courtyard_includes_body: true`,
and its own hand-verified `pad_pitch`/`pad_size`/`drill`/`body_width`/
`body_margin`/`fab_body_size` (no shared formula across DIN sizes,
same convention as chip-passive `silk_y`/`silk_half_length`).

## Non-goals

- Vertical-mount axial resistors (bent-lead, different pitch-vs-body
  relationship) — horizontal only, this batch.
- `R_Array_SIP*` and other THT resistor form factors — future follow-up.
- A shared formula deriving `body_width`/`fab_body_size` from the DIN
  class name — 4 body sizes is not enough evidence of a pattern beyond
  "hand-copy per variant," and the courtyard/lead-clearance findings
  already show real KiCad doesn't apply one consistent oversizing rule
  across body sizes.

## Testing

- Unit tests on `two_pad_chip`'s new params.
- `_add_outline` unit tests for `silk_leads`, `fab_leads`, and
  `courtyard_includes_body` (plus a regression guard that
  `fab_body_size` alone, without the new flag, doesn't change existing
  chip-passive courtyard behavior).
- `tests/test_pipeline_regression.py` pad-geometry checks for all 4 new
  variants against the real reference footprints.
- Regenerate `renders/review.html` and visually confirm.
