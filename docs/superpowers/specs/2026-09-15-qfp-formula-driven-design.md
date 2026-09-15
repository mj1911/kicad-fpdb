# QFP formula-driven design

## Problem

Every QFP variant in `data/kicad-fpdb.yaml` is a fully enumerated leaf: it
declares `pin_count`, `pitch`, `pad_offset`, and `pad_size` explicitly, with
no shared formula relating them. Unlike DIP/SOIC (where a new pin count
reuses the family's `pitch`/`row_spacing`/`body_width` unchanged), adding a
new QFP variant today requires hand-deriving `pad_offset` from the real
reference footprint before it can be declared — there's no way to go
straight from a datasheet's body size to a working descriptor.

## Investigation

Read 8 real `LQFP-*` reference footprints from
`/usr/share/kicad/footprints/Package_QFP.pretty/`, spanning body sizes from
7mm to 28mm:

| File | Body (mm) | Pins | Pitch | Pad 1 X | `pad_offset` | extension (`pad_offset - body/2`) |
|---|---|---|---|---|---|---|
| LQFP-32_7x7mm_P0.8mm | 7 | 32 | 0.8 | -4.175 | 4.175 | 0.675 |
| LQFP-48_7x7mm_P0.5mm | 7 | 48 | 0.5 | -4.1625 | 4.1625 | 0.6625 |
| LQFP-64_10x10mm_P0.5mm | 10 | 64 | 0.5 | -5.675 | 5.675 | 0.675 |
| LQFP-80_12x12mm_P0.5mm | 12 | 80 | 0.5 | -6.6875 | 6.6875 | 0.6875 |
| LQFP-100_14x14mm_P0.5mm | 14 | 100 | 0.5 | -7.675 | 7.675 | 0.675 |
| LQFP-144_20x20mm_P0.5mm | 20 | 144 | 0.5 | -10.6625 | 10.6625 | 0.6625 |
| LQFP-176_24x24mm_P0.5mm | 24 | 176 | 0.5 | -12.675 | 12.675 | 0.675 |
| LQFP-208_28x28mm_P0.5mm | 28 | 208 | 0.5 | -14.675 | 14.675 | 0.675 |

Two relationships hold:

1. **Silk corner-mark span** (`body_size`, the oversized bracket-corner
   rectangle already drawn on `F.SilkS`) = `courtyard_body_size + 0.22mm`,
   exact across all 8 samples (verified against each file's own `F.SilkS`
   corner-bracket `fp_line` coordinates, not just the two already in the
   database).
2. **Pad offset** = `courtyard_body_size / 2 + lead_extension`, where
   `lead_extension` takes one of three real values across the 8 samples:
   `0.675` (5 of 8: 32, 64, 100, 176, 208-pin), `0.6625` (2 of 8: 48,
   144-pin), `0.6875` (1 of 8: 80-pin). Not a single clean formula — the
   same "default constant with per-variant override" shape already used
   for SOIC's courtyard margin and the chip-passive `silk_y`/
   `silk_half_length` values.

`pin_count`, `pitch`, and `pad_size` remain hand-declared per variant, same
as today — no formula relates them to body size either (real pad lengths
in the sample: 1.5, 1.475, 1.55, 1.475, 1.6, 1.475, 1.5, 1.5mm, with no
correlation to body size or pin count).

## Design

### `quad_perimeter` generator (`kicad_fpdb/generators/quad_perimeter.py`)

Add two new parameters and make two existing ones derivable:

- `courtyard_body_size: float` — new required param, the true JEDEC body
  size (already declared today for the courtyard; now also feeds pad
  geometry).
- `pad_lead_extension: float = 0.675` — new optional param, the default
  extension beyond half the body to reach pad center. Per-variant override
  for the two real values that differ (`0.6625`, `0.6875`).
- `pad_offset: float | None = None` — becomes optional. If given
  explicitly, it wins outright (escape hatch for any future variant that
  doesn't fit the formula, matching the project's other per-family escape
  hatches like `silk_segments`). Otherwise computed as
  `courtyard_body_size / 2 + pad_lead_extension`.
- `body_size: float | None = None` — becomes optional. If given explicitly
  it wins (same escape-hatch shape). Otherwise computed as
  `courtyard_body_size + 0.22`.

The computed `body_size` is returned/exposed the same way the caller
(`_add_outline` in `pipeline.py`) already consumes it today — no change
needed in `pipeline.py` itself, since `body_size` is read from the
resolved params dict after `generate_footprint()` merges family-tree
params; the generator computing a default for a param that's otherwise
unset is consistent with how `two_pad_chip` already defaults
`roundrect_rratio` via `clamped_roundrect_rratio`.

### `data/kicad-fpdb.yaml`

- `QFP` root: add `pad_lead_extension: 0.675`; remove the shared
  `body_size: 7.22` (now derived per variant from each variant's own
  `courtyard_body_size`, correctly scaling for body sizes other than
  7x7mm — today's flat `7.22` only happened to work because both existing
  variants share a 7x7mm body).
- `QFP-32`: remove explicit `pad_offset` (now derived: `7.0/2 + 0.675 =
  4.175`, matching the real file exactly).
- `QFP-48`: remove explicit `pad_offset`; add `pad_lead_extension: 0.6625`
  override (derives `7.0/2 + 0.6625 = 4.1625`, matching exactly).
- Add 6 new real variants as children of `QFP`, each declaring only
  `pin_count`, `pitch`, `pad_size`, and `courtyard_body_size` (plus a
  `pad_lead_extension` override where the real value isn't the `0.675`
  default):
  - `QFP-64`: 10x10mm, P0.5, 64 pins, pad_size `[1.55, 0.3]`, default extension.
  - `QFP-80`: 12x12mm, P0.5, 80 pins, pad_size `[1.475, 0.25]`, `pad_lead_extension: 0.6875`.
  - `QFP-100`: 14x14mm, P0.5, 100 pins, pad_size `[1.6, 0.3]`, default extension.
  - `QFP-144`: 20x20mm, P0.5, 144 pins, pad_size `[1.475, 0.3]`, `pad_lead_extension: 0.6625`.
  - `QFP-176`: 24x24mm, P0.5, 176 pins, pad_size `[1.5, 0.3]`, default extension.
  - `QFP-208`: 28x28mm, P0.5, 208 pins, pad_size `[1.5, 0.3]`, default extension.

### Out of scope

The silk corner-mark bracket *leg length* (currently a fixed
`CORNER_MARK_MM = 0.3` in `pipeline.py`) stays a fixed approximation — real
leg lengths vary per variant (0.30mm to 0.975mm across the 8 samples
checked here) with no formula found, and CLAUDE.md already documents this
as a known, accepted approximation. Not part of this change.

## Testing

- Unit tests on `quad_perimeter` directly: default-extension path,
  override-extension path, explicit-`pad_offset` escape hatch overriding
  the formula, derived `body_size` default, explicit-`body_size` escape
  hatch.
- Regression cases for all 6 new variants added to
  `kicad_fpdb/reference_cases.py` / `tests/test_pipeline_regression.py`,
  verifying 0.0mm pad-position delta against the real reference files —
  same pattern as every other family.
- Full suite + visual review via `kicad_fpdb/visual_compare.py` before
  committing.
