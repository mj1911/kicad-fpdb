# Corner marks extend to the courtyard jog

Date: 2026-09-17

## Problem

`_add_corner_marks` (`kicad_fpdb/pipeline.py`) draws LQFP and QFN's
F.SilkS corner-mark brackets — two short legs per corner, pointing
inward from the oversized silk body corner — using one fixed constant,
`CORNER_MARK_MM = 0.3`, for every variant of both families. This was
already documented as a deliberate approximation ("real KiCad varies
this per package... this project uses one fixed value for all
variants"). The request here: instead of a fixed length, each leg
should extend exactly until it reaches the courtyard's own "jog" — the
point where the stepped F.CrtYd outline transitions from following the
plain body corner to following the adjacent side's pad-arm edge — so
the mark visually connects to the courtyard's own step instead of
stopping at an arbitrary length.

## Investigation

Dumped the real generated geometry for `LQFP-32` to see the actual
relationship between the silk corner and the courtyard's stepped
shape:

- Silk body corner (top-left): `(-3.61, -3.61)`
- Current corner-mark legs: inward by fixed `0.3mm`, ending at
  `(-3.31, -3.61)` (horizontal) and `(-3.61, -3.31)` (vertical)
- Courtyard's own top-left region traces: `(-5.175, -3.3) →
  (-3.75, -3.3) → (-3.75, -3.75) → (-3.3, -3.75) → (-3.3, -5.175)`

The two relevant "jog" points are `(-3.75, -3.3)` (where the courtyard
transitions from the left pad-arm's edge to the plain body corner) and
`(-3.3, -3.75)` (same transition on the top side). The horizontal
silk leg (running along the top edge, `y = -3.61`) should extend in x
until `x = -3.3` — the x-coordinate of the *top* side's own arm edge.
The vertical silk leg (running along the left edge, `x = -3.61`)
should extend in y until `y = -3.3` — the y-coordinate of the *left*
side's own arm edge. For LQFP-32 this works out to `0.31mm` instead of
the current `0.3mm` (a near-coincidental match); the point of the
change is that this is now computed exactly per variant rather than
approximated by one constant for every variant of both families.

This confirms the earlier direction question: legs keep pointing
**inward** (unchanged) — only the length changes, now derived from the
adjacent side's own courtyard-arm edge instead of a fixed constant.

Also confirmed: `_add_exposed_pad` (QFN's center EP/thermal pad) runs
*after* `_add_outline` in `generate_footprint`, so `geometry.pads`
never includes the EP pad when `_quad_side_groups` — reused for this
calculation — classifies pads into left/right/top/bottom groups. No
interference from QFN's exposed pad.

## Design

**No new param needed.** `_add_corner_marks` is only ever called from
one place (`_add_outline`'s `elif body_size is not None:` branch), and
that branch is only ever reached by LQFP and QFN — the fix applies to
both automatically, with zero yaml changes.

**Change `_add_corner_marks`'s signature** to additionally accept the
per-side arm rects (already computed elsewhere via
`_quad_side_groups`) and the courtyard margins:

```python
def _add_corner_marks(geometry, sx0, sy0, sx1, sy1,
                       side_groups: dict[str, tuple[float, float, float, float]] | None = None,
                       mx: float = COURTYARD_MARGIN_MM, my: float = COURTYARD_MARGIN_MM) -> None:
```

**Per-corner leg length**, replacing the fixed `CORNER_MARK_MM * x_dir`
/ `CORNER_MARK_MM * y_dir`:

- The horizontal leg at a corner is bounded by the `top` or `bottom`
  side's arm rect (whichever side the corner is on, by its `y`):
  `edge_x = side_rect[0] - mx` if the leg points in `+x` (i.e.
  `x_dir > 0`), else `side_rect[2] + mx`. Leg endpoint x is `edge_x`
  directly (not `cx + x_dir * length`) — the sign falls out naturally
  since `edge_x` already sits on the correct side of `cx`.
- The vertical leg is bounded by the `left` or `right` side's arm rect
  (by the corner's `x`): `edge_y = side_rect[1] - my` if `y_dir > 0`,
  else `side_rect[3] + my`.
- **Fallback:** if `side_groups` is `None` or the relevant side is
  missing from it, keep today's fixed `CORNER_MARK_MM` behavior for
  that leg. Not reachable today (LQFP/QFN's `quad_perimeter` always
  populates all four sides) but keeps the function safe to call with
  partial data, e.g. from existing unit tests that construct geometry
  by hand.

**Caller change** (`_add_outline`'s `elif body_size is not None:`
branch): compute `side_groups = _quad_side_groups(geometry.pads)` once
and pass it, along with the already-in-scope `mx`/`my`, into
`_add_corner_marks`.

## Non-goals

- No change to which two sides bound which leg, or to the legs'
  direction (inward) — only the length formula changes.
- No change to any family other than LQFP/QFN (no other family reaches
  this code path).
- No change to the courtyard or F.Fab outline geometry themselves —
  only the F.SilkS corner-mark legs.

## Verification

- Update `tests/test_pipeline_outline.py`'s existing
  `test_add_outline_with_body_size_draws_corner_marks` (currently
  asserts fixed `±0.3mm` legs) to assert the new computed endpoints for
  the `_qfp32_geometry()` fixture, worked out by hand from that
  fixture's real pad positions and margins.
- Add a case exercising the fallback (`side_groups=None` or a partial
  dict) to confirm the old fixed-length behavior still applies when
  side data isn't available.
- Run the full test suite, including the regression suite (`pytest
  tests/test_pipeline_regression.py`) to confirm no LQFP/QFN case
  regresses on pad/courtyard/fab geometry (this change only touches
  F.SilkS corner marks, which the regression suite doesn't currently
  assert on beyond their existing endpoint-count checks in the unit
  tests).
- Visual review via `python -m kicad_fpdb.render_png --family LQFP QFN`
  (or `visual_compare`) to confirm the marks visibly reach the
  courtyard jog on a small (QFN-12) and large (LQFP-208) variant.
