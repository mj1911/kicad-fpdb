# F.Fab Body Outline — Design Spec

Date: 2026-09-15

## Background

Real KiCad footprints draw the true physical component body on F.Fab —
an assembly-drawing outline distinct from both the F.SilkS body (often
deliberately oversized for visibility, per this project's existing
`body_width`/`body_size`) and the F.CrtYd courtyard (margin-expanded for
placement clearance). Investigated real DIP-16, SOIC-8, QFP-32, R-0603,
and SOT-23 reference footprints.

## Investigation: reuse the existing "true body" values wherever possible

For SOIC, QFP, and SOT-23, the real F.Fab body rect's dimensions match
**exactly** the true-body values these families already declare for
their courtyard (`courtyard_body_width`/`courtyard_body_margin` for
SOIC's dual-row shape, `courtyard_body_size` — scalar for QFP, tuple for
SOT-23 — for the quad/asymmetric shapes). No new yaml values needed for
these three families beyond an opt-in flag and a chamfer size.

DIP has no existing "true body" value (its courtyard uses a flat
asymmetric margin on the pad bbox directly, not a union with a separate
body rect), so it needs its own new `fab_body_width`/`fab_body_margin`
pair — measured directly from real DIP-16 (narrow), DIP-16 r (regular),
and DIP-24 w (wide): width is 6.35mm for narrow/regular and 14.73mm for
wide (not derivable from the existing per-class `body_width` dict —
different real values, own dict), margin is 1.27mm shared across all
three width classes.

R/C chip passives similarly have no reusable true-body value (their
courtyard is a flat margin-expanded pad bbox), so each declares its own
new `fab_body_size` (a plain rectangle, no chamfer — chip passives have
no polarity, matching their existing `pin1_marker: false`).

## Investigation: the corner chamfer

DIP, SOIC, QFP, and SOT-23 (all four variants) each cut a chamfer into
the top-left corner (above pad 1) of their F.Fab body — a diagonal cut
of a fixed size per family (not derived from any other declared value):
DIP 1.0mm, SOIC 0.975mm, QFP 1.0mm, SOT-23 (base) 0.325mm, SOT-23-5/6/8
0.4mm. R/C have no chamfer at all (plain rectangle) — consistent with
already having no pin-1 marker.

Note SOT-23 and SOT-23-5 keep this F.Fab chamfer even though their own
F.SilkS pin-1 circle marker was removed (per the earlier "asymmetric
layout is unambiguous" decision) — the two are independent signals on
different layers, and real KiCad keeps the F.Fab chamfer regardless.

## Design

### `kicad_fpdb/pipeline._add_outline`

Five new params:

- `fab_body_width: float | None`, `fab_body_margin: float | None` — a
  family's own true-body pair (DIP), same dual-row centering style as
  the existing `body_width`/`body_margin`.
- `fab_body_size: float | tuple[float, float] | None` — a family's own
  true-body size (R/C), same centering style as `courtyard_body_size`.
- `fab_outline: bool` — when true and neither of the above is given,
  reuse the already-declared `courtyard_body_width`/`courtyard_body_margin`
  or `courtyard_body_size` instead (SOIC/QFP/SOT-23).
- `fab_chamfer: float | None` — corner-cut size; when given, emit a
  5-point `Poly` (`fill="no"`) instead of a plain `Rect`.

Resolution order: `fab_body_width`+`fab_body_margin` → `fab_body_size` →
(`fab_outline` and) `courtyard_body_width`+`courtyard_body_margin` →
(`fab_outline` and) `courtyard_body_size`. A family declaring none of
these gets no F.Fab body geometry at all (unaffected).

`generate_footprint` pops and threads all five the same way as every
other outline param.

### `data/kicad-fpdb.yaml`

- `DIP` root: `fab_body_width: {narrow: 6.35, regular: 6.35, wide: 14.73}`,
  `fab_body_margin: 1.27`, `fab_chamfer: 1.0`.
- `SOIC` root: `fab_outline: true`, `fab_chamfer: 0.975`.
- `QFP-32`/`QFP-48`: `fab_outline: true`, `fab_chamfer: 1.0`.
- `SOT-23`: `fab_outline: true`, `fab_chamfer: 0.325`.
- `SOT-23-5`/`SOT-23-6`/`SOT-23-8`: `fab_outline: true`, `fab_chamfer: 0.4`.
- Each `R-*`/`C-*` variant: its own `fab_body_size: [w, h]`, hand-copied
  from the real reference footprint (no chamfer) — same
  no-shared-formula convention as `silk_y`/`silk_half_length`.

## Non-goals

- Matching DIP's real fp_line-per-edge style exactly — a single 5-point
  `Poly` (`fill="no"`) draws the identical visible outline and is reused
  for every chamfered family, real KiCad's own file format detail aside.
- TSOT-23/SOT-23W (not yet added to this project at all, per the
  SOT-23 family spec's own non-goals).

## Testing

- Unit tests on `_add_outline` for each of the four resolution paths
  (own width/margin, own size, reused width/margin, reused tuple size)
  plus a plain-rect-no-chamfer case and a no-params regression guard.
- `tests/test_pipeline_outline.py` exact-coordinate assertions at the
  `generate_footprint` level for representative variants of each
  family.
- Regenerate `renders/review.html` and visually confirm.
