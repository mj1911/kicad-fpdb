# SOT-23-6/-8 Pin-1 Triangle Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give SOT-23-6/-8 (and their byte-identical TSOT-23-6/-8 aliases) the pin-1 triangle marker instead of a circle, reusing SOIC's narrow-class formula and constants exactly (verified exact/near-exact against both real reference files). SOT-23 and SOT-23-5 (asymmetric, `pin1_marker: false`) are untouched — only packages that can physically be placed backwards get a marker at all, unchanged from today's policy.

**Architecture:** No new params or constants — this is a pure reuse of the `pin1_marker_style: triangle` / `pin1_triangle_axis: y` / `pin1_triangle_size: small` / `pin1_triangle_anchor_mm: 0.65` combination SOIC's narrow class already declares. One real bug fix is needed first: the existing body-anchor calculation in `_add_outline` assumes `courtyard_body_size` is a plain number, but SOT declares it as a `[width, height]` tuple — dividing that directly by 2 raises `TypeError`.

**Tech Stack:** Python, pytest. No new dependencies.

## Global Constraints

- SOT-23 and SOT-23-5 (and TSOT-23-5) must keep `pin1_marker: false` — no marker of any style. Their own override already takes precedence over the shared node's `pin1_marker_style`, so no explicit change is needed there, but every relevant test must keep confirming it.
- No new geometry constants — every value used here already exists (SOIC narrow's `0.65mm` anchor, the existing "small" size class).
- Full test suite (`pytest`) must pass after every task; the regression suite runs on this machine (real KiCad footprint library present, per `CLAUDE.md`'s cross-machine notes).

---

### Task 1: Fix the tuple-`courtyard_body_size` bug in the triangle's body-anchor calculation

**Files:**
- Modify: `kicad_fpdb/pipeline.py:484-486`
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: the existing `pin1_triangle_anchor_mm is not None` branch in `_add_outline` now handles `courtyard_body_size` being either a plain number (QFN/LQFP, unchanged behavior) or a `(width, height)` tuple (SOT, new) — taking the width (index `0`) in the tuple case.

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_pipeline_outline.py`, right after `test_add_outline_triangle_axis_none_still_infers_from_pad_shape`:

```python
def test_add_outline_with_y_axis_triangle_handles_tuple_courtyard_body_size():
    from kicad_fpdb.geometry import FootprintGeometry, Pad
    geometry = FootprintGeometry(name="TEST")
    geometry.pads = [
        Pad(number="1", pad_type="smd", shape="roundrect", at=(-1.0, -1.0), size=(1.0, 0.6)),
        Pad(number="2", pad_type="smd", shape="roundrect", at=(1.0, -1.0), size=(1.0, 0.6)),
    ]
    _add_outline(
        geometry, pin1_marker_style="triangle", pin1_triangle_axis="y",
        pin1_triangle_anchor_mm=0.75, courtyard_margin_y=0.25,
        courtyard_body_size=(3.0, 5.0),
    )

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]

    # Extension axis (Y): apex = pad1's own top edge (-1.0 - 0.3 = -1.3)
    # minus courtyard_margin_y (0.25) minus the fixed 0.01mm silk offset
    # = -1.56; base = apex - 0.33 (the default "small" depth) = -1.89.
    # Perpendicular axis (X): body-anchored using the tuple's WIDTH
    # (index 0, 3.0), not the full tuple -- apex.x = -(3.0/2 + 0.75) =
    # -2.25, independent of pad1.x. Base spread +/-0.24 (the default
    # "small" half-width).
    apex = (-2.25, -1.56)
    base_a = (-2.49, -1.89)
    base_b = (-2.01, -1.89)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert points == {apex, base_a, base_b}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_pipeline_outline.py -k tuple_courtyard_body_size -v`
Expected: FAIL with `TypeError: unsupported operand type(s) for /: 'tuple' and 'int'`.

- [ ] **Step 3: Fix the body-anchor calculation**

In `kicad_fpdb/pipeline.py`, change (around line 484-486):

```python
                body_half = (
                    courtyard_body_width / 2 if courtyard_body_width is not None else courtyard_body_size / 2
                )
```

to:

```python
                if courtyard_body_width is not None:
                    body_half = courtyard_body_width / 2
                elif isinstance(courtyard_body_size, (tuple, list)):
                    body_half = courtyard_body_size[0] / 2
                else:
                    body_half = courtyard_body_size / 2
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_pipeline_outline.py -k tuple_courtyard_body_size -v`
Expected: PASS.

- [ ] **Step 5: Run the full unit test suite to confirm no regression**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS (the scalar `courtyard_body_size` case, e.g. QFN/LQFP's own triangle tests, is unaffected by the new `elif` branch).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "Fix the pin-1 triangle's body-anchor calc for a tuple courtyard_body_size

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Opt SOT-23-6/-8 into the triangle marker and update affected tests

**Files:**
- Modify: `data/kicad-fpdb.yaml` (the `SOT-23-5-6-8` node's `&sot_5_6_8_shared` params)
- Modify: `kicad_fpdb/footprint_diff.py`
- Modify: `tests/test_pipeline_outline.py`
- Test: `tests/test_pipeline_outline.py`, `tests/test_pipeline_regression.py` (via the shared `diff_footprint`)

**Interfaces:**
- Consumes: the fixed triangle branch from Task 1; `TRIANGLE_MARKER_FAMILIES` (already defined in `kicad_fpdb/footprint_diff.py`).
- Produces: `SOT-23-6`, `SOT-23-8`, `TSOT-23-6`, `TSOT-23-8` now generate with a triangle marker matching their real reference files; `SOT-23`, `SOT-23-5`, `TSOT-23-5` remain marker-less; the regression suite and `verify_library.py` now check all of this.

- [ ] **Step 1: Write the failing test updates**

In `tests/test_pipeline_outline.py`, the two existing tests that assert a circle marker for SOT-23-6/-8 (around line 1193-1201) need updating — they're now outdated the same way the earlier SOIC-8 ones were:

```python
def test_generate_footprint_sot23_6_has_triangle_pin1_marker():
    # SOT-23-6 (3+3) and SOT-23-8 (4+4) are symmetric -- rotating the
    # part 180 degrees still fits, so they keep a marker; it's now a
    # triangle (matching real KiCad), not the old circle.
    text = generate_footprint("SOT-23-6", FAMILY_TREE_PATH, name="SOT236_TEST")
    assert "fp_circle" not in text
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        text, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_sot23_8_has_triangle_pin1_marker():
    text = generate_footprint("SOT-23-8", FAMILY_TREE_PATH, name="SOT238_TEST")
    assert "fp_circle" not in text
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        text, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3
```

(This replaces the old `test_generate_footprint_sot23_6_still_has_pin1_marker` / `test_generate_footprint_sot23_8_still_has_pin1_marker` bodies in place — same function names' *purpose*, renamed to match what they now assert. Leave `test_generate_footprint_sot23_has_no_pin1_marker` and `test_generate_footprint_sot23_5_has_no_pin1_marker` exactly as they are — still correct, no marker of any kind.)

Also add a leak guard, near the existing `test_generate_footprint_does_not_leak_pin1_triangle_params_to_generator`:

```python
def test_generate_footprint_does_not_leak_pin1_triangle_params_to_sot_generator():
    # asymmetric_dual_row doesn't accept pin1_triangle_axis/_size/
    # _anchor_mm either -- same guard as the QFN/SOIC/LQFP version,
    # for the generator SOT-23 uses.
    generate_footprint("SOT-23-6", FAMILY_TREE_PATH, name="TEST")
```

- [ ] **Step 2: Run the new/updated tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k "sot23_6_has_triangle or sot23_8_has_triangle or leak_pin1_triangle_params_to_sot" -v`
Expected: the two `_has_triangle_pin1_marker` tests FAIL (`fp_circle` still present, no `fp_poly` triangle yet — the yaml doesn't opt in yet). The leak guard PASSES already (nothing to leak yet).

- [ ] **Step 3: Update the yaml**

In `data/kicad-fpdb.yaml`, find the `SOT-23-5-6-8` node's `&sot_5_6_8_shared` params block (the one already declaring `row_spacing`, `courtyard_body_size: [1.6, 2.9]`, `fab_chamfer`) and add:

```yaml
pin1_marker_style: triangle
pin1_triangle_axis: y
pin1_triangle_size: small
pin1_triangle_anchor_mm: 0.65
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k "sot23_6_has_triangle or sot23_8_has_triangle or has_no_pin1_marker or leak_pin1_triangle_params_to_sot" -v`
Expected: all PASS, including the unchanged `test_generate_footprint_sot23_has_no_pin1_marker` / `test_generate_footprint_sot23_5_has_no_pin1_marker` (confirms `pin1_marker: false` still suppresses everything regardless of the new `pin1_marker_style` on the shared node).

- [ ] **Step 5: Run the full unit test suite**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS.

- [ ] **Step 6: Extend the regression suite's triangle-marker family set**

In `kicad_fpdb/footprint_diff.py`, change:

```python
TRIANGLE_MARKER_FAMILIES = {"QFN", "SOIC", "LQFP"}
```

to:

```python
TRIANGLE_MARKER_FAMILIES = {"QFN", "SOIC", "LQFP", "SOT", "TSOT"}
```

(Both `"SOT"` and `"TSOT"` are needed — `"TSOT-23-6".split()[0].split("-")[0]` is `"TSOT"`, a distinct family head from `"SOT"`.) Update the comment above it (which currently says SOT-23/TSOT-23 are excluded) to reflect that SOT-23-6/-8/TSOT-23-6/-8 are now covered, while SOT-23/SOT-23-5/TSOT-23-5 correctly report no triangle from either side (both real and generated have none, so `diff_footprint`'s existing logic reports no diff without any special-casing).

- [ ] **Step 7: Run the full suite, including the regression suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`). Every SOT-23/TSOT-23 case is now checked for the first time — if any unexpectedly fails, stop and investigate before continuing (read the printed diff; don't loosen `TRIANGLE_POINT_TOLERANCE_MM` without understanding why first, per the tolerance's own existing guidance).

- [ ] **Step 8: Run `verify_library` for a full report**

Run: `python3 -m kicad_fpdb.verify_library --family SOT TSOT`
Expected: `<N>/<N> cases match exactly.`

- [ ] **Step 9: Visual review**

Run: `python -m kicad_fpdb.render_png --family SOT TSOT --output-dir renders_png`

Open `renders_png/SOT-23.png` and `renders_png/SOT-23-5.png` (should show no pin-1 marker in either panel, unchanged) and `renders_png/SOT-23-6.png` / `renders_png/SOT-23-8.png` (should now show a matching triangle in both panels, replacing the old circle in the generated one).

- [ ] **Step 10: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/footprint_diff.py tests/test_pipeline_outline.py
git commit -m "Opt SOT-23-6/-8 (and TSOT-23-6/-8) into the pin-1 triangle marker

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Document in CLAUDE.md and CHANGELOG.md

**Files:**
- Modify: `CLAUDE.md` (narrative log section and TODO list)
- Modify: `CHANGELOG.md` (top of file)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add a CLAUDE.md entry**

Append a new bullet to `CLAUDE.md`'s narrative log (the `## Claude-isms below` section), after the most recent entry and before `## TODO`:

```markdown
* Extended the pin-1 triangle marker to SOT-23-6/-8 (and their
  byte-identical TSOT-23-6/-8 aliases) — a pure reuse of SOIC's
  narrow-class formula and constants (`axis="y"`, `size="small"`,
  `anchor_mm=0.65`), verified exact (SOT-23-6) and near-exact
  (SOT-23-8, the same ~0.005mm rounding-noise category already
  accepted elsewhere) against both real reference files, with zero new
  geometry needed. SOT-23 and SOT-23-5 (`pin1_marker: false`, their
  asymmetric layouts are only placeable one way) are untouched — only
  packages that can physically be placed backwards get a marker at
  all, unchanged from before. One real bug fixed along the way: the
  triangle's body-anchor calculation assumed `courtyard_body_size` was
  always a plain number (true for QFN/LQFP), but SOT declares it as a
  `[width, height]` tuple (a non-square true body) — now takes the
  width specifically instead of raising `TypeError`. See
  docs/superpowers/specs/2026-09-17-sot23-pin1-triangle-marker-
  design.md.
```

Remove the now-resolved TODO entry (the one added when SOIC/LQFP were done, reading roughly "Extend the `pin1_marker_style: triangle` convention to SOT-23 (and TSOT-23)...").

- [ ] **Step 2: Add a CHANGELOG.md entry**

Check the most recent entry's date/version at the top of `CHANGELOG.md`. If it's already dated today, fold this into that existing entry (per this project's own changelog convention); otherwise add a new dated entry above it.

```markdown
* Extended the pin-1 triangle marker to SOT-23-6/-8 (and TSOT-23-6/-8),
  reusing SOIC's narrow-class formula and constants exactly -- no new
  geometry needed. SOT-23/SOT-23-5 stay marker-less, unchanged. Fixed
  a tuple-vs-scalar bug in the triangle's body-anchor calculation along
  the way. See docs/superpowers/specs/2026-09-17-sot23-pin1-triangle-
  marker-design.md.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the SOT-23-6/-8 triangle marker extension in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
