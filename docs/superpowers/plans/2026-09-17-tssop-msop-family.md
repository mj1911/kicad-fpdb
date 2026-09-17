# TSSOP/MSOP Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add TSSOP and MSOP families (25 variants total: 4 MSOP + 21 TSSOP across narrow/wide/xwide body classes), matching real KiCad exactly, using only existing `dual_row_grid`/`_add_outline` mechanics — no pipeline.py changes.

**Architecture:** Pure data addition. New `MSOP` and `TSSOP` roots in `data/kicad-fpdb.yaml`. **Important deviation from SOIC's own pattern**: SOIC's `variants:`/`default_width:` width-class mechanism does NOT work for TSSOP, because silk shape (`silk_two_lines` vs `silk_segments` — genuinely different param sets, not just different values) and pin-1 triangle axis vary jointly by *pin count and* width class, not by width class alone (confirmed: not predictable from any formula). Instead, each pin count is its own child (like LQFP's own per-variant, non-formula-driven pattern) with a **child-level `modifiers:` block** for `w`/`xw` tokens where a wider real variant exists at that same pin count — each modifier's dict is a fully self-contained, independent parameter set (verified via `family_tree.py`: child modifiers merge additively with the root's via `_merge_modifiers`, and `_deep_merge_into` does a plain overwrite for non-dict values, so this works with zero code changes).

**Tech Stack:** YAML, Python, pytest. No new dependencies.

## Global Constraints

- No new generator code or `_add_outline` changes — everything here is existing `dual_row_grid`/`silk_segments`/`silk_two_lines`/`pin1_triangle_*`/stepped-courtyard machinery already used by SOIC/SOT-23.
- Every numeric value below comes directly from the design spec's investigation (`docs/superpowers/specs/2026-09-17-tssop-msop-family-design.md`) — do not recompute or approximate.
- `-1EP` exposed-pad variants, the 3mm-body TSSOP-8 oddball, TSSOP-4, and HTSSOP/ETSSOP are explicitly out of scope (separate follow-ups).
- Full test suite (`pytest`) must pass after every task; the regression suite runs on this machine (real KiCad footprint library present).

---

### Task 1: Add the MSOP family and extend `naming.py`

**Files:**
- Modify: `data/kicad-fpdb.yaml` (new `MSOP` root, inserted right after `SOIC`'s block ends, before the `# two_pad_chip turned out...` comment preceding `R:`)
- Modify: `kicad_fpdb/naming.py` (extend the `("SOIC", "LQFP", "QFN")` branch)
- Modify: `kicad_fpdb/reference_cases.py` (4 new `CASES` entries, inserted right after the last `SOIC-8 ep2_95x4_9_mask2_71x3_4` entry, before `R-0201`)

**Interfaces:**
- Consumes: existing `dual_row_grid`/`_add_outline`/`generate_footprint` machinery — unchanged.
- Produces: `generate_footprint("MSOP-8", ...)` etc. resolve and match their real reference files exactly.

- [ ] **Step 1: Extend `naming.py`**

In `kicad_fpdb/naming.py`, change:

```python
    if family in ("SOIC", "LQFP", "QFN"):
```

to:

```python
    if family in ("SOIC", "LQFP", "QFN", "TSSOP", "MSOP"):
```

- [ ] **Step 2: Add the `MSOP` root to `data/kicad-fpdb.yaml`**

Insert this new root right after `SOIC`'s block (after the `ep2_95x4_9_mask2_71x3_4` entry, before the `# two_pad_chip turned out...` comment):

```yaml
# MSOP: no width-class mechanism -- each of the 4 real plain variants
# declares its own row_spacing/courtyard_body_margin directly (they
# don't share one flat value the way TSSOP's width classes do). See
# docs/superpowers/specs/2026-09-17-tssop-msop-family-design.md.
MSOP:
  generator: dual_row_grid
  params:
    pad_shape: roundrect
    pad_type: smd
    centered: true
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    fab_outline: true
    fab_chamfer: 0.75
  children:
    MSOP-8:
      params: {pitch: 0.65, pad_size: [1.625, 0.4], row_spacing: 4.225, courtyard_body_width: 3.0, courtyard_body_margin: 0.5,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: small, pin1_triangle_anchor_mm: 0.66,
               fab_reference_font_size: 0.75, fab_reference_thickness: 0.11,
               silk_segments: [[[-1.61,-1.61],[1.61,-1.61]], [[-1.61,-1.435],[-1.61,-1.61]], [[-1.61,1.61],[-1.61,1.435]],
                               [[1.61,-1.61],[1.61,-1.435]], [[1.61,1.435],[1.61,1.61]], [[1.61,1.61],[-1.61,1.61]]]}
    MSOP-10:
      params: {pitch: 0.5, pad_size: [1.5, 0.35], row_spacing: 4.2, courtyard_body_width: 3.0, courtyard_body_margin: 0.5,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: small, pin1_triangle_anchor_mm: 0.66,
               fab_reference_font_size: 0.75, fab_reference_thickness: 0.11,
               silk_segments: [[[-1.61,-1.61],[1.61,-1.61]], [[-1.61,-1.435],[-1.61,-1.61]], [[-1.61,1.61],[-1.61,1.435]],
                               [[1.61,-1.61],[1.61,-1.435]], [[1.61,1.435],[1.61,1.61]], [[1.61,1.61],[-1.61,1.61]]]}
    MSOP-12:
      params: {pitch: 0.65, pad_size: [1.45, 0.4], row_spacing: 4.3, courtyard_body_width: 3.0, courtyard_body_margin: 0.39,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: small, pin1_triangle_anchor_mm: 0.665,
               fab_reference_rotation: 90,
               silk_segments: [[[-1.61,-2.1295],[1.61,-2.1295]], [[-1.61,-2.085],[-1.61,-2.1295]], [[-1.61,2.1295],[-1.61,2.085]],
                               [[1.61,-2.1295],[1.61,-2.085]], [[1.61,2.085],[1.61,2.1295]], [[1.61,2.1295],[-1.61,2.1295]]]}
    MSOP-16:
      params: {pitch: 0.5, pad_size: [1.45, 0.3], row_spacing: 4.3, courtyard_body_width: 3.0, courtyard_body_margin: 0.265,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               fab_reference_rotation: 90,
               silk_two_lines: true, body_width: 3.22, body_margin: 0.41}
```

- [ ] **Step 3: Add the 4 `CASES` entries**

In `kicad_fpdb/reference_cases.py`, right after the `("SOIC-8 ep2_95x4_9_mask2_71x3_4", ...)` line:

```python
    ("MSOP-8", "Package_SO.pretty/MSOP-8_3x3mm_P0.65mm.kicad_mod"),
    ("MSOP-10", "Package_SO.pretty/MSOP-10_3x3mm_P0.5mm.kicad_mod"),
    ("MSOP-12", "Package_SO.pretty/MSOP-12_3x4.039mm_P0.65mm.kicad_mod"),
    ("MSOP-16", "Package_SO.pretty/MSOP-16_3x4.039mm_P0.5mm.kicad_mod"),
```

- [ ] **Step 4: Verify**

Run: `python3 -m kicad_fpdb.verify_library --family MSOP`
Expected: `4/4 cases match exactly.` If any diff, read the printed detail and cross-check against the exact real file (`cat /usr/share/kicad*/footprints/Package_SO.pretty/MSOP-8_3x3mm_P0.65mm.kicad_mod` etc.) — every value here was copied directly from a real file, so a mismatch means a transcription error, not a formula problem.

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`).

- [ ] **Step 6: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/naming.py kicad_fpdb/reference_cases.py
git commit -m "Add the MSOP family (4 variants)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Add TSSOP's simple (no-modifier) variants — TSSOP-8/14/16/20/64

**Files:**
- Modify: `data/kicad-fpdb.yaml` (new `TSSOP` root with these 5 children)
- Modify: `kicad_fpdb/reference_cases.py` (5 new `CASES` entries, right after the MSOP ones added in Task 1)

**Interfaces:**
- Consumes: same as Task 1.
- Produces: `generate_footprint("TSSOP-8", ...)` etc. (no width modifier) match their real files.

- [ ] **Step 1: Add the `TSSOP` root with these 5 children**

Insert this new root right after the `MSOP` root added in Task 1 (still before the `# two_pad_chip turned out...` comment):

```yaml
# TSSOP: same two-row gullwing topology as SOIC/DIP. Does NOT use
# SOIC's variants:/default_width: width-class mechanism -- silk shape
# (silk_two_lines vs silk_segments, genuinely different param sets)
# and pin-1 triangle axis vary jointly by pin count AND width class,
# not by width class alone, so each pin count is its own child (like
# LQFP's own per-variant pattern) with a child-level `modifiers:`
# block for `w`/`xw` where a wider real variant exists at that pin
# count. See docs/superpowers/specs/2026-09-17-tssop-msop-family-
# design.md.
TSSOP:
  generator: dual_row_grid
  variant_param: pin_count
  params:
    pad_shape: roundrect
    pad_type: smd
    centered: true
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    fab_outline: true
    fab_chamfer: 1.0
  children:
    TSSOP-8:
      params: {pin_count: 8, pitch: 0.65, pad_size: [1.475, 0.4], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.525, fab_chamfer: 0.75,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: small, pin1_triangle_anchor_mm: 0.67,
               silk_segments: [[[-2.31,-1.61],[2.31,-1.61]], [[-2.31,-1.435],[-2.31,-1.61]], [[-2.31,1.61],[-2.31,1.435]],
                               [[2.31,-1.61],[2.31,-1.435]], [[2.31,1.435],[2.31,1.61]], [[2.31,1.61],[-2.31,1.61]]]}
    TSSOP-14:
      params: {pin_count: 14, pitch: 0.65, pad_size: [1.475, 0.4], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.55,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: large, pin1_triangle_anchor_mm: 0.75,
               silk_segments: [[[-2.31,-2.61],[2.31,-2.61]], [[-2.31,-2.41],[-2.31,-2.61]], [[-2.31,2.61],[-2.31,2.41]],
                               [[2.31,-2.61],[2.31,-2.41]], [[2.31,2.41],[2.31,2.61]], [[2.31,2.61],[-2.31,2.61]]]}
    TSSOP-16:
      params: {pin_count: 16, pitch: 0.65, pad_size: [1.475, 0.4], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.225,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               silk_two_lines: true, body_width: 4.62, body_margin: 0.46}
    TSSOP-20:
      params: {pin_count: 20, pitch: 0.65, pad_size: [1.475, 0.4], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.325,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               silk_two_lines: true, body_width: 4.62, body_margin: 0.46}
    TSSOP-64:
      params: {pin_count: 64, pitch: 0.5, pad_size: [1.475, 0.3], row_spacing: 7.425, courtyard_body_width: 6.1, courtyard_body_margin: 0.75,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: large, pin1_triangle_anchor_mm: 0.75,
               silk_segments: [[[-3.16,-8.61],[3.16,-8.61]], [[-3.16,-8.16],[-3.16,-8.61]], [[-3.16,8.61],[-3.16,8.16]],
                               [[3.16,-8.61],[3.16,-8.16]], [[3.16,8.16],[3.16,8.61]], [[3.16,8.61],[-3.16,8.61]]]}
```

(Note: `TSSOP-64` has no real narrower variant at that pin count, so its base descriptor directly uses the wide/6.1mm-body data — there's nothing narrower to make the "default".)

- [ ] **Step 2: Add the 5 `CASES` entries**

In `kicad_fpdb/reference_cases.py`, right after the 4 MSOP entries from Task 1:

```python
    ("TSSOP-8", "Package_SO.pretty/TSSOP-8_4.4x3mm_P0.65mm.kicad_mod"),
    ("TSSOP-14", "Package_SO.pretty/TSSOP-14_4.4x5mm_P0.65mm.kicad_mod"),
    ("TSSOP-16", "Package_SO.pretty/TSSOP-16_4.4x5mm_P0.65mm.kicad_mod"),
    ("TSSOP-20", "Package_SO.pretty/TSSOP-20_4.4x6.5mm_P0.65mm.kicad_mod"),
    ("TSSOP-64", "Package_SO.pretty/TSSOP-64_6.1x17mm_P0.5mm.kicad_mod"),
```

If any of these exact filenames don't match what's actually on disk, run `ls /usr/share/kicad*/footprints/Package_SO.pretty/ | grep "^TSSOP-8_\|^TSSOP-14_\|^TSSOP-16_\|^TSSOP-20_\|^TSSOP-64_"` first and correct the relpath — the design spec's own investigation confirmed these exist, but confirm the exact filename spelling before running the regression suite.

- [ ] **Step 3: Verify**

Run: `python3 -m kicad_fpdb.verify_library --family TSSOP`
Expected: `5/5 cases match exactly.`

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip).

- [ ] **Step 5: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/reference_cases.py
git commit -m "Add TSSOP-8/14/16/20/64 (no width modifier needed)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Add TSSOP-24 and TSSOP-56 (narrow + wide via `w` modifier)

**Files:**
- Modify: `data/kicad-fpdb.yaml` (add `TSSOP-24`, `TSSOP-56` children, each with a `w` modifier)
- Modify: `kicad_fpdb/reference_cases.py` (4 new `CASES` entries: `TSSOP-24`, `TSSOP-24 w`, `TSSOP-56`, `TSSOP-56 w`)

**Interfaces:**
- Consumes: same as Task 1/2.
- Produces: `generate_footprint("TSSOP-24", ...)` and `generate_footprint("TSSOP-24 w", ...)` (and the `-56` equivalents) each match their own real file.

- [ ] **Step 1: Add the 2 children to the `TSSOP` node's `children:` block**

```yaml
    TSSOP-24:
      params: {pin_count: 24, pitch: 0.65, pad_size: [1.475, 0.4], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.325,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               silk_two_lines: true, body_width: 4.62, body_margin: 0.46}
      modifiers:
        w:
          row_spacing: 7.425
          courtyard_body_width: 6.1
          courtyard_body_margin: 0.325
          pin1_marker_style: triangle
          pin1_triangle_axis: x
          silk_two_lines: true
          body_width: 6.32
          body_margin: 0.46
    TSSOP-56:
      params: {pin_count: 56, pitch: 0.4, pad_size: [1.475, 0.25], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.25,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               silk_two_lines: true, body_width: 4.62, body_margin: 0.385}
      modifiers:
        w:
          pitch: 0.5
          pad_size: [1.475, 0.3]
          row_spacing: 7.425
          courtyard_body_width: 6.1
          courtyard_body_margin: 0.25
          pin1_marker_style: triangle
          pin1_triangle_axis: x
          silk_two_lines: true
          body_width: 6.32
          body_margin: 0.41
```

- [ ] **Step 2: Add the 4 `CASES` entries**

```python
    ("TSSOP-24", "Package_SO.pretty/TSSOP-24_4.4x7.8mm_P0.65mm.kicad_mod"),
    ("TSSOP-24 w", "Package_SO.pretty/TSSOP-24_6.1x7.8mm_P0.65mm.kicad_mod"),
    ("TSSOP-56", "Package_SO.pretty/TSSOP-56_4.4x11.3mm_P0.4mm.kicad_mod"),
    ("TSSOP-56 w", "Package_SO.pretty/TSSOP-56_6.1x14mm_P0.5mm.kicad_mod"),
```

Confirm exact filenames on disk first (`ls .../Package_SO.pretty/ | grep "^TSSOP-24_\|^TSSOP-56_"`) and correct if they differ.

- [ ] **Step 3: Verify**

Run: `python3 -m kicad_fpdb.verify_library --family TSSOP`
Expected: `9/9 cases match exactly.` (the 5 from Task 2 plus these 4).

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip).

- [ ] **Step 5: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/reference_cases.py
git commit -m "Add TSSOP-24/56 with a 'w' (wide) modifier variant

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Add TSSOP-28/32/36/48 (narrow + wide + xwide via `w`/`xw` modifiers)

**Files:**
- Modify: `data/kicad-fpdb.yaml` (add `TSSOP-28`, `TSSOP-32`, `TSSOP-36`, `TSSOP-48` children, each with `w` and `xw` modifiers)
- Modify: `kicad_fpdb/reference_cases.py` (12 new `CASES` entries: 3 per pin count × 4 pin counts)

**Interfaces:**
- Consumes: same as Task 1/2/3.
- Produces: `generate_footprint("TSSOP-28", ...)`, `"TSSOP-28 w"`, `"TSSOP-28 xw"` (and the 32/36/48 equivalents) each match their own real file.

- [ ] **Step 1: Add the 4 children to the `TSSOP` node's `children:` block**

```yaml
    TSSOP-28:
      params: {pin_count: 28, pitch: 0.65, pad_size: [1.475, 0.4], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.625,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: large, pin1_triangle_anchor_mm: 0.75,
               silk_segments: [[[-2.31,-4.96],[2.31,-4.96]], [[-2.31,-4.685],[-2.31,-4.96]], [[-2.31,4.96],[-2.31,4.685]],
                               [[2.31,-4.96],[2.31,-4.685]], [[2.31,4.685],[2.31,4.96]], [[2.31,4.96],[-2.31,4.96]]]}
      modifiers:
        w:
          row_spacing: 7.425
          courtyard_body_width: 6.1
          courtyard_body_margin: 0.625
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-3.16,-4.96],[3.16,-4.96]], [[-3.16,-4.685],[-3.16,-4.96]], [[-3.16,4.96],[-3.16,4.685]],
                          [[3.16,-4.96],[3.16,-4.685]], [[3.16,4.685],[3.16,4.96]], [[3.16,4.96],[-3.16,4.96]]]
        xw:
          row_spacing: 9.325
          courtyard_body_width: 8.0
          courtyard_body_margin: 0.625
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-4.11,-4.96],[4.11,-4.96]], [[-4.11,-4.685],[-4.11,-4.96]], [[-4.11,4.96],[-4.11,4.685]],
                          [[4.11,-4.96],[4.11,-4.685]], [[4.11,4.685],[4.11,4.96]], [[4.11,4.96],[-4.11,4.96]]]
    TSSOP-32:
      params: {pin_count: 32, pitch: 0.4, pad_size: [1.475, 0.25], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.25,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               silk_two_lines: true, body_width: 4.62, body_margin: 0.385}
      modifiers:
        w:
          pitch: 0.65
          pad_size: [1.475, 0.4]
          row_spacing: 7.425
          courtyard_body_width: 6.1
          courtyard_body_margin: 0.625
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-3.16,-5.61],[3.16,-5.61]], [[-3.16,-5.335],[-3.16,-5.61]], [[-3.16,5.61],[-3.16,5.335]],
                          [[3.16,-5.61],[3.16,-5.335]], [[3.16,5.335],[3.16,5.61]], [[3.16,5.61],[-3.16,5.61]]]
        xw:
          pitch: 0.65
          pad_size: [1.475, 0.4]
          row_spacing: 9.325
          courtyard_body_width: 8.0
          courtyard_body_margin: 0.625
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-4.11,-5.61],[4.11,-5.61]], [[-4.11,-5.335],[-4.11,-5.61]], [[-4.11,5.61],[-4.11,5.335]],
                          [[4.11,-5.61],[4.11,-5.335]], [[4.11,5.335],[4.11,5.61]], [[4.11,5.61],[-4.11,5.61]]]
    TSSOP-36:
      params: {pin_count: 36, pitch: 0.5, pad_size: [1.475, 0.3], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.6,
               pin1_marker_style: triangle, pin1_triangle_axis: y, pin1_triangle_size: large, pin1_triangle_anchor_mm: 0.75,
               silk_segments: [[[-2.31,-4.96],[2.31,-4.96]], [[-2.31,-4.66],[-2.31,-4.96]], [[-2.31,4.96],[-2.31,4.66]],
                               [[2.31,-4.96],[2.31,-4.66]], [[2.31,4.66],[2.31,4.96]], [[2.31,4.96],[-2.31,4.96]]]}
      modifiers:
        w:
          pitch: 0.65
          pad_size: [1.475, 0.4]
          row_spacing: 7.425
          courtyard_body_width: 6.1
          courtyard_body_margin: 0.725
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-3.16,-6.36],[3.16,-6.36]], [[-3.16,-5.985],[-3.16,-6.36]], [[-3.16,6.36],[-3.16,5.985]],
                          [[3.16,-6.36],[3.16,-5.985]], [[3.16,5.985],[3.16,6.36]], [[3.16,6.36],[-3.16,6.36]]]
        xw:
          pitch: 0.65
          pad_size: [1.475, 0.4]
          row_spacing: 9.325
          courtyard_body_width: 8.0
          courtyard_body_margin: 0.725
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-4.11,-6.36],[4.11,-6.36]], [[-4.11,-5.985],[-4.11,-6.36]], [[-4.11,6.36],[-4.11,5.985]],
                          [[4.11,-6.36],[4.11,-5.985]], [[4.11,5.985],[4.11,6.36]], [[4.11,6.36],[-4.11,6.36]]]
    TSSOP-48:
      params: {pin_count: 48, pitch: 0.4, pad_size: [1.475, 0.25], row_spacing: 5.725, courtyard_body_width: 4.4, courtyard_body_margin: 0.25,
               pin1_marker_style: triangle, pin1_triangle_axis: x,
               silk_two_lines: true, body_width: 4.62, body_margin: 0.385}
      modifiers:
        w:
          pitch: 0.5
          pad_size: [1.475, 0.3]
          row_spacing: 7.425
          courtyard_body_width: 6.1
          courtyard_body_margin: 0.5
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-3.16,-6.36],[3.16,-6.36]], [[-3.16,-6.16],[-3.16,-6.36]], [[-3.16,6.36],[-3.16,6.16]],
                          [[3.16,-6.36],[3.16,-6.16]], [[3.16,6.16],[3.16,6.36]], [[3.16,6.36],[-3.16,6.36]]]
        xw:
          pitch: 0.5
          pad_size: [1.475, 0.3]
          row_spacing: 9.325
          courtyard_body_width: 8.0
          courtyard_body_margin: 0.5
          pin1_marker_style: triangle
          pin1_triangle_axis: y
          pin1_triangle_size: large
          pin1_triangle_anchor_mm: 0.75
          silk_segments: [[[-4.11,-6.36],[4.11,-6.36]], [[-4.11,-6.16],[-4.11,-6.36]], [[-4.11,6.36],[-4.11,6.16]],
                          [[4.11,-6.36],[4.11,-6.16]], [[4.11,6.16],[4.11,6.36]], [[4.11,6.36],[-4.11,6.36]]]
```

- [ ] **Step 2: Add the 12 `CASES` entries**

```python
    ("TSSOP-28", "Package_SO.pretty/TSSOP-28_4.4x9.7mm_P0.65mm.kicad_mod"),
    ("TSSOP-28 w", "Package_SO.pretty/TSSOP-28_6.1x9.7mm_P0.65mm.kicad_mod"),
    ("TSSOP-28 xw", "Package_SO.pretty/TSSOP-28_8x9.7mm_P0.65mm.kicad_mod"),
    ("TSSOP-32", "Package_SO.pretty/TSSOP-32_4.4x6.5mm_P0.4mm.kicad_mod"),
    ("TSSOP-32 w", "Package_SO.pretty/TSSOP-32_6.1x11mm_P0.65mm.kicad_mod"),
    ("TSSOP-32 xw", "Package_SO.pretty/TSSOP-32_8x11mm_P0.65mm.kicad_mod"),
    ("TSSOP-36", "Package_SO.pretty/TSSOP-36_4.4x9.7mm_P0.5mm.kicad_mod"),
    ("TSSOP-36 w", "Package_SO.pretty/TSSOP-36_6.1x12.5mm_P0.65mm.kicad_mod"),
    ("TSSOP-36 xw", "Package_SO.pretty/TSSOP-36_8x12.5mm_P0.65mm.kicad_mod"),
    ("TSSOP-48", "Package_SO.pretty/TSSOP-48_4.4x9.7mm_P0.4mm.kicad_mod"),
    ("TSSOP-48 w", "Package_SO.pretty/TSSOP-48_6.1x12.5mm_P0.5mm.kicad_mod"),
    ("TSSOP-48 xw", "Package_SO.pretty/TSSOP-48_8x12.5mm_P0.5mm.kicad_mod"),
```

Confirm exact filenames on disk first (`ls .../Package_SO.pretty/ | grep "^TSSOP-28_\|^TSSOP-32_\|^TSSOP-36_\|^TSSOP-48_"`) and correct if they differ.

- [ ] **Step 3: Verify**

Run: `python3 -m kicad_fpdb.verify_library --family TSSOP`
Expected: `21/21 cases match exactly.` (the 9 from Tasks 2/3 plus these 12).

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip).

- [ ] **Step 5: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/reference_cases.py
git commit -m "Add TSSOP-28/32/36/48 with 'w'/'xw' (wide/xwide) modifier variants

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Full verification, visual review, and documentation

**Files:**
- Modify: `CLAUDE.md` (narrative log section and TODO list)
- Modify: `CHANGELOG.md` (top of file)

**Interfaces:** None — verification and documentation only.

- [ ] **Step 1: Full-family verification**

Run: `python3 -m kicad_fpdb.verify_library --family TSSOP MSOP`
Expected: `25/25 cases match exactly.`

Run: `python3 -m kicad_fpdb.verify_library`
Expected: `<total>/<total> cases match exactly.` (every case in `CASES`, confirming nothing else regressed).

- [ ] **Step 2: Full test suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`).

- [ ] **Step 3: Visual review**

Run: `python -m kicad_fpdb.render_png --family TSSOP MSOP --output-dir renders_png -j 12`

Open a small (`TSSOP-8`), a wide/xwide pair (`TSSOP-28_w`/`TSSOP-28_xw` or similar filenames), and both MSOP square/tall variants (`MSOP-8`, `MSOP-12`) — confirm the generated (left) and reference (right) panels match, including that the 6-line corner-tick silk variants and 2-line variants both render correctly, and that `TSSOP-24`/`TSSOP-24_w`'s silk bodies are visibly different widths.

- [ ] **Step 4: Add a CLAUDE.md entry**

Append a new bullet to `CLAUDE.md`'s narrative log (the `## Claude-isms below` section), after the most recent entry and before `## TODO`:

```markdown
* Added the TSSOP and MSOP families (25 variants: 4 MSOP + 21 TSSOP
  across narrow/4.4mm, wide/6.1mm, and xwide/8mm body classes) — pure
  data addition, zero new code, reusing `dual_row_grid` and every
  existing `_add_outline` mechanism (`silk_segments`, `silk_two_lines`,
  the stepped courtyard, both pin-1 triangle axes). Deviates from
  SOIC's own `variants:`/`default_width:` width-class mechanism: TSSOP's
  silk shape (a 6-segment corner-tick body via `silk_segments`, or a
  plain `silk_two_lines` body — genuinely different param sets, not
  just different values) and pin-1 triangle axis vary jointly by pin
  count *and* width class, not by width class alone, with no formula
  (confirmed against the real library) — so each pin count is its own
  child (like LQFP's own per-variant pattern), with a **child-level**
  `modifiers:` block for `w`/`xw` tokens carrying a fully independent
  parameter set, rather than a shared root-level width-class dict.
  `fab_chamfer`/`pin1_triangle_size`/`pin1_triangle_anchor_mm` also
  split along a MSOP-and-TSSOP-8 (`0.75`/`small`/`0.66-0.67`) vs.
  every-other-TSSOP-pin-count (`1.0`/`large`/`0.75`) line, not by width
  class. Where multiple real pitch options exist for a given (pin
  count, width class), picked the largest available — not arbitrary,
  since it's a physical constraint (finer pitch becomes mechanically
  required only once more pins must fit a JEDEC-standard body length),
  confirmed by surveying the full real pitch distribution before
  finalizing. `-1EP` exposed-pad variants deliberately deferred as a
  separate follow-up spec (directly reuses the SOIC-8-1EP paste-split
  mechanism). See docs/superpowers/specs/2026-09-17-tssop-msop-family-
  design.md.
```

Update the TODO entry about expanding coverage to note this is now done, and add the `-1EP` follow-up:

```markdown
* Expand `data/kicad-fpdb.yaml` coverage: more DIP/SOIC pitches and
  widths, additional package families (BGA, SOD diodes, etc.) — each
  needs its own hand-verified real-footprint regression case per the
  existing pattern in `tests/test_pipeline_regression.py`.
  SOT-23/-5/-6/-8, TSOT-23-5/-6/-8, QFN (20 generic single-EP
  variants), chip passives through 1210/1812/2010/2512, and TSSOP/MSOP
  (25 variants) are done.
* TSSOP/MSOP `-1EP` exposed-pad variants (8 TSSOP + 10 MSOP real
  files) — directly reuses the SOIC-8-1EP paste-split/EP mechanism
  already built, deliberately deferred as its own follow-up spec
  rather than bundled into the base family.
* TSSOP's oddball 3mm-body 8-pin variant, `TSSOP-4` (a 4-pin/4mm-pitch
  one-off), and vendor-prefixed HTSSOP/ETSSOP heatsink-variant
  families (a genuinely different real family name, not a modifier on
  plain TSSOP) — same deferred treatment as SOIC-8-1EP's own
  `_ThermalVias` siblings.
* Additional real TSSOP pitch options at (pin_count, width_class)
  combos where more than one exists (beyond the one already covered)
  — a natural follow-up via a `p40`/`p50`-style modifier, same pattern
  as QFN's `p65`/`p4`.
```

- [ ] **Step 5: Add a CHANGELOG.md entry**

Check the most recent entry's date/version at the top of `CHANGELOG.md`. If it's already dated today, fold this into that existing entry (per this project's own changelog convention); otherwise add a new dated entry above it.

```markdown
* Added the TSSOP and MSOP families (25 variants), pure data addition
  reusing every existing `dual_row_grid`/`_add_outline` mechanism. See
  docs/superpowers/specs/2026-09-17-tssop-msop-family-design.md.
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the TSSOP/MSOP family in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
