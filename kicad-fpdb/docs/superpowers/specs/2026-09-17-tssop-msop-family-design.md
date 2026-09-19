# Add TSSOP and MSOP families (base, non-EP variants)

Date: 2026-09-17

## Problem

`data/kicad-fpdb.yaml` covers DIP/CERDIP/SMDIP/SOIC among two-row
gullwing packages, but not TSSOP or MSOP — two large, well-populated
real families (`Package_SO.pretty`) using the exact same physical
topology as SOIC. Per the TODO's "expand coverage... additional
package families" item.

## Investigation

Both families fit the existing `dual_row_grid` generator and
`_add_outline` mechanisms exactly — **no pipeline.py changes needed**,
confirmed against 25 real reference files (4 MSOP + 21 TSSOP spanning
narrow/wide/xwide body classes and pin counts 8-64).

**Two silk "flavors" exist per file, chosen independently of pin
count/pitch/width class** (per-file vendor-generator noise, not a
formula — same category as SOT-23's own per-variant silk):

- **6-line flavor**: `F.SilkS` has 2 full top/bottom lines plus 4
  short 0.175mm corner ticks — not expressible via `silk_two_lines`;
  needs the existing `silk_segments` verbatim escape hatch (SOT-23's
  own convention). Its pin-1 triangle uses `pin1_triangle_axis: y`
  (SOIC/LQFP-style, body-anchored).
- **2-line flavor**: plain `silk_two_lines: true` (exactly like
  SOIC), with `body_width`/`body_margin` derived the same way. Its
  pin-1 triangle uses `pin1_triangle_axis: x` (QFN-style, pad-relative
  — no anchor needed, the existing axis="x" branch already handles it
  from pad geometry alone).

Silk flavor and triangle axis always travel together (confirmed on
every one of the 25 samples) — declaring one implies the other, so no
new coupling logic is needed, just per-variant data.

**Width-class constants** (same mechanism as SOIC's `narrow`/`wide`
via `variants:`), confirmed clean across every sample in each class:

| Class | `row_spacing` | `courtyard_body_width` | `fab_chamfer` |
|---|---|---|---|
| MSOP (no width class — always this body) | 4.2-4.3 (varies slightly, see table) | 3.0 | 0.75 |
| TSSOP narrow | 5.725 | 4.4 | 1.0 (except TSSOP-8: 0.75) |
| TSSOP wide | 7.425 | 6.1 | 1.0 |
| TSSOP xwide | 9.325 | 8.0 | 1.0 |

`pin1_triangle_size`/`pin1_triangle_anchor_mm` split along a
MSOP-and-TSSOP-8 vs. everything-else-TSSOP line, not by width class:
`small`/`0.66-0.67` for MSOP and TSSOP-8 (matching the smaller `0.75mm`
chamfer class), `large`/`0.75` for every other TSSOP pin count. Not
used at all for 2-line-flavor (axis="x") variants.

`fab_reference_rotation: 90` is needed only for MSOP-12/16 (a
genuinely non-square 3x4.039mm body) — MSOP-8/10 (square 3x3mm) and
every TSSOP variant (all wide-format bodies) stay unrotated, the
opposite of SOIC's blanket family-level rotation. `fab_reference_
font_size`/`_thickness` override (`0.75`/`0.11`) is needed only for
MSOP-8/10 — MSOP-12/16 and all TSSOP variants use the project default
(`1.0`/`0.15`).

**Pitch selection**: several (pin_count, width_class) combinations
have multiple real pitch options. Investigated the full distribution
across the real library (not just the sampled 25) and confirmed this
isn't arbitrary — it's a physical constraint (more pins must fit into
a JEDEC-standard body length as pin count grows, mechanically forcing
finer pitch once a coarser one no longer fits). Rule adopted: **the
largest (coarsest) pitch available for that specific combination**,
falling back to a finer one only when no coarser option exists for it
— matching how `default_width` already picks the most standard option
elsewhere in this project. No pitch-variant modifiers added in this
pass (a natural, smaller follow-up, same pattern as QFN's `p65`/`p4`).

## Full per-variant dataset

All pads: `roundrect`/`smd`/`centered: true`, `pad_size.x` constant
within a width class (`1.475` for every TSSOP class, varies per MSOP
variant), `pad_size.y` varies only with pitch. `courtyard_margin_x`/
`_y: 0.25` and `fab_outline: true` are constant across all 25.
`text_margin_mm` stays the unmodified `0.7` default everywhere
(confirmed on every sample).

**MSOP** (own root, no shared width class — `row_spacing`/`courtyard_
body_margin` are per-variant, not a class constant):

| Descriptor | `pitch` | `pad_size` | `row_spacing` | `courtyard_body_margin` | silk | triangle |
|---|---|---|---|---|---|---|
| MSOP-8 | 0.65 | [1.625, 0.4] | 4.225 | 0.5 | 6-line (below) | y, small, 0.66 |
| MSOP-10 | 0.5 | [1.5, 0.35] | 4.2 | 0.5 | 6-line (same shape as MSOP-8) | y, small, 0.66 |
| MSOP-12 | 0.65 | [1.45, 0.4] | 4.3 | 0.39 | 6-line (below) | y, small, 0.665 |
| MSOP-16 | 0.5 | [1.45, 0.3] | 4.3 | 0.265 | 2-line, `body_width: 3.22`, `body_margin: 0.41` | x, small |

MSOP-8/10 `silk_segments` (identical shape, both 3x3mm body):
`[[-1.61,-1.61],[1.61,-1.61]]`, `[[-1.61,-1.435],[-1.61,-1.61]]`,
`[[-1.61,1.61],[-1.61,1.435]]`, `[[1.61,-1.61],[1.61,-1.435]]`,
`[[1.61,1.435],[1.61,1.61]]`, `[[1.61,1.61],[-1.61,1.61]]`.

MSOP-12 `silk_segments` (3x4.039mm body):
`[[-1.61,-2.1295],[1.61,-2.1295]]`, `[[-1.61,-2.085],[-1.61,-2.1295]]`,
`[[-1.61,2.1295],[-1.61,2.085]]`, `[[1.61,-2.1295],[1.61,-2.085]]`,
`[[1.61,2.085],[1.61,2.1295]]`, `[[1.61,2.1295],[-1.61,2.1295]]`.

MSOP-8/10: `fab_reference_font_size: 0.75`, `_thickness: 0.11`, no
rotation override. MSOP-12/16: default font (no override),
`fab_reference_rotation: 90`. `courtyard_body_width: 3.0` for all 4
(true F.Fab body 3.0 x 3.0 for MSOP-8/10, 3.0 x 4.039 for MSOP-12/16 —
`courtyard_body_margin` above is the Y-axis value derived from each
variant's own real body length).

**TSSOP narrow** (`row_spacing: 5.725`, `courtyard_body_width: 4.4`,
`fab_chamfer: 1.0` except TSSOP-8's `0.75`):

| Descriptor | `pitch` | `pad_size` | `courtyard_body_margin` | silk | triangle |
|---|---|---|---|---|---|
| TSSOP-8 | 0.65 | [1.475, 0.4] | 0.525 | 6-line A | y, small, 0.67 |
| TSSOP-14 | 0.65 | [1.475, 0.4] | 0.55 | 6-line B | y, large, 0.75 |
| TSSOP-16 | 0.65 | [1.475, 0.4] | 0.225 | 2-line, `body_width: 4.62`, `body_margin: 0.46` | x, small |
| TSSOP-20 | 0.65 | [1.475, 0.4] | 0.325 | 2-line, `body_width: 4.62`, `body_margin: 0.46` | x, small |
| TSSOP-24 | 0.65 | [1.475, 0.4] | 0.325 | 2-line, `body_width: 4.62`, `body_margin: 0.46` | x, small |
| TSSOP-28 | 0.65 | [1.475, 0.4] | 0.625 | 6-line C | y, large, 0.75 |
| TSSOP-32 | 0.4 | [1.475, 0.25] | 0.25 | 2-line, `body_width: 4.62`, `body_margin: 0.385` | x, small |
| TSSOP-36 | 0.5 | [1.475, 0.3] | 0.6 | 6-line D | y, large, 0.75 |
| TSSOP-48 | 0.4 | [1.475, 0.25] | 0.25 | 2-line, `body_width: 4.62`, `body_margin: 0.385` | x, small |
| TSSOP-56 | 0.4 | [1.475, 0.25] | 0.25 | 2-line, `body_width: 4.62`, `body_margin: 0.385` | x, small |

Narrow 6-line segment sets (x half-length always `2.31`, only the y
values change with body length):
- **A** (TSSOP-8, body y `±1.61`, tick to `±1.435`): `[[-2.31,-1.61],[2.31,-1.61]]`, `[[-2.31,-1.435],[-2.31,-1.61]]`, `[[-2.31,1.61],[-2.31,1.435]]`, `[[2.31,-1.61],[2.31,-1.435]]`, `[[2.31,1.435],[2.31,1.61]]`, `[[2.31,1.61],[-2.31,1.61]]`
- **B** (TSSOP-14, `±2.61`, tick to `±2.41`): same shape, y values `2.61`/`2.41`
- **C** (TSSOP-28, `±4.96`, tick to `±4.685`): y values `4.96`/`4.685`
- **D** (TSSOP-36, `±4.96`, tick to `±4.66`): y values `4.96`/`4.66` (note: same outer extent as C but a different tick length — TSSOP-28 and TSSOP-36 are NOT the same shape despite both having body length 9.7mm, since pad pitch/Y-size differs)

**TSSOP wide** (`row_spacing: 7.425`, `courtyard_body_width: 6.1`,
`fab_chamfer: 1.0`):

| Descriptor | `pitch` | `pad_size` | `courtyard_body_margin` | silk | triangle |
|---|---|---|---|---|---|
| TSSOP-24 | 0.65 | [1.475, 0.4] | 0.325 | 2-line, `body_width: 6.32`, `body_margin: 0.46` | x, small |
| TSSOP-28 | 0.65 | [1.475, 0.4] | 0.625 | 6-line E | y, large, 0.75 |
| TSSOP-32 | 0.65 | [1.475, 0.4] | 0.625 | 6-line F | y, large, 0.75 |
| TSSOP-36 | 0.65 | [1.475, 0.4] | 0.725 | 6-line G | y, large, 0.75 |
| TSSOP-48 | 0.5 | [1.475, 0.3] | 0.5 | 6-line H | y, large, 0.75 |
| TSSOP-56 | 0.5 | [1.475, 0.3] | 0.25 | 2-line, `body_width: 6.32`, `body_margin: 0.41` | x, small |
| TSSOP-64 | 0.5 | [1.475, 0.3] | 0.75 | 6-line I | y, large, 0.75 |

Wide 6-line segments (x half-length always `3.16`):
- **E** (TSSOP-28, `±4.96`/`±4.685`): `[[-3.16,-4.96],[3.16,-4.96]]`, `[[-3.16,-4.685],[-3.16,-4.96]]`, `[[-3.16,4.96],[-3.16,4.685]]`, `[[3.16,-4.96],[3.16,-4.685]]`, `[[3.16,4.685],[3.16,4.96]]`, `[[3.16,4.96],[-3.16,4.96]]`
- **F** (TSSOP-32, `±5.61`/`±5.335`): y values `5.61`/`5.335`
- **G** (TSSOP-36, `±6.36`/`±5.985`): y values `6.36`/`5.985`
- **H** (TSSOP-48, `±6.36`/`±6.16`): y values `6.36`/`6.16`
- **I** (TSSOP-64, `±8.61`/`±8.16`): y values `8.61`/`8.16`

**TSSOP xwide** (`row_spacing: 9.325`, `courtyard_body_width: 8.0`,
`fab_chamfer: 1.0`; all 4 samples happen to be the 6-line flavor):

| Descriptor | `pitch` | `pad_size` | `courtyard_body_margin` | silk | triangle |
|---|---|---|---|---|---|
| TSSOP-28 | 0.65 | [1.475, 0.4] | 0.625 | 6-line J | y, large, 0.75 |
| TSSOP-32 | 0.65 | [1.475, 0.4] | 0.625 | 6-line K | y, large, 0.75 |
| TSSOP-36 | 0.65 | [1.475, 0.4] | 0.725 | 6-line L | y, large, 0.75 |
| TSSOP-48 | 0.5 | [1.475, 0.3] | 0.5 | 6-line M | y, large, 0.75 |

Xwide 6-line segments (x half-length always `4.11`), same y-value
pairs as their wide-class counterparts of the same body length/pitch
(J=E's y-values, K=F's, L=G's, M=H's, just at `±4.11` instead of
`±3.16`).

## Design

Pure data addition to `data/kicad-fpdb.yaml`:
- New `MSOP` root (`generator: dual_row_grid`), 4 flat children, no
  width-class mechanism (each variant declares its own `row_spacing`/
  `courtyard_body_margin` directly — they don't share one).
- New `TSSOP` root (`generator: dual_row_grid`), `variants: {n:
  narrow, w: wide, xw: xwide}`, `default_width: narrow`, with
  `row_spacing`/`courtyard_body_width`/`fab_chamfer` as per-class
  dicts (fab_chamfer needs a `TSSOP-8`-only override — same mechanism
  DIP-22/24's `body_width` override already uses) and `pitch`/
  `pad_size`/`courtyard_body_margin`/silk/triangle params declared per
  leaf child, following the tables above.
- New descriptive-suffix support in `kicad_fpdb.naming`: TSSOP/MSOP
  need the same `family in ("SOIC", "LQFP", "QFN")`-style dimension
  suffix SOIC already produces (body size + pitch) — extend that
  existing branch to include `"TSSOP"`/`"MSOP"`.

## Non-goals

- `-1EP` exposed-pad variants for either family — a deliberate,
  separate follow-up spec (directly reuses the SOIC-8-1EP paste-split
  mechanism, per investigation, but is its own scope).
- TSSOP's oddball 3mm-body 8-pin variant, and the single 4-pin/4mm-
  pitch TSSOP-4 oddity.
- Additional real pitch options at (pin_count, width_class) combos
  where more than one exists — a natural follow-up via a `p40`/`p50`-
  style modifier, same pattern as QFN's `p65`/`p4`.
- Vendor-prefixed HTSSOP/ETSSOP heatsink-variant families — a
  genuinely different real family name, not a modifier on plain
  TSSOP, same treatment as SOIC-8-1EP's own deferred `_ThermalVias`.

## Verification

- Add all 25 descriptors to `kicad_fpdb.reference_cases.CASES`.
- `pytest tests/test_pipeline_regression.py` (via the shared
  `kicad_fpdb.footprint_diff.diff_footprint`) verifies each against
  its real file exactly.
- `python -m kicad_fpdb.verify_library --family TSSOP MSOP` for a
  full report.
- Visual review via `python -m kicad_fpdb.render_png --family TSSOP
  MSOP`.
