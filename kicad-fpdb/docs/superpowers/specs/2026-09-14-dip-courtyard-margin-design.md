# DIP Courtyard Margin Tightening — Design Spec

Date: 2026-09-14

## Background

`_add_outline()`'s courtyard (F.CrtYd) rectangle is currently the pad
bounding box expanded by a single flat `COURTYARD_MARGIN_MM = 0.5` on
every side, for every family. Real KiCad's DIP courtyards use two
different margins depending on axis, making ours visibly too wide
perpendicular to the pin rows.

Checked directly against five real DIP reference footprints (three pin
counts, three row-spacing widths):

| Footprint | margin_x (perpendicular to rows) | margin_y (along rows) |
|---|---|---|
| DIP-16 W7.62 | 0.25–0.26 | 0.72 |
| DIP-14 W7.62 | 0.25–0.26 | 0.73 |
| DIP-18 W7.62 | 0.25–0.26 | 0.72 |
| DIP-16 W10.16 | 0.25 | 0.72 |
| DIP-24 W15.24 | 0.25 | 0.72 |

Consistent within ~0.01mm across every pin count and width class
checked: real DIP courtyard margin is **0.25mm in X, 0.72mm in Y** —
both independent of pin count and width class, the same "one constant
covers every variant" pattern already seen for DIP's `body_margin`.

SOIC's real courtyard is not a simple rectangle at all — it's built from
many short `fp_line` segments forming a stepped shape that hugs the pad
envelope more closely at the ends than in the middle. Matching that is a
meaningfully different (and bigger) undertaking, so it's explicitly out
of scope here.

## Goals

- Replace the flat 0.5mm courtyard margin with 0.25mm (X) / 0.72mm (Y)
  for DIP only, matching real KiCad almost exactly.

## Non-goals

- SOIC's stepped courtyard shape — future work, not a rectangle-margin
  tweak.
- Any change to QFP or chip-passive (R/C) courtyards — they keep the
  current flat 0.5mm margin.
- Any change to F.SilkS geometry or the pin-1 marker — this spec only
  touches the courtyard `Rect`.

## Design

### Data model (`data/kicad-fpdb.yaml`)

Add `courtyard_margin_x`/`courtyard_margin_y` to DIP's root `params`
(inherited by every child via the existing chain-merge, same pattern as
`pin1_marker`):

```yaml
DIP:
  params:
    ...
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.72
```

### Pipeline (`kicad_fpdb/pipeline.py`)

Both are outline inputs — pop them from resolved params in
`generate_footprint`, defaulting to `None`:

```python
courtyard_margin_x = params.pop("courtyard_margin_x", None)
courtyard_margin_y = params.pop("courtyard_margin_y", None)
...
_add_outline(geometry, ..., courtyard_margin_x=courtyard_margin_x, courtyard_margin_y=courtyard_margin_y)
```

`_add_outline` gains two new parameters, each defaulting to `None` and
falling back to the existing `COURTYARD_MARGIN_MM` when absent — this is
the only change to the courtyard block, which stays otherwise identical
and continues to run first, unconditionally, exactly as today:

```python
def _add_outline(geometry, ..., courtyard_margin_x: float | None = None,
                  courtyard_margin_y: float | None = None) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
    cy0x, cy0y = min_x - mx, min_y - my
    cy1x, cy1y = max_x + mx, max_y + my
    geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))
    ...
```

Nothing else in `_add_outline` changes — the F.SilkS branches and the
pin-1 marker are untouched.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (pad geometry untouched).
- Unit test on `_add_outline` confirming the courtyard rectangle uses
  the asymmetric margins when given, and the existing flat margin when
  not (regression guard for every non-DIP family).
- Tests via `generate_footprint` confirming DIP-16's courtyard exactly
  matches real KiCad's `(-1.06, -1.52)` to `(8.67, 19.3)` (using 0.25
  rather than the real footprint's own 0.26 for this specific variant —
  within the same ~0.01mm tolerance already accepted for SOIC's margin).
- Regenerate `renders/review.html` and visually confirm DIP courtyards
  are visibly tighter and closer to the reference panel.
