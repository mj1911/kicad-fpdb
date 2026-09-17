# SOIC/LQFP Pin-1 Triangle Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the pin-1 triangle marker (`pin1_marker_style: triangle`, currently QFN-only) to SOIC and LQFP, matching real KiCad's own marker position and size for both families exactly (SOIC/LQFP's extension-axis position has a documented ≤0.01mm residual on some variants — accepted, not chased further per the design spec).

**Architecture:** `_add_outline`'s existing triangle branch (QFN-only today) is generalized in place — not duplicated — with three new optional params: `pin1_triangle_axis` (which axis the marker extends along, explicit instead of inferred from pad shape), `pin1_triangle_size` (selects between two real marker sizes), and `pin1_triangle_anchor_mm` (body-anchored perpendicular-axis position, used by SOIC/LQFP but not QFN). All three default to values that reproduce today's QFN geometry exactly, so QFN's yaml needs zero changes. Along the way, `kicad_fpdb/footprint_diff.py`'s triangle-marker regression check gets a real bug fix (it currently never executes for any descriptor) and a tolerance-based comparison (needed because LQFP's real files have a small, unavoidable rounding residual that exact-match comparison would wrongly flag).

**Tech Stack:** Python, pytest. No new dependencies.

## Global Constraints

- Geometry values (verified against real KiCad reference files, see spec): SOIC narrow uses the existing "small" size (`depth=0.33mm`, `half-width=0.24mm`) with anchor constant `0.65mm`; SOIC wide and LQFP use a new "large" size (`depth=0.47mm`, `half-width=0.34mm`), with anchor constants `0.90mm` (SOIC wide) and `0.75mm` (LQFP).
- QFN's existing triangle geometry must not change at all — every existing QFN unit/regression test must keep passing unchanged.
- The extension-axis formula (`pad-edge − margin − 0.01mm`) is unchanged from QFN's; only the axis it's applied to and the perpendicular-axis anchoring are new.
- Full test suite (`pytest`) must pass after every task; the regression suite is skipped automatically on a machine without the real KiCad footprint library (not the case here, per `CLAUDE.md`'s cross-machine notes).

---

### Task 1: Generalize `_add_outline`'s triangle branch with axis/size/anchor params

**Files:**
- Modify: `kicad_fpdb/pipeline.py:50-57` (constants), `kicad_fpdb/pipeline.py:133-136` (`_add_outline` signature), `kicad_fpdb/pipeline.py:433-461` (triangle branch)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_pad_center_extent(pads, axis)` (already defined and used elsewhere in `kicad_fpdb/pipeline.py`), `kicad_fpdb.geometry.Poly` (already used).
- Produces: `_add_outline(..., pin1_triangle_axis: str | None = None, pin1_triangle_size: str = "small", pin1_triangle_anchor_mm: float | None = None)`. When the triangle branch runs with `pin1_triangle_axis is None`, behavior is byte-identical to today (shape-inferred axis, `"small"` size, pad-relative perpendicular position) — this is QFN's path, unchanged. `axis="y"` with `pin1_triangle_anchor_mm` set is the new SOIC/LQFP path.

- [ ] **Step 1: Write the failing unit tests**

Add to `tests/test_pipeline_outline.py`, right after the existing `test_add_outline_pin1_marker_false_suppresses_triangle_too` (reuses the same `_qfp32_geometry()` fixture already used there — pad 1 at `(-4.175, -2.8)`, size `(1.5, 0.5)`, symmetric pads giving a centroid at x=0):

```python
def test_add_outline_with_y_axis_triangle_uses_body_anchor():
    geometry = _qfp32_geometry()
    _add_outline(
        geometry, body_size=7.22, pin1_marker_style="triangle",
        pin1_triangle_axis="y", pin1_triangle_size="large", pin1_triangle_anchor_mm=0.75,
        courtyard_margin_x=0.25, courtyard_margin_y=0.25, courtyard_body_size=7.0,
    )

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"

    # Extension axis (Y): apex = pad1's own top edge (-2.8 - 0.25 = -3.05)
    # minus courtyard_margin_y (0.25) minus the fixed 0.01mm silk offset
    # = -3.31; base = apex - 0.47 (the "large" depth) = -3.78.
    # Perpendicular axis (X): body-anchored, NOT pad1-relative -- apex.x
    # = -(courtyard_body_size/2 + anchor) = -(3.5 + 0.75) = -4.25,
    # independent of pad1.x entirely. Base spread +/-0.34 (the "large"
    # half-width) around that.
    apex = (-4.25, -3.31)
    base_a = (-4.59, -3.78)
    base_b = (-3.91, -3.78)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert points == {apex, base_a, base_b}


def test_add_outline_with_y_axis_triangle_falls_back_to_pad_relative_without_anchor():
    geometry = _qfp32_geometry()
    _add_outline(
        geometry, body_size=7.22, pin1_marker_style="triangle",
        pin1_triangle_axis="y", pin1_triangle_size="large",
        courtyard_margin_x=0.25, courtyard_margin_y=0.25,
    )

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    # No pin1_triangle_anchor_mm -- perpendicular axis (X) falls back to
    # pad1's own x (-4.175) directly, not body-anchored.
    apex = (-4.175, -3.31)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert apex in points


def test_add_outline_triangle_axis_none_still_infers_from_pad_shape():
    # Regression guard: pin1_triangle_axis's default (None) must keep
    # reproducing today's QFN behavior exactly -- shape-inferred axis
    # ("x", since this fixture's pad 1 is wider than tall), "small" size,
    # pad-relative perpendicular position. Byte-identical to the
    # existing test_add_outline_with_triangle_style_draws_pin1_triangle.
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22, pin1_marker_style="triangle")

    marker = geometry.polys[0]
    apex = (-5.435, -2.8)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert apex in points
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k "y_axis_triangle or axis_none_still" -v`
Expected: the first two FAIL with `TypeError: _add_outline() got an unexpected keyword argument 'pin1_triangle_axis'`; the third PASSES already (it only exercises the existing default path, added here purely as a regression guard before the refactor).

- [ ] **Step 3: Generalize the triangle branch**

In `kicad_fpdb/pipeline.py`, add the new constant right after `PIN1_TRIANGLE_SILK_OFFSET_MM` (around line 57):

```python
# A second, larger real marker size -- SOIC's wide width class and
# every LQFP variant use this pair instead of the "small" one above,
# verified exact (zero error) against every real sample checked. See
# docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-triangle-marker-
# design.md.
PIN1_TRIANGLE_DEPTH_LARGE_MM = 0.47
PIN1_TRIANGLE_HALF_HEIGHT_LARGE_MM = 0.34
```

Change the `_add_outline` signature (around line 133-136) to add the three new parameters, right after `pin1_marker_style: str = "circle",`:

```python
                  pin1_marker_style: str = "circle",
                  pin1_triangle_axis: str | None = None, pin1_triangle_size: str = "small",
                  pin1_triangle_anchor_mm: float | None = None,
```

Replace the triangle branch (lines 433-461, i.e. the `if pin1_marker and pad1 is not None and pin1_marker_style == "triangle":` block, up to but not including the following `elif pin1_marker and pad1 is not None:` circle branch) with:

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None and pin1_marker_style == "triangle":
        # A filled triangle pointing outward from pad 1. Real KiCad's own
        # per-family generator scripts each choose which axis the marker
        # extends along independently -- not inferrable from pad shape
        # alone (SOIC/LQFP's pad 1 is wide-in-X, same as QFN's, but their
        # real marker extends in Y, not X) -- so pin1_triangle_axis makes
        # that choice explicit, defaulting to the old shape-based
        # inference (pw > ph -> "x") so QFN's yaml needs no change. See
        # docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-
        # design.md (axis="x", the original QFN case) and
        # docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-triangle-
        # marker-design.md (axis="y", added for SOIC/LQFP).
        pw, ph = pad1.size
        px, py = pad1.at
        mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
        my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
        offset = PIN1_TRIANGLE_SILK_OFFSET_MM
        depth, half_span = (
            (PIN1_TRIANGLE_DEPTH_LARGE_MM, PIN1_TRIANGLE_HALF_HEIGHT_LARGE_MM)
            if pin1_triangle_size == "large"
            else (PIN1_TRIANGLE_DEPTH_MM, PIN1_TRIANGLE_HALF_HEIGHT_MM)
        )
        axis = pin1_triangle_axis if pin1_triangle_axis is not None else ("x" if pw > ph else "y")
        if axis == "x":
            direction = -1.0 if px < 0 else 1.0
            apex_x = px + direction * (pw / 2 + mx + offset)
            base_x = apex_x + direction * depth
            points = [(apex_x, py), (base_x, py - half_span), (base_x, py + half_span)]
        else:
            direction = -1.0 if py < 0 else 1.0
            apex_y = py + direction * (ph / 2 + my + offset)
            base_y = apex_y + direction * depth
            if pin1_triangle_anchor_mm is not None:
                # Body-anchored, not pad-relative: real KiCad's own LQFP/
                # SOIC marker sits a fixed distance from the true body
                # edge regardless of where pad 1's own lead happens to
                # extend to -- verified exact (zero error) against every
                # real LQFP/SOIC sample once pad_lead_extension's effect
                # on pad 1's own position was correctly excluded. See
                # docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-
                # triangle-marker-design.md.
                body_half = (
                    courtyard_body_width / 2 if courtyard_body_width is not None else courtyard_body_size / 2
                )
                min_px, max_px = _pad_center_extent(geometry.pads, 0)
                center_x = (min_px + max_px) / 2
                perp_dir = -1.0 if px < center_x else 1.0
                apex_x = center_x + perp_dir * (body_half + pin1_triangle_anchor_mm)
            else:
                apex_x = px
            points = [(apex_x, apex_y), (apex_x - half_span, base_y), (apex_x + half_span, base_y)]
        geometry.polys.append(Poly(points=points, layer="F.SilkS"))
```

(The pre-existing `elif pin1_marker and pad1 is not None:` circle branch immediately below stays untouched.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k "y_axis_triangle or axis_none_still" -v`
Expected: all 3 PASS.

- [ ] **Step 5: Run the full unit test suite to confirm no regression**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS, including every pre-existing QFN triangle test (`test_add_outline_with_triangle_style_draws_pin1_triangle`, `test_add_outline_pin1_marker_false_suppresses_triangle_too`, `test_generate_footprint_qfn12_has_triangle_pin1_marker`, `test_generate_footprint_does_not_leak_pin1_marker_style_to_generator`) unchanged.

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "Generalize the pin-1 triangle marker with explicit axis/size/anchor params

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Wire the new params through, opt SOIC/LQFP in, and fix the regression suite's triangle check

**Files:**
- Modify: `kicad_fpdb/pipeline.py:617-681` (`generate_footprint`), `data/kicad-fpdb.yaml:227-248` (`SOIC` root), `data/kicad-fpdb.yaml:353-361` (`LQFP` root), `kicad_fpdb/footprint_diff.py`
- Test: `tests/test_pipeline_outline.py`, `tests/test_pipeline_regression.py` (via the shared `diff_footprint`)

**Interfaces:**
- Consumes: `_add_outline(..., pin1_triangle_axis=..., pin1_triangle_size=..., pin1_triangle_anchor_mm=...)` from Task 1.
- Produces: `generate_footprint` now pops `pin1_triangle_axis`/`pin1_triangle_size`/`pin1_triangle_anchor_mm` from the resolved yaml params and passes them through; SOIC and LQFP's real footprints now generate with a triangle marker matching real KiCad; `kicad_fpdb.footprint_diff.diff_footprint`'s triangle check now actually executes (previously dead code, see below) and covers QFN, SOIC, and LQFP with a small numeric tolerance instead of exact-match comparison.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`, near the existing `test_generate_footprint_qfn12_has_triangle_pin1_marker` / `test_generate_footprint_does_not_leak_pin1_marker_style_to_generator`:

```python
def test_generate_footprint_soic8_has_triangle_pin1_marker():
    fp = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="TEST")
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        fp, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_lqfp32_has_triangle_pin1_marker():
    fp = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="TEST")
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        fp, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_does_not_leak_pin1_triangle_params_to_generator():
    # If pipeline.py forgot to pop pin1_triangle_axis/_size/_anchor_mm
    # before calling the generator, this raises TypeError for an
    # unexpected kwarg -- this just has to not raise.
    generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="TEST")
    generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="TEST")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k "soic8_has_triangle or lqfp32_has_triangle" -v`
Expected: both FAIL — SOIC-8/LQFP-32 still draw a circle marker (0 silk triangles found), since the yaml doesn't opt in yet and `generate_footprint` doesn't pass the new params through yet.

- [ ] **Step 3: Wire the params through `generate_footprint` and update the yaml**

In `kicad_fpdb/pipeline.py`, add three new pops right after the existing `pin1_marker_style = params.pop("pin1_marker_style", "circle")` line (around line 627):

```python
    pin1_marker_style = params.pop("pin1_marker_style", "circle")
    pin1_triangle_axis = params.pop("pin1_triangle_axis", None)
    pin1_triangle_size = params.pop("pin1_triangle_size", "small")
    pin1_triangle_anchor_mm = params.pop("pin1_triangle_anchor_mm", None)
```

Add the three to the `_add_outline(...)` call (around line 675-676), right after `pin1_marker=pin1_marker, pin1_marker_style=pin1_marker_style,`:

```python
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, pin1_marker_style=pin1_marker_style,
                 pin1_triangle_axis=pin1_triangle_axis, pin1_triangle_size=pin1_triangle_size,
                 pin1_triangle_anchor_mm=pin1_triangle_anchor_mm,
                 silk_y=silk_y, silk_half_length=silk_half_length,
```

In `data/kicad-fpdb.yaml`, add to the `SOIC` root's `params` block (around line 227-248), alongside the existing `courtyard_body_width`/`courtyard_body_margin` dicts:

```yaml
    pin1_marker_style: triangle
    pin1_triangle_axis: y
    pin1_triangle_size: {narrow: small, wide: large}
    pin1_triangle_anchor_mm: {narrow: 0.65, wide: 0.90}
```

And to the `LQFP` root's `params` block (around line 353-361):

```yaml
    pin1_marker_style: triangle
    pin1_triangle_axis: y
    pin1_triangle_size: large
    pin1_triangle_anchor_mm: 0.75
```

`QFN`'s root is **not** touched — all three new params default to values reproducing its exact existing geometry.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k "soic8_has_triangle or lqfp32_has_triangle or does_not_leak_pin1_triangle" -v`
Expected: all 3 PASS.

- [ ] **Step 5: Fix and extend the regression suite's triangle check**

`kicad_fpdb/footprint_diff.py` currently has a bug: `if descriptor.split()[0] == "QFN":` is always `False` for every real descriptor (e.g. `"QFN-12".split()[0]` is `"QFN-12"`, never `"QFN"`) — the triangle-marker check has never actually executed. Fix this as part of extending it to SOIC/LQFP.

Add `import math` at the top of `kicad_fpdb/footprint_diff.py`, alongside the existing `import re`.

Add two new module-level constants near the existing `TRIANGLE_ROUND_DP` (which this step removes, replaced by a numeric tolerance instead — exact rounded-set comparison can't absorb LQFP's known ≤0.01mm residual without also hiding a much larger, real bug):

```python
# Families whose real reference footprints carry a pin-1 triangle
# marker on F.SilkS (matched via pin1_marker_style="triangle") --
# checked against the descriptor's own family head (e.g. "QFN-12" ->
# "QFN"). SOT-23/TSOT-23 also have real triangle markers but are
# deliberately not included yet -- their geometry doesn't fit either
# formula this project implements; see docs/superpowers/specs/
# 2026-09-17-soic-lqfp-pin1-triangle-marker-design.md's Non-goals.
TRIANGLE_MARKER_FAMILIES = {"QFN", "SOIC", "LQFP"}
# Max allowed distance, in mm, between a real triangle point and its
# closest generated counterpart. Needs to be looser than a simple
# rounded-value comparison: LQFP's real files have an unavoidable
# ~0.01mm generator-rounding residual on some variants (verified exact
# match on the other variants) -- 0.015mm absorbs that while staying
# far tighter than any plausible real geometry bug (marker dimensions
# are 0.24-0.47mm at this scale).
TRIANGLE_POINT_TOLERANCE_MM = 0.015
```

Remove the old `TRIANGLE_ROUND_DP = 2` constant (superseded by `TRIANGLE_POINT_TOLERANCE_MM`).

Add a new helper function near `_diff_rratio`:

```python
def _triangle_points_match(
    real_points: list[tuple[float, float]], gen_points: list[tuple[float, float]],
    tolerance: float = TRIANGLE_POINT_TOLERANCE_MM,
) -> bool:
    if len(real_points) != len(gen_points):
        return False
    remaining = list(gen_points)
    for rp in real_points:
        if not remaining:
            return False
        closest = min(remaining, key=lambda gp: math.hypot(gp[0] - rp[0], gp[1] - rp[1]))
        if math.hypot(closest[0] - rp[0], closest[1] - rp[1]) > tolerance:
            return False
        remaining.remove(closest)
    return True
```

Replace the existing triangle-check block at the end of `diff_footprint` (currently `if descriptor.split()[0] == "QFN":` through the end of the function) with:

```python
    family = descriptor.split()[0].split("-")[0]
    if family in TRIANGLE_MARKER_FAMILIES:
        real_triangle = parse_silk_triangle(real_text)
        generated_triangle = parse_silk_triangle(generated)
        if real_triangle is None:
            diffs.append(f"real file has no pin-1 triangle marker (unexpected for {family})")
        elif generated_triangle is None:
            diffs.append("missing pin-1 triangle marker")
        elif not _triangle_points_match(real_triangle, generated_triangle):
            diffs.append(f"pin-1 triangle points: generated={generated_triangle} real={real_triangle}")

    return diffs
```

Update the module docstring's tolerance list at the top of the file (the bullet currently describing `TRIANGLE_ROUND_DP`-based comparison) to instead describe the new tolerance-based comparison and note which families it covers.

- [ ] **Step 6: Run the full unit test suite**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS.

- [ ] **Step 7: Run the full suite, including the regression suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`). This is the first time the triangle check has ever actually run for QFN (previously dead code) — if any QFN case unexpectedly fails here, stop and investigate before continuing; it would mean either the bug-fixed check or the original QFN geometry has a real, previously-hidden discrepancy. Every SOIC and LQFP case now also gets checked for the first time.

- [ ] **Step 8: Run `verify_library` for a full report**

Run: `python3 -m kicad_fpdb.verify_library --family SOIC LQFP QFN`
Expected: `<N>/<N> cases match exactly.` If any case has a diff, read the printed detail (exact generated vs. real values) before deciding whether it's a genuine geometry bug or a formula/constant that needs adjusting — do not loosen `TRIANGLE_POINT_TOLERANCE_MM` further without first understanding why.

- [ ] **Step 9: Visual review**

Run: `python -m kicad_fpdb.render_png --family SOIC LQFP --output-dir renders_png`

Open a narrow SOIC (`renders_png/SOIC-8.png`), a wide SOIC (`renders_png/SOIC-14_w.png` or similar), and a small/large LQFP pair, and confirm the generated (left) panel's pin-1 marker is now a triangle near the top-left corner, visually matching the reference (right) panel's position and size.

- [ ] **Step 10: Commit**

```bash
git add kicad_fpdb/pipeline.py data/kicad-fpdb.yaml kicad_fpdb/footprint_diff.py tests/test_pipeline_outline.py
git commit -m "Opt SOIC/LQFP into the triangle marker; fix and extend the regression suite's triangle check

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
* Extended the pin-1 triangle marker (`pin1_marker_style: triangle`,
  originally QFN-only) to SOIC and LQFP. Real KiCad's per-family
  scripts each choose the marker's extension axis independently — QFN
  extends along the same axis pad 1's lead points on (X), but SOIC and
  LQFP extend perpendicular to it (Y) despite pad 1 having the same
  wide-in-X shape in both cases — so `pin1_triangle_axis` makes that
  choice explicit (`None` keeps QFN's old shape-inferred behavior,
  zero yaml change needed there). There are also two real marker
  sizes, not one: the existing `depth=0.33mm`/`half-width=0.24mm`
  (`pin1_triangle_size: small`, QFN and SOIC's narrow class) and a
  second `depth=0.47mm`/`half-width=0.34mm` pair (`"large"`, SOIC's
  wide class and every LQFP variant regardless of body size).
  SOIC/LQFP's perpendicular-axis position turned out to be anchored to
  the true body edge, not to pad 1 — `apex = -(true_body_half_width +
  constant)` — verified **exact, zero error** against every real
  sample once `pad_lead_extension`'s effect on pad 1's own position
  (which had made it look approximately, not exactly, pad-relative)
  was correctly excluded; constants are `0.75mm` (LQFP), `0.65mm`
  (SOIC narrow), `0.90mm` (SOIC wide) — a new `pin1_triangle_anchor_mm`
  param drives this, unused (`None`) for QFN. The extension-axis
  formula itself is unchanged from QFN's (`pad-edge - margin - 0.01mm`)
  and holds almost exactly — 4 of LQFP's 8 variants match to the last
  digit, the rest are off by exactly `0.01mm` in a way that didn't
  resolve to a cleaner alternate constant, accepted as generator
  rounding noise (same category already accepted for LQFP's corner
  marks and SOIC's body-width formula). See docs/superpowers/specs/
  2026-09-17-soic-lqfp-pin1-triangle-marker-design.md.
* Fixed a real, previously-dead check while extending the above: the
  regression suite's (`kicad_fpdb.footprint_diff.diff_footprint`)
  pin-1-triangle comparison used `descriptor.split()[0] == "QFN"`,
  which is always `False` for every actual descriptor (e.g.
  `"QFN-12".split()[0]` is `"QFN-12"`, never `"QFN"`) — this check had
  never actually executed since it was added. Fixed to
  `descriptor.split()[0].split("-")[0]` (matching the family-head
  extraction already used elsewhere, e.g. `render_png.py`) and
  extended to cover SOIC/LQFP too (`TRIANGLE_MARKER_FAMILIES`). Also
  replaced the old rounded-set-equality comparison with a numeric
  per-point distance tolerance (`TRIANGLE_POINT_TOLERANCE_MM =
  0.015mm`), needed to absorb LQFP's known ≤0.01mm residual without
  loosening things enough to hide a real bug.
```

Update the existing TODO entry (added during the QFN triangle work) that reads roughly "Extend the `pin1_marker_style: triangle` convention... to SOIC, SOT-23, and LQFP" — narrow it to just SOT-23 now that SOIC/LQFP are done:

```markdown
* Extend the `pin1_marker_style: triangle` convention to SOT-23 (and
  TSOT-23) — its real triangle geometry doesn't fit either the QFN
  (axis="x") or SOIC/LQFP (axis="y", body-anchored) formula and needs
  its own investigation. Also raises a separate question: real
  SOT-23/SOT-23-5 reference files have a triangle marker even though
  this project currently sets `pin1_marker: false` for both (reasoned
  as "asymmetric layout, only placeable one way" — a functional
  argument unrelated to whether real KiCad draws a marker there) —
  needs its own decision before implementing.
```

- [ ] **Step 2: Add a CHANGELOG.md entry**

Check the most recent entry's date/version at the top of `CHANGELOG.md`. If it's already dated today, fold this into that existing entry (per this project's own changelog convention); otherwise add a new dated entry above it.

```markdown
* Extended the pin-1 triangle marker to SOIC and LQFP (previously
  QFN-only), with a body-anchored position formula verified exact
  against every real sample. Fixed a pre-existing dead check in the
  regression suite's triangle comparison along the way (family-head
  string comparison never matched any real descriptor). See
  docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-triangle-marker-
  design.md.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the SOIC/LQFP triangle marker extension in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
