# QFN family design

## Goal

Add a `QFN` package family (20 generic, single-exposed-pad variants
spanning 8-80 pins) to `data/kicad-fpdb.yaml`, matching real KiCad's
`Package_DFN_QFN.pretty` library exactly per variant, the same way
every prior family (DIP, SOIC, LQFP, SOT-23, ...) was added.

## Scope

- Real KiCad's generic (non-vendor-prefixed) `QFN-N-1EP_WxHmm_Pp.pmm_
  EPExEmm.kicad_mod` files only — not vendor variants (`HVQFN`,
  `DHVQFN`, `Microchip_DRQFN`, ...), matching the existing convention
  that `LQFP` only covers KiCad's own generic low-profile QFP, not
  vendor-specific ones.
- Single exposed pad (`-1EP`) only — no 2EP/3EP/5EP variants (those
  don't fit the current exposed-pad code, which assumes exactly one
  center pad).
- No `_ThermalVias` siblings (via array inside the thermal pad) —
  deferred, same as the existing TODO item for SOIC-8-1EP's own
  `_ThermalVias` siblings ("a genuinely new primitive").
- 20 variants, one per pin-count bucket from 8 to 80 pins, picked from
  the real library for a representative body-size/pitch spread:

  | Pins | Real reference file |
  |------|----------------------|
  | 8  | `QFN-8-1EP_6x5mm_P1.27mm_EP3.4x4.2mm` |
  | 12 | `QFN-12-1EP_3x3mm_P0.5mm_EP1.45x1.45mm` |
  | 16 | `QFN-16-1EP_3x3mm_P0.5mm_EP1.45x1.45mm` |
  | 20 | `QFN-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm` |
  | 24 | `QFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm` |
  | 28 | `QFN-28-1EP_5x5mm_P0.5mm_EP3.1x3.1mm` |
  | 32 | `QFN-32-1EP_5x5mm_P0.5mm_EP3.3x3.3mm` |
  | 36 | `QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm` |
  | 40 | `QFN-40-1EP_6x6mm_P0.5mm_EP4.6x4.6mm` |
  | 42 | `QFN-42-1EP_5x6mm_P0.4mm_EP3.7x4.7mm` |
  | 44 | `QFN-44-1EP_7x7mm_P0.5mm_EP5.2x5.2mm` |
  | 48 | `QFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm` |
  | 52 | `QFN-52-1EP_7x8mm_P0.5mm_EP5.41x6.45mm` |
  | 56 | `QFN-56-1EP_8x8mm_P0.5mm_EP5.6x5.6mm` |
  | 60 | `QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm` |
  | 64 | `QFN-64-1EP_9x9mm_P0.5mm_EP6x6mm` |
  | 68 | `QFN-68-1EP_8x8mm_P0.4mm_EP5.2x5.2mm` |
  | 72 | `QFN-72-1EP_10x10mm_P0.5mm_EP6x6mm` |
  | 76 | `QFN-76-1EP_9x9mm_P0.4mm_EP5.81x6.31mm` |
  | 80 | `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm` |

  If hand-verification turns up an anomaly on any one of these (same
  category as DIP-32's rect-vs-roundrect anomaly or SOIC-32's pad
  width mismatch), it's swapped for another file in the same
  pin-count bucket rather than blocking the whole batch.

## Design: 100% reuse, no new primitives

A QFN is geometrically an LQFP (`quad_perimeter`'s 4-sided perimeter
pad layout, already correctly orienting long/short pad axis per side)
with three differences, and all three are already-existing,
already-generic mechanisms in the pipeline:

1. **Roundrect leads instead of rect** — `quad_perimeter` already
   emits `roundrect` pads (LQFP just happens to use large enough pads
   that the clamp rarely shows). Pure data: QFN's `pad_size` values
   are smaller/differently-proportioned than LQFP's, nothing else
   changes.
2. **One center exposed pad + 4-way paste split** — the `ep_size`
   mechanism (`_add_exposed_pad` in `pipeline.py`) was built for
   SOIC-8-1EP but runs generator-agnostically, after whichever
   generator produced the geometry. Declaring `ep_size` (and
   optionally `ep_mask_size`) on a QFN variant is enough; no code
   changes needed. The paste-split formula (`_PASTE_SPLIT_SLOPE`/
   `_PASTE_SPLIT_INTERCEPT`, fit only against SOIC-8-1EP samples
   so far) gets validated against real QFN paste geometry as part of
   hand-verifying each of the 20 cases — if a QFN sample's residual
   exceeds the existing ~0.006mm tolerance, that's a real finding to
   report before proceeding, not something to silently override.
3. **Stepped courtyard, chamfered F.Fab body, circle pin-1 marker,
   corner-mark silk** — all identical to LQFP's own existing
   mechanisms (`courtyard_body_size` + `courtyard_margin_x/y`,
   `fab_outline: true` + `fab_chamfer`, default `pin1_marker: true`,
   `_add_corner_marks`/`CORNER_MARK_MM`). QFN deliberately keeps the
   same circle pin-1 marker (not real KiCad's filled triangle) that
   every other IC family already uses — a consistent, established
   departure from real KiCad's own marker convention, not an
   oversight; matching it exactly is explicitly out of scope (same
   category as the still-open SOT-23W TODO, which needs a new
   triangle primitive this design does not add).

Net: no new generator, no new geometry primitive, no changes to
`pipeline.py`, `geometry.py`, or `writer.py`. The only code change is
additive: a `QFN` branch in `kicad_fpdb/naming.py`.

## Naming

`descriptive_suffix` gets a new `family == "QFN"` branch: same
WxH-body + `P{pitch}` suffix LQFP already produces from the generated
F.Fab true-body outline, with an appended `_EP{w}x{h}mm` segment read
from the variant's own `ep_size` param — matching real KiCad's QFN
naming exactly (e.g. `QFN-16-1EP` → `QFN-16-1EP_3x3mm_P0.5mm_
EP1.45x1.45mm`). The literal `-1EP` token is part of each variant's
own descriptor name (`QFN-16-1EP`), the same convention already used
for `SOIC-8-1EP`, not something `descriptive_suffix` generates.

## Testing

- 20 new entries in `kicad_fpdb/reference_cases.py`, each covered by
  the existing `tests/test_pipeline_regression.py` byte/geometry
  comparison against the real `.kicad_mod` file.
- Any per-variant override needed (unusual `pad_lead_extension`,
  `ep_mask_size`, etc.) follows the existing "explicit-value escape
  hatch" convention already used throughout `data/kicad-fpdb.yaml`.
- Visual sanity check via `python -m kicad_fpdb.visual_compare`,
  pinning `PREVIEW_ONLY_DESCRIPTORS` to the 20 new QFN cases for this
  round.

## Non-goals (deferred, added to CLAUDE.md TODO)

- Vendor-specific QFN variants (`HVQFN`, `VQFN`, `DHVQFN`, ...).
- Multi-EP QFN variants (2EP/3EP/4EP/5EP).
- `_ThermalVias` siblings (needs a real via-array primitive — same
  deferred item already open for SOIC-8-1EP).
- A real filled-triangle pin-1 marker (same deferred item already
  open for SOT-23W).
