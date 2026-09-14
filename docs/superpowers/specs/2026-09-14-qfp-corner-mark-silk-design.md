# QFP Corner-Mark Silk Outline — Design Spec

Date: 2026-09-14

## Background

`docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`
replaced the generic pad-bbox-derived F.SilkS rectangle with a real
body-derived one for DIP and SOIC, explicitly scoping QFP out. QFP still
uses the original generic outline (pad bounding box + flat margin).

Real KiCad's own QFP footprints don't draw a full silk rectangle at all —
they draw four small L-shaped corner brackets (plus the same style of
filled pin-1 triangle this project already draws generically). Checked
directly against both of this project's real QFP reference footprints:

- `LQFP-32_7x7mm_P0.8mm.kicad_mod`: corner brackets at x=±3.61, y=±3.61,
  each leg 0.3mm long (e.g. one corner's two legs run from (-3.61,-3.61)
  to (-3.31,-3.61) and to (-3.61,-3.31)).
- `LQFP-48_7x7mm_P0.5mm.kicad_mod`: same corner position (±3.61, ±3.61 —
  both are 7×7mm bodies), leg length 0.45mm instead of 0.3mm.

The corner position (3.61mm half-extent) is a real physical body-size
constant, independent of pad position — the same "real, not pad-derived"
pattern as DIP's `body_width`/SOIC's `body_width`.

## Goals

- Add a `body_size` descriptor param to QFP-32 and QFP-48 (7.22mm — the
  real value for both, since both reference cases are 7×7mm packages).
- Draw four corner-mark L-brackets from it instead of the generic
  pad-bbox rectangle, reusing the existing pin-1 triangle marker
  unchanged (it already anchors to "nearest body corner", which still
  makes sense with corner marks).
- Leave courtyard (F.CrtYd) generic, as with DIP/SOIC.

## Non-goals

- Making QFP a formula-driven family (deriving `pad_offset` from a
  declared body size) — that's a separately parked TODO in `CLAUDE.md`
  and out of scope here. QFP-32/QFP-48 remain fully-enumerated children;
  this spec only adds `body_size` alongside their existing params.
- Exact per-variant leg-length accuracy. Real KiCad uses 0.3mm for
  QFP-32 and 0.45mm for QFP-48; this project uses one fixed constant
  (0.3mm) for all QFP corner marks, consistent with the "symbolic, not
  exact" stance already established for SOIC's margin.
- Chip passives (R/C) — untouched, still generic.

## Design

### Data model (`data/kicad-fpdb.yaml`)

Add `body_size: 7.22` to both `QFP-32` and `QFP-48`'s existing `params`
blocks (a plain scalar — no width-class variants exist for QFP, unlike
DIP).

### Pipeline (`kicad_fpdb/pipeline.py`)

`generate_footprint` also pops `body_size` from resolved params (outline
input, not a generator input) and passes it to `_add_outline` alongside
the existing `body_width`/`body_margin`.

`_add_outline` gains a third outline mode, checked after the existing
body_width/body_margin rectangle mode:

```python
def _add_outline(geometry, body_width=None, body_margin=None, body_size=None) -> None:
    ...  # courtyard rect unchanged

    if body_width is not None and body_margin is not None:
        ...  # existing DIP/SOIC rectangle mode, unchanged
    elif body_size is not None:
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        center_y = (min_py + max_py) / 2
        half = body_size / 2
        sx0, sx1 = center_x - half, center_x + half
        sy0, sy1 = center_y - half, center_y + half
        _add_corner_marks(geometry, sx0, sy0, sx1, sy1)
    else:
        ...  # existing generic pad-bbox fallback, unchanged

    # pin-1 marker: unchanged, still uses sx0/sy0/sx1/sy1 from whichever
    # branch ran
```

A new `_add_corner_marks(geometry, sx0, sy0, sx1, sy1)` helper draws two
short `Line`s per corner (a new `CORNER_MARK_MM = 0.3` constant, sibling
to the existing `SILK_MARGIN_MM`/`PIN1_MARKER_MM` constants), each leg
running inward from the corner along one axis — no full-perimeter lines
are drawn for this mode. It does **not** draw a `Rect`; the courtyard
`Rect` is unaffected and unrelated.

The pin-1 marker logic is untouched — it already computes `sx0/sy0/sx1/sy1`
generically regardless of which branch produced them, and picks the
nearest corner to pad 1.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (pad geometry is untouched).
- Unit tests on `_add_outline`/`_add_corner_marks` asserting the exact
  8 line segments (2 per corner × 4 corners) for known `body_size` inputs,
  matching the real coordinates above (with this project's fixed 0.3mm
  leg length rather than QFP-48's real 0.45mm).
- Regenerate `renders/review.html` and visually confirm QFP-32/QFP-48
  show four corner brackets positioned like the reference panel's real
  corner marks (leg length will look slightly shorter for QFP-48, per
  the accepted non-goal above).
