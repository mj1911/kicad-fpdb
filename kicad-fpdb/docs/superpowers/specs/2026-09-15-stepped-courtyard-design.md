# Real-Shaped Library Courtyards — Design Spec

Date: 2026-09-15

## Background

Only DIP has a real (asymmetric-margin) F.CrtYd courtyard today
(`docs/superpowers/specs/2026-09-14-dip-courtyard-margin-design.md`).
SOIC, QFP, and the chip passives (R/C) still use the generic flat 0.5mm
pad-bounding-box margin (`COURTYARD_MARGIN_MM` in `kicad_fpdb/pipeline.py`).
This was an explicit parked TODO item from the DIP courtyard work.

## Investigation

Checked directly against real KiCad reference footprints:

**Chip passives (R/C):** still a single rectangle, not stepped — just the
wrong margin. Measured margin (pad bbox to F.CrtYd rect, both axes equal):

| Footprint | margin |
|---|---|
| R-0402 | 0.15mm |
| R-0603 | 0.255mm (round to 0.25) |
| R-0805 | 0.25mm |
| C-0603 | 0.255mm (round to 0.25) |

No shared formula across sizes (consistent with this project's existing
`silk_y`/`silk_half_length` chip-passive convention — each value declared
per variant, copied verbatim from its reference footprint).

**SOIC:** a genuinely stepped shape (12 `fp_line` segments in the real
files), but it resolves exactly to **the union of two rectangles, each
independently expanded by a flat 0.25mm margin**:

1. The *true physical body* rectangle (e.g. 3.9mm × 4.9mm for SOIC-8/
   SOIC-14 — the width/length named in the footprint's own filename) —
   **not** the existing `body_width` param (4.12mm), which is a
   deliberately oversized value used only for the F.SilkS outline's
   visual clarity.
2. The full pad bounding box.

Verified exactly against SOIC-8 (courtyard corners at
`(±2.2, ±2.7)`/`(±3.7, ±2.46)`) and SOIC-14 (`(±2.2, ±4.58)`/
`(±3.7, ±4.36)`, the 4.58 vs. the formula's 4.6 being the same ~0.02mm
SOIC approximation already documented in the real-body-silk-outline spec).

**QFP:** also stepped (20 segments), and resolves to the same model
generalized to four sides: **union of the true physical body square
(7.0mm × 7.0mm — not the existing `body_size` param of 7.22mm, again an
oversized silk-only value) and one pad-group rectangle per side**, each
independently expanded by the same flat 0.25mm margin. Verified exactly
against LQFP-32 (arms to `±5.18`/`±3.3`, body corner `±3.75`) and
LQFP-48 (arms to `±5.15`/`±3.15`, body corner `±3.75`) — the latter with
no rounding slop at all.

Each side's pad group can be derived purely from existing pad geometry,
with no new data: a `quad_perimeter` pad belongs to the left/right group
when `size[0] > size[1]` (it's wider than tall — points outward along X)
and to the top/bottom group otherwise, split further by the sign of its
own position. This generalizes to any future quad-perimeter family
without change.

## Goals

- Replace the flat 0.5mm courtyard margin for R/C with their real
  per-variant margins (data-only change).
- Give SOIC and QFP their real stepped F.CrtYd shape via a shared
  "union of margin-expanded rectangles" model.
- Keep the shape-construction logic generic enough that a third
  quad-perimeter family (e.g. a future QFN) gets a correct stepped
  courtyard automatically, without new code.

## Non-goals

- Any change to DIP's courtyard (already real, already a plain
  rectangle in actual KiCad — no stepping needed).
- Any change to F.SilkS geometry, `body_width`, or `body_size` — those
  stay exactly as they are; the new `courtyard_body_size` values are
  courtyard-only and intentionally different numbers.
- General-purpose polygon boolean ops beyond axis-aligned rectangle
  union (no rotation, no holes, no non-rectilinear shapes).

## Design

### `kicad_fpdb/rect_union.py` (new module)

```python
def union_outline(rects: list[tuple[float, float, float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Boundary of the union of axis-aligned rects, as an ordered closed loop
    of (start, end) segments. Assumes the union is simply connected (no
    holes) — true for every shape this project constructs."""
```

Implementation: coordinate-compress all rect edges into a sorted grid,
mark each grid cell filled if it lies inside any rect, collect every
filled-cell edge whose neighbor is unfilled or off-grid as a boundary
edge, merge collinear adjacent edges, then walk the edge graph from an
arbitrary start into one ordered loop (every vertex has degree 2 for a
hole-free rectilinear region — no branch/merge handling needed).

Pure function over plain tuples — no dependency on `kicad_fpdb.geometry`
— so it's unit-testable in isolation (e.g.: two overlapping rects forming
a plus/cross; five rects forming the QFP topology) independent of KiCad
or the pipeline.

### `kicad_fpdb/pipeline.py`

New `_add_outline` param: `courtyard_body_size: tuple[float, float] | None
= None` (true physical width/length, courtyard-only).

The courtyard block currently always emits one `Rect` from the flat/
asymmetric margin. When `courtyard_body_size` is given, it instead builds
a rect list and calls `union_outline`, appending each returned segment as
`Line(start=s, end=e, layer="F.CrtYd")` to `geometry.lines`:

- **When also in the `body_width`/`body_margin` branch (dual-row/SOIC
  shape):** `rects = [body_rect, pad_bbox]`, where `body_rect` is
  centered via the same pad-center-extent logic already used for the
  silk body rect, sized from `courtyard_body_size` instead of
  `body_width`, and `pad_bbox` is the existing `pad_bounding_box(...)`
  result already computed at the top of `_add_outline`. Both
  independently expanded by `(courtyard_margin_x, courtyard_margin_y)`.
- **When in the `body_size` branch (quad/QFP shape):** `rects =
  [body_square] + [group_bbox for each of the 4 side groups]`, body
  square sized from `courtyard_body_size` (not `body_size`), side groups
  derived from pad geometry as described above. Same margin expansion.
- Without `courtyard_body_size`, behavior is byte-for-byte unchanged
  (still the single `Rect` from `courtyard_margin_x`/`_y`, defaulting to
  `COURTYARD_MARGIN_MM`) — DIP and any future generic family are
  unaffected.

`generate_footprint` pops `courtyard_body_size` from resolved params
alongside the other outline params and threads it through, same pattern
as every other outline param already there.

### `data/kicad-fpdb.yaml`

```yaml
SOIC:
  params:
    ...
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    courtyard_body_size: [3.9, 4.9]

QFP:
  children:
    QFP-32:
      params: {..., courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, courtyard_body_size: [7.0, 7.0]}
    QFP-48:
      params: {..., courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, courtyard_body_size: [7.0, 7.0]}

R:
  children:
    R-0402:
      params: {..., courtyard_margin_x: 0.15, courtyard_margin_y: 0.15}
    R-0603:
      params: {..., courtyard_margin_x: 0.25, courtyard_margin_y: 0.25}
    R-0805:
      params: {..., courtyard_margin_x: 0.25, courtyard_margin_y: 0.25}

C:
  children:
    C-0603:
      params: {..., courtyard_margin_x: 0.25, courtyard_margin_y: 0.25}
```

(SOIC's `courtyard_body_size` for a *wide* SOIC variant, if one is added
later, would need its own physical width/length — same pattern DIP
already follows for `body_width` keyed by width class. Not needed yet
since only narrow SOIC variants exist in `data/kicad-fpdb.yaml` today.)

## Testing

- Unit tests directly on `rect_union.union_outline`: a two-rect
  cross/plus shape, and a five-rect QFP-topology shape, asserting the
  exact returned segment loop.
- Extend the pipeline regression suite
  (`tests/test_pipeline_regression.py`) with exact-coordinate courtyard
  assertions for SOIC-8, SOIC-14, LQFP-32, and LQFP-48, using the real
  values measured above.
- Existing DIP/chip-passive courtyard tests must keep passing unchanged
  (regression guard that the `courtyard_body_size`-absent path is
  untouched).
- Regenerate `renders/review.html` and visually confirm SOIC and QFP
  courtyards now show the stepped shape matching their reference panel.
