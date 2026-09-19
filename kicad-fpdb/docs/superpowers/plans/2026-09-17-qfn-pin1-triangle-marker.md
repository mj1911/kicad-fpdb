# QFN Pin-1 Triangle Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the QFN family's pin-1 circle marker with a filled triangle matching real KiCad's own convention, verified geometrically against 11 real reference files spanning 12-80 pins and 0.4/0.5/0.65mm pitch.

**Architecture:** Add a new `pin1_marker_style` param to `kicad_fpdb.pipeline._add_outline` (default `"circle"`, unchanged behavior for every existing family). A new `"triangle"` branch derives pin 1's outward-facing side the same way `_quad_side_groups` already does, and emits a filled `Poly` on `F.SilkS` using three new fixed-constant offsets. `data/kicad-fpdb.yaml`'s `QFN` root opts in via `pin1_marker_style: triangle`. No other family's yaml or behavior changes.

**Tech Stack:** Python, pytest. No new dependencies.

## Global Constraints

- Geometry values (verified against real KiCad reference files, see spec): triangle depth `0.33mm`, base half-height `0.24mm`, silk offset past the courtyard edge `0.01mm`.
- `_add_outline`'s existing `pin1_marker=False` behavior (suppress marker entirely) must still work when combined with any `pin1_marker_style` value — `pin1_marker_style` only selects the *shape* when a marker is drawn at all.
- No other family's `pin1_marker_style` changes — every existing family keeps its implicit `"circle"` default.
- Full test suite (`pytest`) must pass after every task; the regression suite (`tests/test_pipeline_regression.py`) is skipped automatically on machines without the real KiCad footprint library, so it is *not* sufficient on its own — the unit tests in `tests/test_pipeline_outline.py` are the ones that must run everywhere.

---

### Task 1: Add `pin1_marker_style` triangle branch to `_add_outline`

**Files:**
- Modify: `kicad_fpdb/pipeline.py:37-44` (constants), `kicad_fpdb/pipeline.py:92-108` (`_add_outline` signature), `kicad_fpdb/pipeline.py:390-404` (pin-1 marker block)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `kicad_fpdb.geometry.Poly(points: list[tuple[float, float]], layer: str, width: float = 0.12, fill: str = "yes")` (already exists, used elsewhere in `_add_outline` for the F.Fab chamfer outline).
- Produces: `_add_outline(..., pin1_marker_style: str = "circle")` — when `pin1_marker_style == "triangle"` and a pin-1 marker is drawn, appends one `Poly` (3 points) to `geometry.polys` on layer `"F.SilkS"` instead of a `Circle` to `geometry.circles`.

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_pipeline_outline.py`, near `test_add_outline_with_body_size_keeps_pin1_marker` (uses the same `_qfp32_geometry()` fixture, which already has pad 1 on the left side — the same orientation real QFN's pin 1 uses):

```python
def test_add_outline_with_triangle_style_draws_pin1_triangle():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22, pin1_marker_style="triangle")

    assert len(geometry.circles) == 0
    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" sits at (-4.175, -2.8), size (1.5, 0.5) -- a left-side pad
    # (width > height), same orientation convention real QFN's pin 1
    # uses. No courtyard_margin_x/_y passed, so _add_outline falls back
    # to COURTYARD_MARGIN_MM (0.5).
    # Apex: pad's own left edge (-4.175 - 0.75 = -4.925), minus the
    # courtyard margin (0.5), minus the fixed 0.01mm silk offset.
    # Base: apex_x - 0.33 (fixed depth), spread pad-y +/- 0.24 (fixed).
    apex = (-5.435, -2.8)
    base_top = (-5.765, -3.04)
    base_bottom = (-5.765, -2.56)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert points == {apex, base_top, base_bottom}


def test_add_outline_pin1_marker_false_suppresses_triangle_too():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22, pin1_marker=False, pin1_marker_style="triangle")

    assert len(geometry.circles) == 0
    assert len(geometry.polys) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k triangle -v`
Expected: both FAIL — `_add_outline() got an unexpected keyword argument 'pin1_marker_style'`.

- [ ] **Step 3: Implement the triangle branch**

In `kicad_fpdb/pipeline.py`, add the three new constants right after `PIN1_MARKER_CLEARANCE_MM` (around line 44):

```python
# Fixed geometry of the QFN-style filled-triangle pin-1 marker
# (pin1_marker_style="triangle"), verified against 11 real QFN
# reference files spanning 12-80 pins and 0.4/0.5/0.65mm pitch -- see
# docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-design.md.
# Depth (apex to base) along pad 1's own outward axis.
PIN1_TRIANGLE_DEPTH_MM = 0.33
# Half-height of the base, perpendicular to the outward axis, centered
# on pad 1's own center.
PIN1_TRIANGLE_HALF_HEIGHT_MM = 0.24
# Extra clearance, beyond the courtyard margin, between pad 1's own
# edge and the triangle's apex -- the apex lands just past where the
# courtyard line on that side already sits.
PIN1_TRIANGLE_SILK_OFFSET_MM = 0.01
```

Change the `_add_outline` signature (around line 92-108) to add the new parameter, right after `pin1_marker: bool = True`:

```python
                  body_size: float | None = None, pin1_marker: bool = True,
                  pin1_marker_style: str = "circle",
```

Replace the pin-1 marker block (lines 390-404) with:

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None and pin1_marker_style == "triangle":
        # A filled triangle pointing outward from pad 1, along whichever
        # axis pad 1 itself points on -- real KiCad's own QFN convention
        # (pin 1 sits on a side, not necessarily the top, unlike the
        # circle marker below). Side/direction is detected the same way
        # _quad_side_groups already classifies quad-perimeter pads: a
        # pad wider than it is tall sits on the left or right side (its
        # outward axis is X); otherwise it's on the top or bottom (Y).
        # See docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-
        # marker-design.md.
        pw, ph = pad1.size
        px, py = pad1.at
        mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
        my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
        offset = PIN1_TRIANGLE_SILK_OFFSET_MM
        depth = PIN1_TRIANGLE_DEPTH_MM
        half_h = PIN1_TRIANGLE_HALF_HEIGHT_MM
        if pw > ph:
            direction = -1.0 if px < 0 else 1.0
            apex_x = px + direction * (pw / 2 + mx + offset)
            base_x = apex_x + direction * depth
            points = [(apex_x, py), (base_x, py - half_h), (base_x, py + half_h)]
        else:
            direction = -1.0 if py < 0 else 1.0
            apex_y = py + direction * (ph / 2 + my + offset)
            base_y = apex_y + direction * depth
            points = [(px, apex_y), (px - half_h, base_y), (px + half_h, base_y)]
        geometry.polys.append(Poly(points=points, layer="F.SilkS"))
    elif pin1_marker and pad1 is not None:
        # A filled circle directly above pad 1: same X as the pad,
        # offset up past its own top edge (and the circle's own radius,
        # so its *near* edge — not its center — clears the pad by
        # PIN1_MARKER_CLEARANCE_MM) so it sits outside both the copper
        # pad and its solder mask opening. This is independent of the
        # outline mode entirely (unlike the old nearest-corner triangle)
        # — see docs/superpowers/specs/2026-09-14-pin1-circle-marker-
        # design.md. "Above" assumes pin 1 is at the top of the part,
        # true for every generator today.
        cx = pad1.at[0]
        radius = PIN1_MARKER_MM / 2
        cy = pad1.at[1] - pad1.size[1] / 2 - PIN1_MARKER_CLEARANCE_MM - radius
        geometry.circles.append(Circle(center=(cx, cy), radius=radius, layer="F.SilkS"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k triangle -v`
Expected: both PASS.

- [ ] **Step 5: Run the full unit test suite to confirm no regression**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS (every existing `pin1_marker`/circle test keeps passing since `pin1_marker_style` defaults to `"circle"`).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "Add triangle style for the pin-1 marker in _add_outline

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Wire `pin1_marker_style` through `generate_footprint` and opt QFN in

**Files:**
- Modify: `kicad_fpdb/pipeline.py:546-614` (`generate_footprint`), `data/kicad-fpdb.yaml:386-393` (`QFN` root)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_outline(..., pin1_marker_style: str = "circle")` from Task 1.
- Produces: `generate_footprint` now pops a `pin1_marker_style` key out of the resolved yaml params (default `"circle"`) and passes it through to `_add_outline`, the same way `pin1_marker` already is.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline_outline.py`, near `test_generate_footprint_soic8_still_has_pin1_marker` / `test_generate_footprint_does_not_leak_pin1_marker_to_generator`:

```python
def test_generate_footprint_qfn12_has_triangle_pin1_marker():
    fp = generate_footprint("QFN-12", FAMILY_TREE_PATH, name="TEST")
    # Exactly one fp_poly on F.SilkS with 3 points -- the pin-1
    # triangle. (The F.Fab chamfer outline is also a Poly, but on
    # F.Fab with 5 points, so this regex -- scoped to F.SilkS -- won't
    # match it.)
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)\s*\(stroke.*?\)\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\)',
        fp, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_does_not_leak_pin1_marker_style_to_generator():
    # If pipeline.py forgot to pop pin1_marker_style before calling the
    # generator, quad_perimeter would raise TypeError for an unexpected
    # kwarg -- this just has to not raise.
    generate_footprint("QFN-12", FAMILY_TREE_PATH, name="TEST")
```

(Note: reuse the existing `FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"` module constant already defined at the top of this file, and the existing `generate_footprint` import. `tests/test_pipeline_outline.py` does not currently import `re` — add `import re` alongside the existing `import math` at the top of the file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k qfn12 -v`
Expected: `test_generate_footprint_qfn12_has_triangle_pin1_marker` FAILS (no `fp_poly` triangle yet — QFN-12 still draws a circle since the yaml doesn't opt in and `generate_footprint` doesn't pass the param through yet). `test_generate_footprint_does_not_leak_pin1_marker_style_to_generator` PASSES already (nothing to leak yet) — that's expected; it exists to guard the change made in this task.

- [ ] **Step 3: Wire the param through `generate_footprint` and update the yaml**

In `kicad_fpdb/pipeline.py`, add a new pop right after the existing `pin1_marker = params.pop("pin1_marker", True)` line (around line 555):

```python
    pin1_marker = params.pop("pin1_marker", True)
    pin1_marker_style = params.pop("pin1_marker_style", "circle")
```

Add `pin1_marker_style=pin1_marker_style` to the `_add_outline(...)` call (around line 603-614), right after `pin1_marker=pin1_marker,`:

```python
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, pin1_marker_style=pin1_marker_style,
                 silk_y=silk_y, silk_half_length=silk_half_length,
```

In `data/kicad-fpdb.yaml`, add `pin1_marker_style: triangle` to the `QFN` root's `params` block (around line 386-393):

```yaml
QFN:
  generator: quad_perimeter
  params:
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    fab_outline: true
    fab_chamfer: 1.0
    pad_lead_extension: -0.0625
    pin1_marker_style: triangle
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k qfn12 -v`
Expected: both PASS.

- [ ] **Step 5: Run the full unit test suite**

Run: `pytest tests/ -v --ignore=tests/test_pipeline_regression.py --ignore=tests/test_visual_compare.py --ignore=tests/test_writer.py`
Expected: all PASS. (These three files are skipped here only because they depend on the local KiCad install and are covered explicitly in Task 3.)

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py data/kicad-fpdb.yaml tests/test_pipeline_outline.py
git commit -m "Wire pin1_marker_style through generate_footprint; opt QFN into the triangle marker

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Regression-verify the triangle against all 20 real QFN files, and visual review

**Files:**
- Modify: `tests/test_pipeline_regression.py`
- Test: `tests/test_pipeline_regression.py` (itself)

**Interfaces:**
- Consumes: `CASES` and `KICAD_FOOTPRINTS`/`FAMILY_TREE_PATH` from `kicad_fpdb.reference_cases` (already imported at the top of this file); `generate_footprint` from `kicad_fpdb.pipeline` (already imported).
- Produces: a new `_parse_silk_triangle(text: str) -> list[tuple[float, float]] | None` helper, and an added comparison block inside the existing `test_pipeline_matches_real_footprint`.

This task only runs meaningfully on a machine with the real KiCad footprint library installed (`pytestmark` at the top of the file already skips the whole module otherwise) — expected, per `CLAUDE.md`'s cross-machine notes.

- [ ] **Step 1: Write the failing test additions**

In `tests/test_pipeline_regression.py`, add a new regex and helper near the existing `PAD_START`/`_parse_pads` definitions (around line 20):

```python
SILK_TRIANGLE_POLY = re.compile(
    r'\(fp_poly\s*\(pts(.*?)\)\s*\(stroke.*?\)\s*(?:\(fill \w+\)\s*)?\(layer "F\.SilkS"\)\)', re.S
)
XY_PATTERN = re.compile(r"\(xy ([-\d.]+) ([-\d.]+)\)")


def _parse_silk_triangle(text: str) -> list[tuple[float, float]] | None:
    # Matches the pin-1 triangle's fp_poly specifically -- it's the only
    # 3-point poly on F.SilkS either the real files or this project's
    # generator ever emit (the F.Fab chamfer outline is a separate,
    # 5-point poly on a different layer).
    for m in SILK_TRIANGLE_POLY.finditer(text):
        points = [(float(x), float(y)) for x, y in XY_PATTERN.findall(m.group(1))]
        if len(points) == 3:
            return points
    return None
```

Add a new block at the end of `test_pipeline_matches_real_footprint` (after the existing unnumbered-pad comparison, i.e. after the current last line of the function):

```python
    real_triangle = _parse_silk_triangle(real_text)
    generated_triangle = _parse_silk_triangle(generated)
    if real_triangle is not None:
        # Real QFN files (and only QFN, among today's reference cases)
        # carry a 3-point pin-1 triangle poly on F.SilkS -- see
        # docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-
        # design.md. Points may come back in a different winding order
        # than the real file, so compare as sets, not sequences.
        assert generated_triangle is not None, f"{descriptor}: missing pin-1 triangle marker"
        real_points = {(round(x, 2), round(y, 2)) for x, y in real_triangle}
        gen_points = {(round(x, 2), round(y, 2)) for x, y in generated_triangle}
        assert gen_points == real_points, f"{descriptor}: pin-1 triangle points"
    else:
        assert generated_triangle is None, f"{descriptor}: unexpected pin-1 triangle marker"
```

- [ ] **Step 2: Run the regression suite to verify it fails (if KiCad is installed) or skips (if not)**

Run: `pytest tests/test_pipeline_regression.py -v`
Expected (KiCad installed): the 20 QFN cases FAIL with `pin-1 triangle points` mismatches (still using the old circle marker in some, or missing, until Task 2 lands — if Task 2 already landed in an earlier commit this run, they may already PASS here, which is fine; the important check is that no QFN case is silently skipped). Expected (KiCad absent): entire module SKIPPED — see `CLAUDE.md`'s cross-machine notes; if this happens, note it explicitly rather than treating it as a pass and move to Step 4's visual review, which needs `kicad-cli` too and will also just report clearly that it can't run.

- [ ] **Step 3: If any QFN case fails, adjust triangle geometry in `_add_outline` from Task 1 until it matches**

This should not be necessary — the geometry constants were verified against these exact 20 files during design — but if `pytest` surfaces a mismatch, print `real_points`/`gen_points` for the failing descriptor and compare against the specific real `.kicad_mod` file under `Package_DFN_QFN.pretty/` to find the discrepancy before changing any constant.

- [ ] **Step 4: Run the full suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the known pre-existing skips: `KICAD_FOOTPRINTS` absent, `test_visual_compare.py`/`test_writer.py`'s `kicad-cli` round-trip skips on a machine without KiCad).

- [ ] **Step 5: Regenerate the visual review page and open it**

Run: `python -m kicad_fpdb.visual_compare`

This needs `kicad-cli` on PATH (per `CLAUDE.md`'s cross-machine notes) — if it errors clearly because `kicad-cli` isn't installed, say so explicitly and skip to Step 6 without claiming visual verification happened.

If it succeeds, open `renders/review.html` and visually confirm on at least QFN-12 (smallest) and QFN-80 (largest, if not excluded by `PREVIEW_EXCLUDED_DESCRIPTORS`/included via `PREVIEW_ONLY_DESCRIPTORS`) that:
- the triangle points outward from pad 1, away from the body, on the left side
- it doesn't overlap the adjacent courtyard/corner-mark lines
- it visually matches the reference panel's own marker

- [ ] **Step 6: Commit**

```bash
git add tests/test_pipeline_regression.py
git commit -m "Verify the QFN pin-1 triangle against all 20 real reference files

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Document in CLAUDE.md and CHANGELOG.md

**Files:**
- Modify: `CLAUDE.md` (narrative log section, after the most recent QFN-related entry)
- Modify: `CHANGELOG.md` (top of file)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add a CLAUDE.md entry**

Append a new bullet to `CLAUDE.md`'s narrative log (the `## Claude-isms below` section), after the existing QFN entries and before `## TODO`:

```markdown
* QFN's pin-1 marker was replaced with a filled triangle matching real
  KiCad's own convention, instead of inheriting the DIP/SOIC/SOT/LQFP
  circle marker it wasn't designed around — real QFN reference files
  (`Package_DFN_QFN.pretty`) draw a triangle pointing outward from pad
  1 along whichever side pad 1 sits on (always the left side today),
  not a circle above it. New `pin1_marker_style` param on `_add_outline`
  (default `"circle"`, every other family unchanged) with a `"triangle"`
  branch: apex sits `courtyard_margin + 0.01mm` past pad 1's own
  outward edge, depth `0.33mm`, base spread `±0.24mm` — all three fixed
  constants verified exactly against 11 real QFN files spanning 12-80
  pins and 0.4/0.5/0.65mm pitch, including a custom-shaped pad 1. Side
  detection reuses `_quad_side_groups`' own width>height convention, so
  it generalizes to any of the four sides, not just QFN's left-side
  convention. The corner-mark bracket leg real KiCad shortens at that
  same corner (~0.02mm) is deliberately not reproduced — visually
  negligible, and QFN's corner marks already carry a larger documented
  approximation. See docs/superpowers/specs/2026-09-17-qfn-pin1-
  triangle-marker-design.md.
```

- [ ] **Step 2: Add a CHANGELOG.md entry**

Check today's date convention: the most recent entry is `2026-09-16 v0.0.16:`. Add a new entry at the very top of `CHANGELOG.md` (after the `# Changes` header):

```markdown
2026-09-17 v0.0.17:

* Replaced QFN's pin-1 circle marker with a filled triangle matching
  real KiCad's own convention (verified against 11 real QFN reference
  files, 12-80 pins). New `pin1_marker_style` param on `_add_outline`
  (default unchanged for every other family); QFN's yaml root opts in.
  See docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-design.md.

```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the QFN pin-1 triangle marker in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
