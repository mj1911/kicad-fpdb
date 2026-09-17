# Exact Reference/Value Text Position Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current flat `0.7mm` + 1.27mm-grid-snap Reference/Value text placement with real KiCad's own (ungridded) placement: a small set of per-family-group flat margins (`0.7mm` default, `0.805mm` for DIP/CERDIP/SMDIP, `0.94mm` for DIP's `socket` modifier, `1.0mm` for R-AXIAL), verified exact or near-exact against every real sample checked.

**Architecture:** `_add_reference_and_value_text` gains a `text_margin_mm` param (default `TEXT_MARGIN_MM = 0.7`, unchanged value); the grid-snap helpers (`_snap_to_grid`, `_snap_outward`, `TEXT_GRID_MM`) are deleted entirely, replaced with plain arithmetic. `generate_footprint` pops `text_margin_mm` from the resolved yaml params the same way `fab_reference_font_size` etc. already are. DIP/CERDIP/SMDIP declare `text_margin_mm: 0.805` at their roots, DIP's (and CERDIP's, in 3 places — its root plus its own `CERDIP-8`/`CERDIP-14` child overrides, which fully replace rather than merge with the root's `socket` modifier) `socket` modifier overrides it to `0.94`, and `R`'s `R-AXIAL` child node declares `1.0`.

**Tech Stack:** Python, pytest. No new dependencies.

## Global Constraints

- No grid-snapping anywhere in text placement — X centering and Y margin are both plain arithmetic now.
- `TEXT_MARGIN_MM`'s default value stays `0.7` (unchanged) — only the snapping behavior and the ability to override it per family change.
- Full test suite (`pytest`) must pass after every task; the regression suite runs on this machine (real KiCad footprint library present).

---

### Task 1: Remove grid-snapping, add `text_margin_mm` mechanism

**Files:**
- Modify: `kicad_fpdb/pipeline.py:1` (remove `import math`), `kicad_fpdb/pipeline.py:21-30` (constants), `kicad_fpdb/pipeline.py:514-527` (delete `_snap_to_grid`/`_snap_outward`), `kicad_fpdb/pipeline.py:551-561` (`_add_reference_and_value_text`), `kicad_fpdb/pipeline.py:686-755` (`generate_footprint`)
- Test: `tests/test_pipeline_text.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_add_reference_and_value_text(geometry, name, text_margin_mm: float = TEXT_MARGIN_MM, fab_reference_font_size=None, fab_reference_thickness=None, fab_reference_rotation=None)`. `generate_footprint` pops `text_margin_mm` (default `TEXT_MARGIN_MM`) from resolved params and passes it through. No yaml changes in this task — every family still resolves to the default `0.7mm`, unchanged from today's flat value, just no longer grid-snapped.

- [ ] **Step 1: Write the failing test**

In `tests/test_pipeline_text.py`, replace `test_reference_and_value_are_snapped_to_005in_grid` (the whole function) with:

```python
def test_reference_and_value_are_not_grid_snapped():
    # Real KiCad never grid-aligns Reference/Value text -- the previous
    # 1.27mm (0.05in) grid-snap was a deliberate stylistic choice this
    # project made, not something real footprints do. R-0603's
    # courtyard is (-1.475, -0.725) to (1.475, 0.725); the plain 0.7mm
    # margin lands at -1.425/1.425, neither a multiple of 1.27.
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_x, ref_y = (float(v) for v in _require_match(AT_3.search(ref_block)).groups())
    value_x, value_y = (float(v) for v in _require_match(AT_3.search(value_block)).groups())

    assert (ref_x, ref_y) == (0.0, -1.425)
    assert (value_x, value_y) == (0.0, 1.425)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_pipeline_text.py -k not_grid_snapped -v`
Expected: FAIL — current output is grid-snapped to `(0.0, -1.27)`/`(0.0, 1.27)` (or similar), not `(-1.425, 1.425)`.

- [ ] **Step 3: Remove grid-snapping and add `text_margin_mm`**

In `kicad_fpdb/pipeline.py`, remove the now-unused `import math` (line 1) — verify first that nothing else in the file uses `math.` (it doesn't, as of this plan; the only two call sites are the functions this step deletes).

Replace the constants block (lines 21-30):

```python
# Margin, in mm, between the outermost silk/courtyard outline edge and
# the Reference/Value text placed above/below it. Default for every
# family except DIP/CERDIP/SMDIP (0.805mm) and R-AXIAL (1.0mm), both
# overridden via the text_margin_mm param -- see docs/superpowers/
# specs/2026-09-17-exact-reference-value-text-position-design.md.
# Verified exact (or near-exact, within real-file rounding noise)
# against real KiCad -- not grid-snapped; real KiCad doesn't grid-
# align this either.
TEXT_MARGIN_MM = 0.7
```

(This removes `TEXT_GRID_MM` entirely — nothing else references it.)

Delete `_snap_to_grid` and `_snap_outward` (lines 514-527) entirely.

Replace `_add_reference_and_value_text` (lines 551-561, i.e. up to but not including the `# Real KiCad also carries a separate fp_text...` comment) with:

```python
def _add_reference_and_value_text(geometry, name: str, text_margin_mm: float = TEXT_MARGIN_MM,
                                   fab_reference_font_size: float | None = None,
                                   fab_reference_thickness: float | None = None,
                                   fab_reference_rotation: float | None = None) -> None:
    min_x, min_y, max_x, max_y = _outline_bounding_box(geometry)
    center_x = (min_x + max_x) / 2
    geometry.texts.append(
        Text(kind="reference", text="REF**", at=(center_x, min_y - text_margin_mm), layer="F.SilkS")
    )
    geometry.texts.append(
        Text(kind="value", text=name, at=(center_x, max_y + text_margin_mm), layer="F.Fab")
    )
```

In `generate_footprint`, add a pop near the other `fab_reference_*` pops (around line 688):

```python
    fab_reference_rotation = params.pop("fab_reference_rotation", None)
    text_margin_mm = params.pop("text_margin_mm", TEXT_MARGIN_MM)
```

And pass it through in the `_add_reference_and_value_text(...)` call (around line 753):

```python
    _add_reference_and_value_text(geometry, name, text_margin_mm=text_margin_mm,
                                   fab_reference_font_size=fab_reference_font_size,
                                   fab_reference_thickness=fab_reference_thickness,
                                   fab_reference_rotation=fab_reference_rotation)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_pipeline_text.py -k not_grid_snapped -v`
Expected: PASS.

- [ ] **Step 5: Run the full text test suite**

Run: `pytest tests/test_pipeline_text.py -v`
Expected: `test_reference_and_value_use_real_dip16_positions` FAILS at this point — it still asserts the old grid-snapped DIP-16 values, and DIP hasn't been given its own `text_margin_mm` override yet (Task 2). Every other test in the file should PASS unchanged, including `test_reference_and_value_never_land_closer_than_the_intended_gap` (its `>= 0.7 - 1e-6` assertion holds exactly now that the margin is applied with plain arithmetic, no snapping to risk rounding inward).

- [ ] **Step 6: Add a leak guard and run the full unit suite**

Add to `tests/test_pipeline_text.py`:

```python
def test_generate_footprint_does_not_leak_text_margin_mm_to_generator():
    # If pipeline.py forgot to pop text_margin_mm before calling the
    # generator, this raises TypeError for an unexpected kwarg.
    generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")
```

Run: `pytest tests/test_pipeline_outline.py -v` (unaffected by this change — confirms no regression elsewhere) and `pytest tests/test_pipeline_text.py -v` (expect the one known DIP-16 failure from Step 5, everything else including the new leak guard passing).

- [ ] **Step 7: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_text.py
git commit -m "Remove Reference/Value text grid-snapping; add text_margin_mm param

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Add per-family text margins and fix the DIP-16 test

**Files:**
- Modify: `data/kicad-fpdb.yaml` (`DIP`, `CERDIP`, `SMDIP` roots; `DIP`'s and `CERDIP`'s `socket` modifiers, including `CERDIP-8`/`CERDIP-14`'s own; `R`'s `R-AXIAL` child)
- Test: `tests/test_pipeline_text.py`

**Interfaces:**
- Consumes: `text_margin_mm` from Task 1.
- Produces: DIP/CERDIP/SMDIP now generate Reference/Value text matching real KiCad's `0.805mm` gap (DIP's/CERDIP's `socket` variants use `0.94mm`), and R-AXIAL uses `1.0mm`.

- [ ] **Step 1: Write the failing test update**

In `tests/test_pipeline_text.py`, update `test_reference_and_value_use_real_dip16_positions`:

```python
def test_reference_and_value_use_real_dip16_positions():
    # DIP-16's courtyard is (-1.05, -1.52) to (8.67, 19.3) -- DIP's own
    # real text margin is 0.805mm (not the 0.7mm default every other
    # family uses), verified against CERDIP-8/CERDIP-14's real files
    # giving this exact value directly, with every other DIP/CERDIP/
    # SMDIP sample checked rounding to 0.80 or 0.81 at the real file's
    # own 2-decimal precision -- consistent with one true value
    # straddling that rounding boundary. No grid-snapping.
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_x, ref_y = (float(v) for v in _require_match(AT_3.search(ref_block)).groups())
    value_x, value_y = (float(v) for v in _require_match(AT_3.search(value_block)).groups())

    assert (ref_x, ref_y) == (3.81, -2.325)
    assert (value_x, value_y) == (3.81, 20.105)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_pipeline_text.py -k dip16_positions -v`
Expected: FAIL — DIP-16 still uses the `0.7mm` default (`ref_y = -1.52 - 0.7 = -2.22`, not `-2.325`).

- [ ] **Step 3: Add the yaml overrides**

In `data/kicad-fpdb.yaml`:

`DIP` root's `params` block — add `text_margin_mm: 0.805` alongside the other flat params (e.g. near `body_margin: 1.33`).

`DIP`'s `socket` modifier (the one under `DIP`'s `modifiers:`, currently declaring `socket_margin_x`/`_y`/`courtyard_margin_x`/`_y`/`courtyard_from_pad_center`/`_with`) — add `text_margin_mm: 0.94` to that same dict.

`CERDIP` root's `params` block — add `text_margin_mm: 0.805`.

`CERDIP`'s root-level `socket` modifier (under `CERDIP`'s own `modifiers:`) — add `text_margin_mm: 0.94`.

`CERDIP-8`'s own `socket` modifier override (under `CERDIP.children.CERDIP-8.modifiers.socket`) — add `text_margin_mm: 0.94`. This child's `socket` entry fully replaces the root's rather than merging (per the existing comment there), so it needs its own copy of every key, same as `courtyard_from_pad_center` and `_with` already are duplicated there.

`CERDIP-14`'s own `socket` modifier override (`CERDIP.children.CERDIP-14.modifiers.socket`) — add `text_margin_mm: 0.94`, same reasoning.

`SMDIP` root's `params` block — add `text_margin_mm: 0.805`.

`R`'s `R-AXIAL` child node (`R.children.R-AXIAL.params`, the intermediate node shared by all 4 DIN body sizes) — add `text_margin_mm: 1.0`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_pipeline_text.py -k dip16_positions -v`
Expected: PASS.

- [ ] **Step 5: Run the full text and outline unit test suites**

Run: `pytest tests/test_pipeline_text.py tests/test_pipeline_outline.py -v`
Expected: all PASS.

- [ ] **Step 6: Spot-check DIP's `socket` and CERDIP by hand**

Run:

```bash
python3 -c "
from kicad_fpdb.pipeline import generate_footprint
import re
for d in ('DIP-14 socket', 'CERDIP-8 socket', 'CERDIP-8', 'SMDIP-8', 'R-AXIAL0204'):
    text = generate_footprint(d, 'data/kicad-fpdb.yaml', name='T')
    m = re.search(r'\(property \"Reference\" \"REF\\*\\*\"\s*\(at ([-\d.]+) ([-\d.]+)', text)
    print(d, m.groups())
"
```

Confirm each descriptor's Reference `at` reflects the expected margin (DIP-14 socket and CERDIP-8 socket use `0.94`; plain CERDIP-8, SMDIP-8 use `0.805`; R-AXIAL0204 uses `1.0`) by comparing against that variant's own courtyard bounding box (from its own generated output or `tests/test_pipeline_outline.py`'s existing fixtures) — not required to match to the file's own display precision, just confirm the right constant applied.

- [ ] **Step 7: Commit**

```bash
git add data/kicad-fpdb.yaml tests/test_pipeline_text.py
git commit -m "Add per-family text_margin_mm overrides for DIP/CERDIP/SMDIP/R-AXIAL

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Verify against the real library and visual review

**Files:**
- Modify: `kicad_fpdb/footprint_diff.py`
- Test: `tests/test_pipeline_regression.py` (via the shared `diff_footprint`)

**Interfaces:**
- Consumes: nothing new from earlier tasks directly — this checks the *output* of Tasks 1-2 against the real library.
- Produces: `diff_footprint` now also compares Reference/Value text position, so the regression suite and `verify_library.py` catch any family this plan's investigation missed.

- [ ] **Step 1: Add Reference/Value position parsing and comparison to `footprint_diff.py`**

Add near the existing pattern constants at the top of `kicad_fpdb/footprint_diff.py`:

```python
REFERENCE_PATTERN = re.compile(r'\(property "Reference" "REF\*\*"\s*\(at ([-\d.]+) ([-\d.]+) 0\)')
VALUE_PATTERN = re.compile(r'\(property "Value" "[^"]*"\s*\(at ([-\d.]+) ([-\d.]+) 0\)')
TEXT_POSITION_TOLERANCE_MM = 0.01
```

Add a parsing helper near `parse_pads`:

```python
def parse_reference_value_positions(text: str) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    ref_match = REFERENCE_PATTERN.search(text)
    value_match = VALUE_PATTERN.search(text)
    ref = (float(ref_match.group(1)), float(ref_match.group(2))) if ref_match else None
    value = (float(value_match.group(1)), float(value_match.group(2))) if value_match else None
    return ref, value
```

Add a comparison block at the end of `diff_footprint` (after the existing triangle-marker check, before `return diffs`):

```python
    real_ref, real_value = parse_reference_value_positions(real_text)
    gen_ref, gen_value = parse_reference_value_positions(generated)
    for label, real_pos, gen_pos in (("Reference", real_ref, gen_ref), ("Value", real_value, gen_value)):
        if real_pos is None or gen_pos is None:
            continue
        rx, ry = real_pos
        gx, gy = gen_pos
        if abs(gx - rx) >= TEXT_POSITION_TOLERANCE_MM or abs(gy - ry) >= TEXT_POSITION_TOLERANCE_MM:
            diffs.append(f"{label} position: generated=({gx}, {gy}) real=({rx}, {ry})")
```

Update the module docstring's tolerance list at the top of the file to mention this new `0.01mm` position tolerance.

- [ ] **Step 2: Run the full suite, including the regression suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`). If any case fails here, it means some family's real text margin doesn't match this plan's investigation (a different value than `0.7`/`0.805`/`0.94`/`1.0`) — read the printed diff (`generated=(...) real=(...)`) to find the actual real gap for that family before adjusting any yaml value, same discipline as every other tolerance-based check in this project.

- [ ] **Step 3: Run `verify_library` for a full report**

Run: `python3 -m kicad_fpdb.verify_library`
Expected: `250/250 cases match exactly.` (plus the existing known-gap note).

- [ ] **Step 4: Visual review**

Run: `python -m kicad_fpdb.render_png --family DIP CERDIP SMDIP R-AXIAL SOIC LQFP --output-dir renders_png -j 12`

Open a plain DIP, a DIP socket variant, and an R-AXIAL case; confirm the Reference/Value text now sits at the same real position in both panels (previously visibly offset by up to ~0.5mm from the old grid-snap).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/footprint_diff.py
git commit -m "Extend diff_footprint to verify Reference/Value text position

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Document in CLAUDE.md and CHANGELOG.md

**Files:**
- Modify: `CLAUDE.md` (narrative log section)
- Modify: `CHANGELOG.md` (top of file)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add a CLAUDE.md entry**

Append a new bullet to `CLAUDE.md`'s narrative log (the `## Claude-isms below` section), after the most recent entry and before `## TODO`:

```markdown
* Replaced Reference/Value text's flat `0.7mm` + 1.27mm-grid-snap
  placement with real KiCad's own (ungridded) placement. Real KiCad
  never grid-aligns this at all — the snap was a deliberate stylistic
  choice this project had made, not something real footprints do. The
  actual gap is a small set of per-family-group flat constants: `0.7mm`
  default (SOIC, LQFP, QFN, R, C, SOT-23, TSOT-23), `0.805mm` for
  DIP/CERDIP/SMDIP (`CERDIP-8`/`CERDIP-14`'s real files give this exact
  value directly; every other DIP-family sample checked rounds to
  `0.80`/`0.81` at the real file's own 2-decimal precision, consistent
  with one true value straddling that boundary), `0.94mm` for DIP's
  `socket` modifier specifically (a genuinely separate constant, not
  something that falls out of the wider socket courtyard automatically
  — verified exact, zero variance, across every socket sample), and
  `1.0mm` for R-AXIAL (exact across all 4 body sizes). New
  `text_margin_mm` param on `_add_outline`'s neighbor
  `_add_reference_and_value_text`, defaulting to the unchanged `0.7mm`
  so most families need no yaml change at all.
  `kicad_fpdb.footprint_diff.diff_footprint` now also compares real
  vs. generated Reference/Value position (`0.01mm` tolerance) so any
  family this investigation missed gets caught by the regression suite
  and `verify_library.py`. See docs/superpowers/specs/2026-09-17-exact-
  reference-value-text-position-design.md.
```

- [ ] **Step 2: Add a CHANGELOG.md entry**

Check the most recent entry's date/version at the top of `CHANGELOG.md`. If it's already dated today, fold this into that existing entry (per this project's own changelog convention); otherwise add a new dated entry above it.

```markdown
* Replaced Reference/Value text's flat-margin-plus-grid-snap placement
  with real KiCad's own ungridded per-family-group margins (`0.7mm`
  default, `0.805mm` DIP/CERDIP/SMDIP, `0.94mm` DIP's `socket`
  modifier, `1.0mm` R-AXIAL). See docs/superpowers/specs/2026-09-17-
  exact-reference-value-text-position-design.md.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the exact Reference/Value text position change in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
