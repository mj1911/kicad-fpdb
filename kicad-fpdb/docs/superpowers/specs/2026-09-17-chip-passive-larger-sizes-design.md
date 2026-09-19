# Add R-1210/1812/2010/2512 and C-1210/1812 chip passive sizes

Date: 2026-09-17

## Problem

`data/kicad-fpdb.yaml`'s `R`/`C` families cover 0201-1206 (R) and
0402-0805 (C). The real library also has 1210/1812/2010/2512 resistors
and 1210/1812 capacitors (no real `C_2010_*`/`C_2512_*` files exist) —
a natural size-coverage gap, per the TODO's "Expand `data/kicad-fpdb.
yaml` coverage... more chip passive sizes" item.

## Investigation

All 6 real reference files (`R_1210_3225Metric`, `C_1210_3225Metric`,
`R_1812_4532Metric`, `C_1812_4532Metric`, `R_2010_5025Metric`,
`R_2512_6332Metric` — the plain variant of each; `_HandSolder` variants
also exist but are out of scope, matching the existing convention of
only covering the plain size for 0201-1206/0402-0805) fit the existing
`two_pad_chip` generator exactly, with the exact same param set already
used for every existing chip-passive variant — no new code, no new
primitive:

| Descriptor | `pad_pitch` | `pad_size` | `silk_y` | `silk_half_length` | `courtyard_margin_x/y` | `fab_body_size` | `fab_reference_font_size` | `fab_reference_thickness` |
|---|---|---|---|---|---|---|---|---|
| R-1210 | 2.925 | [1.125, 2.65] | 1.355 | 0.723737 | 0.255 | [3.2, 2.49] | 0.8 | 0.12 |
| C-1210 | 2.95 | [1.15, 2.7] | 1.36 | 0.711252 | 0.25 | [3.2, 2.5] | 0.8 | 0.12 |
| R-1812 | 4.275 | [1.125, 3.4] | 1.71 | 1.386252 | 0.25 | [4.5, 3.2] | 1.0 | 0.15 |
| C-1812 | 4.1 | [1.4, 3.4] | 1.71 | 1.161252 | 0.25 | [4.5, 3.2] | 1.0 | 0.15 |
| R-2010 | 4.625 | [1.225, 2.65] | 1.36 | 1.527064 | 0.255 | [5.0, 2.5] | 1.0 | 0.15 |
| R-2512 | 5.925 | [1.225, 3.35] | 1.71 | 2.177064 | 0.255 | [6.3, 3.2] | 1.0 | 0.15 |

(`courtyard_margin_x`/`_y` derived directly from each real file's own
courtyard/pad edges — isotropic per variant, same convention as every
existing chip-passive size; `0.255` vs `0.25` is simply each variant's
own real value, not a typo.) `pin1_marker` stays inherited as `false`
from each family's root, and `no_silk` is not needed (all 6 sizes are
well above the `R-0201`-only "too small for silk" threshold).

Real KiCad's own naming (`R_1210_3225Metric` etc.) needs 4 new
`kicad_fpdb.naming.IMPERIAL_TO_METRIC` entries: `"1210": "3225"`,
`"1812": "4532"`, `"2010": "5025"`, `"2512": "6332"`.

## Design

Add 6 new child descriptors to `data/kicad-fpdb.yaml`'s existing `R`
and `C` family nodes, each a flat `params:` dict using the table
above — same shape as every existing `R-*`/`C-*` child. Add the 4 new
`IMPERIAL_TO_METRIC` entries.

## Non-goals

- `_HandSolder` variants (wider pads for hand soldering) — a distinct
  modifier this project doesn't model yet for any chip-passive size.
- `C-2010`/`C-2512` — no real KiCad file exists for either.

## Verification

- Add all 6 new descriptors to `kicad_fpdb.reference_cases.CASES`.
- `pytest tests/test_pipeline_regression.py` (via the shared
  `kicad_fpdb.footprint_diff.diff_footprint`) verifies each against
  its real file exactly.
- `python -m kicad_fpdb.verify_library` for a full report.
- Visual review via `python -m kicad_fpdb.render_png --family R C`.
