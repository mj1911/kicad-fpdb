# Match real KiCad's Reference/Value text position exactly

Date: 2026-09-17

## Problem

Generated footprints place their Reference ("REF**") and Value text
using a flat `TEXT_MARGIN_MM = 0.7` gap from the outline's own bounding
box, then snap the result to a `TEXT_GRID_MM = 1.27` (0.05in) grid —
documented at the time as "real KiCad's own gap here varies a little
per family (~0.7-0.8mm) and isn't itself grid-aligned; this project
uses one flat gap then grid-snaps for a clean look, rather than
chasing per-family exactness." Requested: match real KiCad exactly
instead.

## Investigation

Extracted the real `Reference` property's `at` position and the real
`F.CrtYd` bounding box from one sample per family across all of
`kicad_fpdb.reference_cases.CASES`, and computed `gap = courtyard_min_y
- reference_y` (and the mirrored gap on the Value/max side). Two
findings:

**Real KiCad never grid-snaps this at all.** Every sampled real
position is a plain, ungridded value (e.g. `-2.33`, `-3.4`, `-5.88`) —
none land on a `1.27mm` multiple except by coincidence (DIP's own
pitch/row-spacing happen to already be multiples of `2.54mm`, so its
particular samples land on-grid without any snapping step). The
grid-snap was a deliberate stylistic choice this project made, not a
real KiCad behavior, and this change removes it entirely — for both
the Y placement and the X centering (`_snap_to_grid` on `center_x`).

**The gap is a small set of per-family-group flat constants, not one
universal value and not something that needs per-variant hand-tuning:**

| Group | Gap | Sample evidence |
|---|---|---|
| Default (SOIC, LQFP, QFN, R, C, SOT-23, TSOT-23) | `0.7mm` | Exact match, zero variance, across SOIC-8, SOIC-14W, LQFP-32, LQFP-100, QFN-12, R-0603, R-1206, C-0603, SOT-23-6 |
| DIP, CERDIP, SMDIP (plain, incl. `longpads`) | `0.805mm` | `CERDIP-8`/`CERDIP-14` give the exact value directly (`0.805`); every other DIP/CERDIP/SMDIP sample (~140 cases checked) rounds to `0.80` or `0.81` at the file's 2-decimal precision, consistent with one true value straddling that rounding boundary |
| DIP's `socket` modifier (with or without `longpads`) | `0.94mm` | Exact, zero variance, across every socket sample (DIP and CERDIP alike) — a real, separate override, not the plain DIP value: the extra silk rectangle `_Socket` draws doesn't just widen the courtyard by the same amount the text shifts by, so this needs its own constant rather than falling out of the existing gap formula automatically |
| R-AXIAL | `1.0mm` | Exact, zero variance, across all 4 body sizes (0204/0207/0309/0414) |

No other modifier (`longpads` alone, the various SOIC-8-1EP/QFN
pitch/width modifiers, LQFP/QFN's own variants) shifts the gap from
its family's base value — only DIP's `socket` modifier does.

## Design

**Remove grid-snapping entirely.** `_snap_to_grid` and `_snap_outward`
(`kicad_fpdb/pipeline.py`) and `TEXT_GRID_MM` are deleted;
`_add_reference_and_value_text` computes `center_x` as the plain
`(min_x + max_x) / 2` and the Reference/Value `y` as plain
`min_y - text_margin_mm` / `max_y + text_margin_mm` — no rounding step
at all.

**New param `text_margin_mm`**, threaded through
`_add_reference_and_value_text` and `generate_footprint` the same way
`fab_reference_font_size`/`_thickness`/`_rotation` already are:
default `TEXT_MARGIN_MM = 0.7` when not overridden (covers every
family except the two below with zero yaml changes).

**Data changes** (`data/kicad-fpdb.yaml`): `DIP`, `CERDIP`, and
`SMDIP` are three separate top-level roots (none chains from another),
so each needs its own declaration:
- `DIP`, `CERDIP`, `SMDIP` roots: `text_margin_mm: 0.805` on each.
- `DIP`'s `socket` modifier, and `CERDIP`'s own separate `socket`
  modifier (`CERDIP` declares its own, not inherited from `DIP` — plus
  per-child `socket` overrides on `CERDIP-8`/`CERDIP-14` for their own
  distinct `socket_margin_y`): add `text_margin_mm: 0.94` to each
  `socket` modifier's own override dict (same mechanism
  `socket_margin_x`/`_y` already use there) — applies whether or not
  `longpads` is also active, so no `_with` combo entry is needed. No
  `socket` modifier exists on `SMDIP`.
- `R-AXIAL` (the `R-AXIAL` intermediate node, shared by all 4 body
  sizes): `text_margin_mm: 1.0`.

## Non-goals

- No change to the separate `fp_text user "${REFERENCE}"` F.Fab
  overlay — it's already centered on the true midpoint with no
  grid-snap, unaffected by any of this.
- No change to any geometry other than Reference/Value text position.

## Verification

- Extend `kicad_fpdb.footprint_diff.diff_footprint` to parse and
  compare the real vs. generated `Reference`/`Value` property `at`
  positions (both X and Y), with a small numeric tolerance (e.g.
  `0.01mm`, the same rounding-noise category already accepted for
  LQFP's corner marks and pin-1 triangle) to absorb the DIP-family
  constant's own 2-decimal file-rounding residual.
- Update `tests/test_pipeline_text.py`'s existing grid-snap-specific
  tests (`test_reference_and_value_are_snapped_to_005in_grid`, the
  `_snap_outward`-specific test using R-1206) to reflect the new plain
  (ungridded) placement — this is a deliberate, intended behavior
  change, not a regression.
- Run `python -m kicad_fpdb.verify_library` for a full report across
  all 250 known cases.
- Visual review via `python -m kicad_fpdb.render_png` on a cross
  section (DIP, DIP socket, SOIC, LQFP, R-AXIAL) to confirm text no
  longer visibly snaps to a grid the real footprint doesn't use.
