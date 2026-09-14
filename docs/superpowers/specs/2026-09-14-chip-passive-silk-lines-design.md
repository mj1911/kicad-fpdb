# Chip-Passive Two-Line Silk Outline — Design Spec

Date: 2026-09-14

## Background

R and C (`two_pad_chip`) currently fall through to `_add_outline`'s
generic pad-bbox rectangle (the same fallback used before DIP/SOIC/QFP
each got a real body-derived mode). Real KiCad's own chip-resistor and
chip-capacitor footprints don't draw a rectangle at all — they draw
exactly two short horizontal lines, one above and one below the part,
since the physical component body is always smaller than its pads (the
pads extend past the body to give a solderable tab) — a box around the
pads would just outline the pads themselves, telling the user nothing a
courtyard doesn't already show.

Checked directly against this project's real reference footprints:

| Variant | line y (±) | line half-length (x) |
|---|---|---|
| `R-0402` (`R_0402_1005Metric.kicad_mod`) | 0.38 | 0.153641 |
| `R-0603` (`R_0603_1608Metric.kicad_mod`) | 0.5225 | 0.237258 |
| `R-0805` (`R_0805_2012Metric.kicad_mod`) | 0.735 | 0.227064 |
| `C-0603` (`C_0603_1608Metric.kicad_mod`) | 0.51 | 0.14058 |

These don't reduce to a clean formula from `pad_pitch`/`pad_size` alone
(they appear to come from KiCad's internal pad-rounding/clearance
geometry) — so unlike DIP's `body_width` (one constant per width class,
covering many pin counts) or QFP's `body_size` (one constant covering
two variants), each `two_pad_chip` variant needs its own two constants,
matching the pattern each variant already fully declaring its own
`pad_pitch`/`pad_size` independently in `data/kicad-fpdb.yaml`.

## Goals

- Add `silk_y` and `silk_half_length` params to `R-0402`, `R-0603`,
  `R-0805`, and `C-0603`, with the exact real values above.
- Draw exactly two horizontal `Line`s from them instead of the generic
  rectangle, centered on the pad centroid.
- Leave DIP, SOIC, and QFP unaffected — they keep their own modes.
- Leave courtyard (F.CrtYd) generic, as with every other family so far.

## Non-goals

- Deriving a shared formula across chip-passive sizes. Each variant's
  two constants are copied directly from its real reference footprint,
  the same "hand-verified, not derived" precedent already used for the
  regression suite's real-footprint comparisons.
- New R/C variants beyond the four already in `data/kicad-fpdb.yaml` —
  adding e.g. R-1206 or a polarized capacitor is future work, each
  needing its own hand-verified `silk_y`/`silk_half_length` pair when it
  happens.
- Any change to the pin-1 marker (already off for R/C from prior work).

## Design

### Data model (`data/kicad-fpdb.yaml`)

Add `silk_y` and `silk_half_length` to each of the four existing
`two_pad_chip` children's own `params` (not at the `R`/`C` root, since —
unlike `pin1_marker` — these values genuinely differ per variant and
there's no shared default to inherit):

```yaml
R-0402:
  params: {pad_pitch: 1.02, pad_size: [0.54, 0.64], silk_y: 0.38, silk_half_length: 0.153641}
R-0603:
  params: {pad_pitch: 1.65, pad_size: [0.8, 0.95], silk_y: 0.5225, silk_half_length: 0.237258}
R-0805:
  params: {pad_pitch: 1.825, pad_size: [1.025, 1.4], silk_y: 0.735, silk_half_length: 0.227064}
C-0603:
  params: {pad_pitch: 1.55, pad_size: [0.9, 0.95], silk_y: 0.51, silk_half_length: 0.14058}
```

### Pipeline (`kicad_fpdb/pipeline.py`)

Both are outline inputs — pop them from resolved params in
`generate_footprint`, same pattern as the existing `body_*` params,
defaulting to `None`:

```python
silk_y = params.pop("silk_y", None)
silk_half_length = params.pop("silk_half_length", None)
...
_add_outline(geometry, ..., silk_y=silk_y, silk_half_length=silk_half_length)
```

`_add_outline` gains a fourth mode, checked alongside the existing
`body_width`/`body_margin`, `body_size` branches:

```python
elif silk_y is not None and silk_half_length is not None:
    min_px, max_px = _pad_center_extent(geometry.pads, 0)
    min_py, max_py = _pad_center_extent(geometry.pads, 1)
    center_x = (min_px + max_px) / 2
    center_y = (min_py + max_py) / 2
    for y in (center_y - silk_y, center_y + silk_y):
        geometry.lines.append(Line(
            start=(center_x - silk_half_length, y),
            end=(center_x + silk_half_length, y),
            layer="F.SilkS",
        ))
```

No `sx0/sy0/sx1/sy1` corner rectangle is computed in this mode — the
pin-1 marker block that follows already only runs when `pin1_marker` is
true, and R/C already declare `pin1_marker: false`, so there's no corner
concept needed here at all (unlike the QFP corner-marks mode, which
still needed corners for the marker). If a future variant somehow wanted
both this two-line mode and a marker, that combination is left
unsupported for now — YAGNI, since no current or planned variant needs it.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (pad geometry untouched).
- Unit test on `_add_outline` confirming the two-line mode produces
  exactly 2 `Line`s at the expected coordinates, and no `Rect`/`Poly`
  beyond the existing courtyard `Rect`.
- Tests via `generate_footprint` confirming R-0402/R-0603/R-0805/C-0603
  emit exactly the real `(start ...)`/`(end ...)` coordinates from the
  table above, and no `fp_rect` on `F.SilkS` (only the courtyard one).
- Regenerate `renders/review.html` and visually confirm the R/C cases
  now show two short lines matching the reference panel almost exactly
  (values are copied verbatim from the real footprints, so this should
  be a near-perfect match, unlike SOIC's averaged margin).
