# Chip Passive Larger Sizes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add R-1210, R-1812, R-2010, R-2512, C-1210, and C-1812 chip passive descriptors, matching real KiCad exactly, using only existing `two_pad_chip` mechanics — no new code.

**Architecture:** Pure data addition. 6 new child descriptors under `data/kicad-fpdb.yaml`'s existing `R`/`C` nodes, 4 new `kicad_fpdb.naming.IMPERIAL_TO_METRIC` entries, 6 new `kicad_fpdb.reference_cases.CASES` entries.

**Tech Stack:** YAML, Python, pytest. No new dependencies.

## Global Constraints

- No new generator code or `_add_outline` changes — every value here is a hand-verified constant plugged into the existing `two_pad_chip` param set, same convention as every existing `R-*`/`C-*` child.
- `_HandSolder` variants and `C-2010`/`C-2512` are explicitly out of scope (see spec's Non-goals).
- Full test suite (`pytest`) must pass after every task; the regression suite runs on this machine (real KiCad footprint library present).

---

### Task 1: Add the 6 descriptors and verify against the real library

**Files:**
- Modify: `data/kicad-fpdb.yaml` (`R` and `C` nodes' `children:`)
- Modify: `kicad_fpdb/naming.py` (`IMPERIAL_TO_METRIC`)
- Modify: `kicad_fpdb/reference_cases.py` (`CASES`)
- Test: `tests/test_pipeline_regression.py` (via the shared `diff_footprint`, parametrized from `CASES` — no new test code needed, just new data)

**Interfaces:**
- Consumes: existing `two_pad_chip` generator and `_add_outline`/`generate_footprint` machinery — unchanged.
- Produces: `generate_footprint("R-1210", ...)` etc. now resolve and produce output matching their real reference file exactly.

- [ ] **Step 1: Add the 4 new `IMPERIAL_TO_METRIC` entries**

In `kicad_fpdb/naming.py`, change:

```python
IMPERIAL_TO_METRIC = {
    "0201": "0603",
    "0402": "1005",
    "0603": "1608",
    "0805": "2012",
    "1206": "3216",
}
```

to:

```python
IMPERIAL_TO_METRIC = {
    "0201": "0603",
    "0402": "1005",
    "0603": "1608",
    "0805": "2012",
    "1206": "3216",
    "1210": "3225",
    "1812": "4532",
    "2010": "5025",
    "2512": "6332",
}
```

- [ ] **Step 2: Add the 4 new `R` descriptors to `data/kicad-fpdb.yaml`**

In `data/kicad-fpdb.yaml`, `R`'s `children:` block, add these 4 entries right after the existing `R-1206` entry (before the `# THT axial resistors...` comment):

```yaml
    R-1210:
      params: {pad_pitch: 2.925, pad_size: [1.125, 2.65], silk_y: 1.355, silk_half_length: 0.723737, courtyard_margin_x: 0.255, courtyard_margin_y: 0.255, fab_body_size: [3.2, 2.49], fab_reference_font_size: 0.8, fab_reference_thickness: 0.12}
    R-1812:
      params: {pad_pitch: 4.275, pad_size: [1.125, 3.4], silk_y: 1.71, silk_half_length: 1.386252, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, fab_body_size: [4.5, 3.2], fab_reference_font_size: 1.0, fab_reference_thickness: 0.15}
    R-2010:
      params: {pad_pitch: 4.625, pad_size: [1.225, 2.65], silk_y: 1.36, silk_half_length: 1.527064, courtyard_margin_x: 0.255, courtyard_margin_y: 0.255, fab_body_size: [5.0, 2.5], fab_reference_font_size: 1.0, fab_reference_thickness: 0.15}
    R-2512:
      params: {pad_pitch: 5.925, pad_size: [1.225, 3.35], silk_y: 1.71, silk_half_length: 2.177064, courtyard_margin_x: 0.255, courtyard_margin_y: 0.255, fab_body_size: [6.3, 3.2], fab_reference_font_size: 1.0, fab_reference_thickness: 0.15}
```

- [ ] **Step 3: Add the 2 new `C` descriptors to `data/kicad-fpdb.yaml`**

In `data/kicad-fpdb.yaml`, `C`'s `children:` block, add these 2 entries right after the existing `C-0805` entry:

```yaml
    C-1210:
      params: {pad_pitch: 2.95, pad_size: [1.15, 2.7], silk_y: 1.36, silk_half_length: 0.711252, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, fab_body_size: [3.2, 2.5], fab_reference_font_size: 0.8, fab_reference_thickness: 0.12}
    C-1812:
      params: {pad_pitch: 4.1, pad_size: [1.4, 3.4], silk_y: 1.71, silk_half_length: 1.161252, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, fab_body_size: [4.5, 3.2], fab_reference_font_size: 1.0, fab_reference_thickness: 0.15}
```

- [ ] **Step 4: Add the 6 new `CASES` entries**

In `kicad_fpdb/reference_cases.py`, add right after the existing `("R-1206", ...)` line:

```python
    ("R-1210", "Resistor_SMD.pretty/R_1210_3225Metric.kicad_mod"),
    ("R-1812", "Resistor_SMD.pretty/R_1812_4532Metric.kicad_mod"),
    ("R-2010", "Resistor_SMD.pretty/R_2010_5025Metric.kicad_mod"),
    ("R-2512", "Resistor_SMD.pretty/R_2512_6332Metric.kicad_mod"),
```

and right after the existing `("C-0805", ...)` line:

```python
    ("C-1210", "Capacitor_SMD.pretty/C_1210_3225Metric.kicad_mod"),
    ("C-1812", "Capacitor_SMD.pretty/C_1812_4532Metric.kicad_mod"),
```

- [ ] **Step 5: Run the regression suite for just these 6 new cases**

Run: `python3 -m kicad_fpdb.verify_library --family R C`
Expected: `<N>/<N> cases match exactly.` (the new 6 plus every existing R/C case). If any of the 6 shows a diff, read the printed `generated=(...) real=(...)` detail — it means a transcription error in Step 2/3's params, not a formula problem (every value here was copied directly from the real file).

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`).

- [ ] **Step 7: Visual review**

Run: `python -m kicad_fpdb.render_png --family R C --output-dir renders_png`

Open `renders_png/R-1210.png`, `renders_png/C-1812.png`, etc. and confirm the generated (left) and reference (right) panels match visually.

- [ ] **Step 8: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/naming.py kicad_fpdb/reference_cases.py
git commit -m "Add R-1210/1812/2010/2512 and C-1210/1812 chip passive sizes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Document in CLAUDE.md and CHANGELOG.md

**Files:**
- Modify: `CLAUDE.md` (narrative log section and TODO list)
- Modify: `CHANGELOG.md` (top of file)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add a CLAUDE.md entry**

Append a new bullet to `CLAUDE.md`'s narrative log (the `## Claude-isms below` section), after the most recent entry and before `## TODO`:

```markdown
* Added R-1210/1812/2010/2512 and C-1210/1812 chip passive sizes —
  pure data addition, zero new code, using the exact same `two_pad_chip`
  param set every existing chip-passive size already uses. `_HandSolder`
  variants (wider pads) and `C-2010`/`C-2512` (no real file exists for
  either) are out of scope. See docs/superpowers/specs/2026-09-17-chip-
  passive-larger-sizes-design.md.
```

Update the TODO entry that reads "Expand `data/kicad-fpdb.yaml`
coverage... more chip passive sizes" to note this is now done:

```markdown
* Expand `data/kicad-fpdb.yaml` coverage: more DIP/SOIC pitches and
  widths, additional package families (BGA, etc.) — each needs its own
  hand-verified real-footprint regression case per the existing pattern
  in `tests/test_pipeline_regression.py`. SOT-23/-5/-6/-8,
  TSOT-23-5/-6/-8, QFN (20 generic single-EP variants), and chip
  passives through 1210/1812/2010/2512 are done.
```

- [ ] **Step 2: Add a CHANGELOG.md entry**

Check the most recent entry's date/version at the top of `CHANGELOG.md`. If it's already dated today, fold this into that existing entry (per this project's own changelog convention); otherwise add a new dated entry above it.

```markdown
* Added R-1210/1812/2010/2512 and C-1210/1812 chip passive sizes (pure
  data addition, no new code). See docs/superpowers/specs/2026-09-17-
  chip-passive-larger-sizes-design.md.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the new chip passive sizes in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
