# QFN Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `QFN` package family (20 generic single-exposed-pad variants spanning 12-80 pins) to `data/kicad-fpdb.yaml`, matching real KiCad's `Package_DFN_QFN.pretty` library exactly per variant.

**Architecture:** QFN reuses the existing `quad_perimeter` generator and the existing exposed-pad/courtyard/fab-outline/pin1-marker pipeline entirely — no new generator, no new geometry primitive, no changes to `pipeline.py`/`geometry.py`/`writer.py`. The only code change is additive: a `QFN` branch in `kicad_fpdb/naming.py`. Everything else is data (`data/kicad-fpdb.yaml`) plus regression cases (`kicad_fpdb/reference_cases.py`).

**Tech Stack:** Python, pytest, KiCad's `.kicad_mod` S-expression format, `kicad-cli` (for the visual review tool only).

**Spec:** `docs/superpowers/specs/2026-09-16-qfn-family-design.md`

## Global Constraints

- Every generated pad position/size/type/shape/roundrect_rratio must match its real reference `.kicad_mod` file within the existing regression tolerances (`1e-4` mm for position/size, `1e-2` for roundrect_rratio) — enforced automatically by `tests/test_pipeline_regression.py` once a case is added to `CASES`.
- No new generator, geometry primitive, or change to `pipeline.py`/`geometry.py`/`writer.py` — every mechanism QFN needs (`quad_perimeter`, `ep_size`/`_add_exposed_pad`, `courtyard_body_size`+`courtyard_margin_x/y`, `fab_outline`+`fab_chamfer`, default `pin1_marker: true`, `_add_corner_marks`) already exists and is reused as-is.
- Real KiCad's generic (non-vendor-prefixed) `QFN-N-1EP_...` files only, single exposed pad, no `_ThermalVias` siblings — per the approved spec's scope.
- 20 total variants. Verification against the real files found QFN-8/-42/-52 (the spec's original picks for those 3 pin counts) don't fit `quad_perimeter` (QFN-8 is a 2-row `dual_row_grid`-style layout; QFN-42/-52 have uneven per-side pin counts from a rectangular body) and have no same-pin-count generic alternative — resolved by adding a second body/pitch variant at pin counts 16, 32, and 48 instead (via the same width-class `variants`/`default_width` mechanism DIP/SOIC already use), keeping the total at 20 distinct-geometry descriptors: 12, 16, 16 p65, 20, 24, 28, 32, 32 p65, 36, 40, 44, 48, 48 p4, 56, 60, 64, 68, 72, 76, 80.

---

## Task 1: `QFN` naming support in `kicad_fpdb/naming.py`

**Files:**
- Modify: `kicad_fpdb/naming.py:98-115` (the `family in ("SOIC", "LQFP")` branch of `descriptive_suffix`)
- Test: `tests/test_naming.py`

**Interfaces:**
- Consumes: `descriptive_suffix(family: str, variant: str, params: dict, geometry, applied_modifiers: list | None = None) -> str` (existing signature, unchanged).
- Produces: `descriptive_suffix("QFN", "16", {"pitch": 0.5, "ep_size": [1.45, 1.45]}, geometry_with_fab_outline) == "-1EP_3x3mm_P0.5mm_EP1.45x1.45mm"` — consumed by `kicad_fpdb/pipeline.py:618` (`generate_footprint`, unchanged call site) for every Task 2 regression case.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_naming.py` (after `test_soic_suffix_empty_without_fab_outline`, following the existing `_poly_geometry` helper pattern already in this file):

```python
def test_qfn_suffix_uses_fab_bbox_pitch_and_ep_size():
    geom = _poly_geometry([(-0.75, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (-1.5, -0.75)])
    suffix = descriptive_suffix("QFN", "16", {"pitch": 0.5, "ep_size": [1.45, 1.45]}, geom)
    assert suffix == "-1EP_3x3mm_P0.5mm_EP1.45x1.45mm"


def test_qfn_suffix_empty_without_ep_size():
    geom = _poly_geometry([(-0.75, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (-1.5, -0.75)])
    assert descriptive_suffix("QFN", "16", {"pitch": 0.5}, geom) == "_3x3mm_P0.5mm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_naming.py -k qfn -v`
Expected: FAIL — `descriptive_suffix` falls through every branch and returns `""` (the trailing `return modifier_suffix` with no modifiers applied), not the QFN suffix.

- [ ] **Step 3: Extend the SOIC/LQFP branch to cover QFN**

In `kicad_fpdb/naming.py`, change:

```python
    if family in ("SOIC", "LQFP"):
        pitch = params.get("pitch")
        bbox = fab_outline_bounding_box(geometry)
        if pitch is None or bbox is None:
            return ""
        min_x, min_y, max_x, max_y = bbox
        dims = f"_{_fmt(max_x - min_x)}x{_fmt(max_y - min_y)}mm_P{_fmt(pitch)}mm"
        ep_size = params.get("ep_size") if family == "SOIC" else None
```

to:

```python
    if family in ("SOIC", "LQFP", "QFN"):
        pitch = params.get("pitch")
        bbox = fab_outline_bounding_box(geometry)
        if pitch is None or bbox is None:
            return ""
        min_x, min_y, max_x, max_y = bbox
        dims = f"_{_fmt(max_x - min_x)}x{_fmt(max_y - min_y)}mm_P{_fmt(pitch)}mm"
        ep_size = params.get("ep_size") if family in ("SOIC", "QFN") else None
```

The rest of the branch (the `if ep_size is not None:` block building `"-1EP" + dims + ep_suffix + modifier_suffix`, and the plain `return dims + modifier_suffix` fallback) is unchanged and already does exactly what QFN needs — it was written generically, not SOIC-specific.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_naming.py -v`
Expected: PASS (all tests in the file, not just the new ones — confirms the SOIC/LQFP branch still behaves identically for those families).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/naming.py tests/test_naming.py
git commit -m "$(cat <<'EOF'
Extend descriptive_suffix to cover the QFN family

Generalizes the existing SOIC/LQFP branch (already generic apart
from the ep_size family check) rather than adding a new branch --
QFN needs exactly the same WxH+pitch+EP-size suffix SOIC's own
-1EP variants already produce.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add the `QFN` family and its 20 reference cases

**Files:**
- Modify: `data/kicad-fpdb.yaml` (append a new `QFN` root after the `LQFP` block, i.e. after line 377)
- Modify: `kicad_fpdb/reference_cases.py` (append 20 entries to `CASES`)
- Modify: `kicad_fpdb/visual_compare.py:190-194` (`PREVIEW_ONLY_DESCRIPTORS`)

**Interfaces:**
- Consumes: `quad_perimeter(pin_count, pitch, pad_size, pad_offset=None, courtyard_body_size=None, pad_lead_extension=0.675)` (existing, unchanged) via `pin_count`/`pitch`/`pad_size`/`courtyard_body_size`/`pad_lead_extension` YAML params; `_add_exposed_pad`/`ep_size` (existing, unchanged) via the `ep_size` YAML param; the width-class mechanism (`variants`/`default_width`, existing, unchanged, see `data/kicad-fpdb.yaml:8-9` for the DIP precedent) for the `p65`/`p4` sub-variants.
- Produces: nothing new consumed by later tasks — this is the terminal data addition.

All 20 variants' parameters below were derived by parsing the real reference `.kicad_mod` files directly (pin count from counting numbered pads, pitch from adjacent-pad spacing, `pad_size` from pad 1's own `(size ...)`, `pad_offset` from pad 1's `(at ...)`, `courtyard_body_size` from the F.Fab true-body outline's own bounding box, `ep_size` from the real file's own name, `fab_chamfer` from the F.Fab poly's chamfer-cut point). `pad_lead_extension = pad_offset - courtyard_body_size / 2` per variant; QFN's leads sit *inboard* of the true body edge (unlike LQFP's outward gull-wing leads), so every value here is negative.

- [ ] **Step 1: Add the `QFN` family root and its 17 plain variants to `data/kicad-fpdb.yaml`**

Insert after line 377 (the blank line following `LQFP`'s `LQFP-208` entry, before the `SOT-23's asymmetric pin layouts` comment):

```yaml
# QFN reuses quad_perimeter (roundrect leads, correct per-side
# orientation) and the existing ep_size/_add_exposed_pad,
# courtyard_body_size+courtyard_margin_x/y, fab_outline+fab_chamfer,
# and default pin1_marker mechanisms entirely -- no new generator or
# primitive, see docs/superpowers/specs/2026-09-16-qfn-family-design.md.
# QFN leads sit inboard of the true body edge (unlike LQFP's outward
# gull-wing leads), so pad_lead_extension is negative here.
QFN:
  generator: quad_perimeter
  params:
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    fab_outline: true
    fab_chamfer: 1.0
    pad_lead_extension: -0.0625
    fab_reference_font_size: 0.75
    fab_reference_thickness: 0.11
  children:
    QFN-12:
      params: {pin_count: 12, pitch: 0.5, pad_size: [0.825, 0.25], courtyard_body_size: 3.0, ep_size: [1.45, 1.45], fab_chamfer: 0.75}
    QFN-20:
      params: {pin_count: 20, pitch: 0.5, pad_size: [0.825, 0.25], courtyard_body_size: 4.0, ep_size: [2.5, 2.5]}
    QFN-24:
      params: {pin_count: 24, pitch: 0.5, pad_size: [0.8, 0.25], courtyard_body_size: 4.0, ep_size: [2.5, 2.5], pad_lead_extension: -0.05}
    QFN-28:
      params: {pin_count: 28, pitch: 0.5, pad_size: [0.95, 0.25], courtyard_body_size: 5.0, ep_size: [3.1, 3.1], pad_lead_extension: -0.125}
    QFN-36:
      params: {pin_count: 36, pitch: 0.5, pad_size: [0.825, 0.25], courtyard_body_size: 6.0, ep_size: [3.7, 3.7]}
    QFN-40:
      params: {pin_count: 40, pitch: 0.5, pad_size: [0.825, 0.25], courtyard_body_size: 6.0, ep_size: [4.6, 4.6]}
    QFN-44:
      params: {pin_count: 44, pitch: 0.5, pad_size: [0.875, 0.25], courtyard_body_size: 7.0, ep_size: [5.15, 5.15]}
    QFN-56:
      params: {pin_count: 56, pitch: 0.5, pad_size: [0.875, 0.25], courtyard_body_size: 8.0, ep_size: [5.6, 5.6]}
    QFN-60:
      params: {pin_count: 60, pitch: 0.4, pad_size: [0.8, 0.2], courtyard_body_size: 7.0, ep_size: [3.4, 3.4], pad_lead_extension: -0.05}
    QFN-64:
      params: {pin_count: 64, pitch: 0.5, pad_size: [0.875, 0.25], courtyard_body_size: 9.0, ep_size: [6.0, 6.0]}
    QFN-68:
      params: {pin_count: 68, pitch: 0.4, pad_size: [0.825, 0.2], courtyard_body_size: 8.0, ep_size: [5.2, 5.2]}
    QFN-72:
      params: {pin_count: 72, pitch: 0.5, pad_size: [0.875, 0.25], courtyard_body_size: 10.0, ep_size: [6.0, 6.0]}
    QFN-76:
      params: {pin_count: 76, pitch: 0.4, pad_size: [0.875, 0.2], courtyard_body_size: 9.0, ep_size: [5.81, 6.31]}
    QFN-80:
      params: {pin_count: 80, pitch: 0.4, pad_size: [0.8, 0.2], courtyard_body_size: 10.0, ep_size: [3.4, 3.4], pad_lead_extension: -0.05}
    # QFN-16, QFN-32, and QFN-48 each get a second real body/pitch class
    # (real KiCad's generic library has several per pin count) via the
    # same variants/default_width width-class mechanism DIP/SOIC already
    # use (see data/kicad-fpdb.yaml's DIP root) -- this also fills in
    # for the 3 pin counts (8, 42, 52) whose real files don't fit
    # quad_perimeter at all (QFN-8 is a 2-row layout; QFN-42/-52 have
    # uneven per-side pin counts from a rectangular body), which have no
    # same-pin-count generic alternative.
    QFN-16:
      default_width: default
      variants: {p65: p65}
      params:
        pin_count: 16
        pitch: {default: 0.5, p65: 0.65}
        pad_size: {default: [0.875, 0.25], p65: [0.825, 0.3]}
        courtyard_body_size: {default: 3.0, p65: 4.0}
        ep_size: {default: [1.45, 1.45], p65: [2.5, 2.5]}
        fab_chamfer: {default: 0.75, p65: 1.0}
    QFN-32:
      default_width: default
      variants: {p65: p65}
      params:
        pin_count: 32
        pitch: {default: 0.5, p65: 0.65}
        pad_size: {default: [0.875, 0.25], p65: [1.025, 0.35]}
        courtyard_body_size: {default: 5.0, p65: 7.0}
        ep_size: {default: [3.3, 3.3], p65: [4.65, 4.65]}
        pad_lead_extension: {default: -0.0625, p65: -0.1625}
    QFN-48:
      default_width: default
      variants: {p4: p4}
      params:
        pin_count: 48
        pitch: {default: 0.5, p4: 0.4}
        pad_size: {default: [0.875, 0.25], p4: [0.85, 0.2]}
        courtyard_body_size: {default: 7.0, p4: 6.0}
        ep_size: {default: [5.15, 5.15], p4: [4.2, 4.2]}
        pad_lead_extension: {default: -0.0625, p4: -0.05}
```

- [ ] **Step 2: Add the 20 cases to `kicad_fpdb/reference_cases.py`**

Append to the `CASES` list (after the existing LQFP entries, before the SOT-23 entries — follow the file's existing family-grouped ordering):

```python
    ("QFN-12", "Package_DFN_QFN.pretty/QFN-12-1EP_3x3mm_P0.5mm_EP1.45x1.45mm.kicad_mod"),
    ("QFN-16", "Package_DFN_QFN.pretty/QFN-16-1EP_3x3mm_P0.5mm_EP1.45x1.45mm.kicad_mod"),
    ("QFN-16 p65", "Package_DFN_QFN.pretty/QFN-16-1EP_4x4mm_P0.65mm_EP2.5x2.5mm.kicad_mod"),
    ("QFN-20", "Package_DFN_QFN.pretty/QFN-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm.kicad_mod"),
    ("QFN-24", "Package_DFN_QFN.pretty/QFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm.kicad_mod"),
    ("QFN-28", "Package_DFN_QFN.pretty/QFN-28-1EP_5x5mm_P0.5mm_EP3.1x3.1mm.kicad_mod"),
    ("QFN-32", "Package_DFN_QFN.pretty/QFN-32-1EP_5x5mm_P0.5mm_EP3.3x3.3mm.kicad_mod"),
    ("QFN-32 p65", "Package_DFN_QFN.pretty/QFN-32-1EP_7x7mm_P0.65mm_EP4.65x4.65mm.kicad_mod"),
    ("QFN-36", "Package_DFN_QFN.pretty/QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm.kicad_mod"),
    ("QFN-40", "Package_DFN_QFN.pretty/QFN-40-1EP_6x6mm_P0.5mm_EP4.6x4.6mm.kicad_mod"),
    ("QFN-44", "Package_DFN_QFN.pretty/QFN-44-1EP_7x7mm_P0.5mm_EP5.15x5.15mm.kicad_mod"),
    ("QFN-48", "Package_DFN_QFN.pretty/QFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm.kicad_mod"),
    ("QFN-48 p4", "Package_DFN_QFN.pretty/QFN-48-1EP_6x6mm_P0.4mm_EP4.2x4.2mm.kicad_mod"),
    ("QFN-56", "Package_DFN_QFN.pretty/QFN-56-1EP_8x8mm_P0.5mm_EP5.6x5.6mm.kicad_mod"),
    ("QFN-60", "Package_DFN_QFN.pretty/QFN-60-1EP_7x7mm_P0.4mm_EP3.4x3.4mm.kicad_mod"),
    ("QFN-64", "Package_DFN_QFN.pretty/QFN-64-1EP_9x9mm_P0.5mm_EP6x6mm.kicad_mod"),
    ("QFN-68", "Package_DFN_QFN.pretty/QFN-68-1EP_8x8mm_P0.4mm_EP5.2x5.2mm.kicad_mod"),
    ("QFN-72", "Package_DFN_QFN.pretty/QFN-72-1EP_10x10mm_P0.5mm_EP6x6mm.kicad_mod"),
    ("QFN-76", "Package_DFN_QFN.pretty/QFN-76-1EP_9x9mm_P0.4mm_EP5.81x6.31mm.kicad_mod"),
    ("QFN-80", "Package_DFN_QFN.pretty/QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.kicad_mod"),
```

- [ ] **Step 3: Run the full regression suite**

Run: `python -m pytest -q`
Expected: PASS, 522 tests total (482 existing + 20 new `test_pipeline_matches_real_footprint` cases + 20 new `test_pipeline_naming.py`-style... actually just the 20 regression cases plus the 2 new naming tests from Task 1 = 482 + 20 + 2 = 504; run the suite and read the actual final count rather than assuming).

If any of the 20 cases fails: the failure message names the exact descriptor, pad number, and which of position/size/pad_type/shape/roundrect_rratio mismatched. Cross-check that pad's real `(at ...)`/`(size ...)` against the real file directly (`/usr/share/kicad/footprints/Package_DFN_QFN.pretty/<file>`) and adjust that variant's `pad_size`/`pitch`/`pad_lead_extension` (or add an explicit `pad_offset` override, same escape hatch already used for 2 of 8 real LQFP samples) until it passes — do not adjust the regression tolerance itself.

- [ ] **Step 4: Point the visual review tool at the 20 new cases**

In `kicad_fpdb/visual_compare.py`, replace the `PREVIEW_ONLY_DESCRIPTORS` set (lines 190-194) with:

```python
PREVIEW_ONLY_DESCRIPTORS = {
    "QFN-12", "QFN-16", "QFN-16 p65", "QFN-20", "QFN-24", "QFN-28",
    "QFN-32", "QFN-32 p65", "QFN-36", "QFN-40", "QFN-44", "QFN-48",
    "QFN-48 p4", "QFN-56", "QFN-60", "QFN-64", "QFN-68", "QFN-72",
    "QFN-76", "QFN-80",
}
```

- [ ] **Step 5: Regenerate the review page and eyeball every QFN case**

Run: `python -m kicad_fpdb.visual_compare`

Open `renders/review.html` and check each of the 20 QFN panels: the courtyard's stepped outline should closely track the reference (small ~0.005mm line-position differences, invisible at render scale, are expected and acceptable — same class of approximation already documented for SOIC/LQFP), the F.Fab chamfer should sit at the same corner as the reference, the exposed pad and its 4-way paste split should visually align with the reference's own EP/paste pads, and the pin-1 circle marker should sit just outside pad 1 at the top-left (this is the project's own established departure from real KiCad's filled-triangle marker — confirm it looks reasonable, not that it matches the reference exactly). Note any visual mismatch found; if one exists, treat it as a real finding and fix the underlying YAML param (not the review tool) before continuing.

- [ ] **Step 6: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/reference_cases.py kicad_fpdb/visual_compare.py renders/review.html
git commit -m "$(cat <<'EOF'
Add QFN family: 20 generic single-EP variants, 12-80 pins

Reuses quad_perimeter and the existing exposed-pad/courtyard/
fab-outline pipeline entirely -- pure data addition. QFN-16/-32/-48
each get a second body/pitch class via the existing width-class
mechanism, which also covers the 3 pin counts (8, 42, 52) whose
real files don't fit quad_perimeter and have no same-pin-count
generic alternative.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Documentation

**Files:**
- Modify: `CLAUDE.md` (append a narrative bullet before the `## TODO` section; add/adjust TODO items)
- Modify: `CHANGELOG.md` (new dated entry at the top, per this project's "new heading per session, never trim old entries" convention)

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing consumed by other tasks — this is the terminal task.

- [ ] **Step 1: Add a CLAUDE.md narrative bullet**

Insert a new bullet before the `## TODO` heading in `CLAUDE.md`, summarizing: the QFN family added (20 generic single-EP variants, 12-80 pins), that it reuses `quad_perimeter` and the existing exposed-pad/courtyard/fab-outline pipeline with zero new code besides the `naming.py` generalization, the width-class mechanism used for QFN-16/-32/-48's second body/pitch class, and that QFN-8/-42/-52 don't fit `quad_perimeter` (dual-row layout / uneven per-side pin counts) with no same-pin-count generic alternative available.

- [ ] **Step 2: Update the TODO list**

In `CLAUDE.md`'s `## TODO` section: update the "Expand `data/kicad-fpdb.yaml` coverage... additional package families (QFN, BGA, etc.)" bullet to note QFN is now done (20 generic single-EP variants); add new TODO items for what this batch deliberately excluded: QFN vendor-specific variants (HVQFN/VQFN/DHVQFN/...), multi-EP QFN variants (2EP/3EP/4EP/5EP — not supported by the current single-EP `ep_size` mechanism), QFN `_ThermalVias` siblings (needs a real via-array primitive, same deferred item as SOIC-8-1EP's), and a possible future `dual_row_grid`-based QFN-8-style 2-row QFN family (or similar) for the pin counts that don't fit `quad_perimeter`.

- [ ] **Step 3: Add a CHANGELOG.md entry**

Add a new dated version heading at the top of `CHANGELOG.md` (increment the version per this project's existing pattern, e.g. `v0.0.16`) summarizing: added the QFN family (20 generic single-EP variants, 12-80 pins), fully reusing `quad_perimeter` and the existing exposed-pad/courtyard/fab-outline pipeline; extended `descriptive_suffix` to cover QFN (generalizing the existing SOIC/LQFP branch); noted QFN-8/-42/-52 don't fit `quad_perimeter` and were replaced with second body/pitch classes at QFN-16/-32/-48 via the existing width-class mechanism; full suite passing.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
Document the QFN family addition

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
