# Pin-1 Circle Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pin-1 triangle marker (anchored to the F.SilkS outline's nearest corner) with a filled circle anchored purely to pad 1's own position, directly above it.

**Architecture:** A new `Circle` geometry primitive (`kicad_fpdb/geometry.py`) and writer support (`kicad_fpdb/writer.py`) mirror the existing `Line`/`Rect`/`Poly` pattern. `_add_outline()` in `kicad_fpdb/pipeline.py` replaces its triangle-`Poly`-via-`_nearest_corner` marker block with a circle computed only from pad 1's `at`/`size` — no outline-mode variables involved at all. `_nearest_corner` becomes dead code and is removed.

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q`.

## Global Constraints

- The marker's visual scale stays the same: `PIN1_MARKER_MM` (0.6) is repurposed as the circle's diameter (radius 0.3) rather than the triangle's base/height.
- "Above" means "more negative Y" — a deliberate, documented assumption (every current generator places pin 1 at the top). Do not attempt to generalize this to other directions in this plan; see `docs/superpowers/specs/2026-09-14-pin1-circle-marker-design.md`'s non-goals.
- `Poly`/`_write_poly` stay in the codebase — they're generic primitives, not marker-specific, even though nothing currently produces a `Poly` after this change. Do not remove them.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Add the `Circle` geometry primitive

**Files:**
- Modify: `kicad_fpdb/geometry.py` (add `Circle` dataclass, `circles` field on `FootprintGeometry`)
- Modify: `kicad_fpdb/writer.py` (add `_write_circle`, wire into `write_kicad_mod`)
- Test: `tests/test_writer.py`

**Interfaces:**
- Produces: `Circle(center: tuple[float, float], radius: float, layer: str, width: float = 0.12, fill: str = "yes")`, and `FootprintGeometry.circles: list[Circle]`. Relied on by Task 2.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_writer.py`, after `test_write_poly`:

```python
def test_write_circle():
    circle = Circle(center=(0.0, -1.0), radius=0.3, layer="F.SilkS")
    geom = FootprintGeometry(name="TEST_MIN", circles=[circle])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_circle" in text
    assert "(center 0 -1)" in text
    assert "(end 0.3 -1)" in text
    assert "(fill yes)" in text
    assert '(layer "F.SilkS")' in text
```

And update the import line at the top of the file:

```python
from kicad_fpdb.geometry import Circle, FootprintGeometry, Line, Pad, Poly, Rect, Text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_writer.py -v`
Expected: FAILS with `ImportError: cannot import name 'Circle' from 'kicad_fpdb.geometry'`.

- [ ] **Step 3: Add the `Circle` dataclass**

In `kicad_fpdb/geometry.py`, add after the `Poly` dataclass (before `FootprintGeometry`):

```python
@dataclass
class Circle:
    center: tuple[float, float]
    radius: float
    layer: str
    width: float = 0.12
    fill: str = "yes"
```

And add a `circles` field to `FootprintGeometry`:

```python
@dataclass
class FootprintGeometry:
    name: str
    pads: list[Pad] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    polys: list[Poly] = field(default_factory=list)
    circles: list[Circle] = field(default_factory=list)
```

- [ ] **Step 4: Add writer support**

In `kicad_fpdb/writer.py`, update the import line:

```python
from kicad_fpdb.geometry import Circle, FootprintGeometry, Line, Pad, Poly, Rect, Text
```

Add a loop over circles in `write_kicad_mod`, after the existing poly loop:

```python
    for poly in geometry.polys:
        lines.append(_write_poly(poly))
    for circle in geometry.circles:
        lines.append(_write_circle(circle))
    for pad in geometry.pads:
        lines.append(_write_pad(pad))
```

Add the `_write_circle` function, after `_write_poly`:

```python
def _write_circle(circle: Circle) -> str:
    cx, cy = circle.center
    ex, ey = cx + circle.radius, cy
    return (
        "  (fp_circle\n"
        f"    (center {_fmt(cx)} {_fmt(cy)})\n"
        f"    (end {_fmt(ex)} {_fmt(ey)})\n"
        "    (stroke\n"
        f"      (width {_fmt(circle.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f"    (fill {circle.fill})\n"
        f'    (layer "{circle.layer}")\n'
        "  )"
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_writer.py -v`
Expected: all tests PASS, including the new one.

- [ ] **Step 6: Extend the kicad-cli round-trip test to cover circles**

In `tests/test_writer.py`, add a circle to the geometry built in `test_generated_file_is_valid_kicad_mod` (this validates the new primitive's S-expression syntax against real `kicad-cli`, not just our own parser):

```python
    geom = FootprintGeometry(
        name="TEST_MIN", pads=[pad1, pad2],
        texts=[
            Text(kind="reference", text="REF**", at=(0.8, -1.0), layer="F.Fab"),
            Text(kind="value", text="TEST_MIN", at=(0.8, 3.5), layer="F.Fab"),
        ],
        lines=[Line(start=(-0.5, -0.5), end=(2.0, -0.5), layer="F.SilkS")],
        rects=[Rect(start=(-1.0, -1.0), end=(2.5, 3.0), layer="F.CrtYd")],
        polys=[Poly(points=[(-0.5, -0.5), (0.0, -0.5), (-0.5, 0.0)], layer="F.SilkS")],
        circles=[Circle(center=(0.0, -1.5), radius=0.3, layer="F.SilkS")],
    )
```

- [ ] **Step 7: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (88 baseline + 2 new = 90). If `test_generated_file_is_valid_kicad_mod` is skipped on this machine (no `kicad-cli` on PATH), say so in your report rather than assuming it ran.

- [ ] **Step 8: Commit**

```bash
git add kicad_fpdb/geometry.py kicad_fpdb/writer.py tests/test_writer.py
git commit -m "$(cat <<'EOF'
Add a Circle geometry primitive and fp_circle writer support

Mirrors the existing Line/Rect/Poly pattern. Needed by the upcoming
pin-1 circle marker, but generic — not marker-specific.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Replace the triangle marker with a pad-1-anchored circle

**Files:**
- Modify: `kicad_fpdb/pipeline.py` (the `_add_outline` function; remove `_nearest_corner`)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `Circle` from Task 1.
- Produces: `_add_outline`'s public signature is unchanged (still takes `pin1_marker: bool`); its behavior when `pin1_marker=True` now appends a `Circle` to `geometry.circles` instead of a `Poly` to `geometry.polys`. `generate_footprint`'s signature and the rest of `_add_outline`'s parameters (`body_width`, `body_margin`, `body_size`, `silk_y`, `silk_half_length`, `courtyard_margin_x`, `courtyard_margin_y`) are untouched.

- [ ] **Step 1: Write the failing tests**

In `tests/test_pipeline_outline.py`, replace `test_add_outline_produces_pin1_marker_triangle` (currently lines 101-126) with:

```python
def test_add_outline_produces_pin1_marker_circle():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    assert len(geometry.circles) == 1
    assert len(geometry.polys) == 0
    marker = geometry.circles[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" sits at (0, 0), size (1.6, 1.6). The marker sits directly
    # above it: same X, offset up past the pad's own top edge (half its
    # Y size) by a fixed 0.2mm clearance.
    assert marker.center == pytest.approx((0.0, -1.0))
    assert marker.radius == pytest.approx(0.3)
```

Replace `test_add_outline_pin1_marker_false_suppresses_marker` (currently checking `geometry.polys`) with:

```python
def test_add_outline_pin1_marker_false_suppresses_marker():
    geometry = _dip16_geometry()
    _add_outline(geometry, pin1_marker=False)

    assert len(geometry.circles) == 0
```

Replace `test_add_outline_with_body_size_keeps_pin1_marker` (currently lines 160-172) with:

```python
def test_add_outline_with_body_size_keeps_pin1_marker():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22)

    assert len(geometry.circles) == 1
    marker = geometry.circles[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" (quad_perimeter's left side, first pin) sits at
    # (-4.175, -2.8), size (1.5, 0.5) — the marker is independent of
    # the corner-marks outline entirely now, anchored only to pad 1.
    assert marker.center == pytest.approx((-4.175, -3.25))
    assert marker.radius == pytest.approx(0.3)
```

In `test_add_outline_with_silk_line_params_draws_two_lines`, change:

```python
    # No pin-1 marker (pin1_marker=False, matching how R/C actually
    # declare it), and only the courtyard rect — no F.SilkS rectangle.
    assert len(geometry.polys) == 0
```

to:

```python
    # No pin-1 marker (pin1_marker=False, matching how R/C actually
    # declare it), and only the courtyard rect — no F.SilkS rectangle.
    assert len(geometry.circles) == 0
```

In `test_generate_footprint_includes_outline_geometry`, change `assert "(fp_poly" in text` to `assert "(fp_circle" in text`.

In `test_generate_footprint_r0603_has_no_pin1_marker` and `test_generate_footprint_c0603_has_no_pin1_marker`, change `assert "fp_poly" not in text` to `assert "fp_circle" not in text` in both.

In `test_generate_footprint_dip16_still_has_pin1_marker`, change `assert "fp_poly" in text` to `assert "fp_circle" in text`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_add_outline_produces_pin1_marker_circle`, `test_add_outline_pin1_marker_false_suppresses_marker`, `test_add_outline_with_body_size_keeps_pin1_marker`, `test_add_outline_with_silk_line_params_draws_two_lines`, `test_generate_footprint_includes_outline_geometry`, `test_generate_footprint_r0603_has_no_pin1_marker`, `test_generate_footprint_c0603_has_no_pin1_marker`, and `test_generate_footprint_dip16_still_has_pin1_marker` all FAIL (the code still produces triangles/`Poly`, not circles). This is a larger red set than usual because one behavior change touches many existing assertions — that's expected here, not a sign of a broken step.

- [ ] **Step 3: Replace the marker logic**

In `kicad_fpdb/pipeline.py`, delete the `_nearest_corner` function entirely (currently lines 39-42):

```python
def _nearest_corner(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float]:
    cx = x0 if abs(px - x0) <= abs(px - x1) else x1
    cy = y0 if abs(py - y0) <= abs(py - y1) else y1
    return cx, cy
```

Add a new constant next to `PIN1_MARKER_MM`:

```python
# Gap, in mm, between pad 1's own edge and the pin-1 marker circle
# drawn above it.
PIN1_MARKER_CLEARANCE_MM = 0.2
```

Remove the now-obsolete caveat from the `silk_y`/`silk_half_length` branch's comment (it no longer applies — the marker doesn't touch that branch's variables). Change:

```python
    elif silk_y is not None and silk_half_length is not None:
        # Real KiCad draws chip resistors/capacitors with two short
        # silk lines, not a box — the component body is always smaller
        # than its pads, so a box would just outline the pads
        # themselves. Both values are copied verbatim from real
        # reference footprints per variant (no shared formula holds
        # across pad sizes) — see docs/superpowers/specs/2026-09-14-
        # chip-passive-silk-lines-design.md. This mode never computes a
        # body-corner rectangle, so it must not be combined with
        # pin1_marker=True (would raise NameError below) — a non-issue
        # today since every variant using this mode declares
        # pin1_marker: false.
```

to:

```python
    elif silk_y is not None and silk_half_length is not None:
        # Real KiCad draws chip resistors/capacitors with two short
        # silk lines, not a box — the component body is always smaller
        # than its pads, so a box would just outline the pads
        # themselves. Both values are copied verbatim from real
        # reference footprints per variant (no shared formula holds
        # across pad sizes) — see docs/superpowers/specs/2026-09-14-
        # chip-passive-silk-lines-design.md.
```

Replace the marker block at the end of `_add_outline` (currently):

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None:
        cx, cy = _nearest_corner(pad1.at[0], pad1.at[1], sx0, sy0, sx1, sy1)

        # An isoceles triangle whose sharp tip sits at the body corner,
        # pointing toward pad 1's actual position, with its base offset
        # outward (away from the pad) — an arrow aimed at pin 1, not just
        # a wedge sitting in the corner.
        vx, vy = pad1.at[0] - cx, pad1.at[1] - cy
        length = math.hypot(vx, vy) or 1.0
        ux, uy = vx / length, vy / length
        px, py = -uy, ux

        tip = (cx, cy)
        base_x, base_y = cx - ux * PIN1_MARKER_MM, cy - uy * PIN1_MARKER_MM
        half_width = PIN1_MARKER_MM / 2
        base1 = (base_x + px * half_width, base_y + py * half_width)
        base2 = (base_x - px * half_width, base_y - py * half_width)

        geometry.polys.append(Poly(points=[tip, base1, base2], layer="F.SilkS"))
```

with:

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None:
        # A filled circle directly above pad 1: same X as the pad,
        # offset up past its own top edge by a fixed clearance. This is
        # independent of the outline mode entirely (unlike the old
        # nearest-corner triangle) — see docs/superpowers/specs/
        # 2026-09-14-pin1-circle-marker-design.md. "Above" assumes pin 1
        # is at the top of the part, true for every generator today.
        cx = pad1.at[0]
        cy = pad1.at[1] - pad1.size[1] / 2 - PIN1_MARKER_CLEARANCE_MM
        geometry.circles.append(Circle(center=(cx, cy), radius=PIN1_MARKER_MM / 2, layer="F.SilkS"))
```

Both `math.hypot` (line 137, in the triangle vector math you just deleted) and `Poly` (line 147, same block) were the only uses of either in this file — confirmed via `grep -n "math\.\|Poly" kicad_fpdb/pipeline.py` before this change. Remove the now-unused `import math` line entirely, and update the geometry import to drop `Poly` and add `Circle`:

```python
from kicad_fpdb.geometry import Circle, Line, Rect, Text, pad_bounding_box
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (90 baseline from Task 1 + 0 net new, since this task only modifies existing tests = 90).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Replace the pin-1 triangle marker with a circle above pad 1

The marker is now a filled circle positioned directly above pad 1's
own position (same X, offset past its top edge by a fixed clearance),
independent of the F.SilkS outline mode entirely. Removes the now-dead
_nearest_corner helper and the outline-mode dependency it required.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Visual verification and doc update

**Files:**
- Modify: `CLAUDE.md` (the pin-1 marker bullet in the running notes section)
- Regenerate (not committed — gitignored): `renders/`

**Interfaces:**
- Consumes: the completed pipeline change from Task 2 — no new code interfaces.
- Produces: nothing consumed by later tasks; this is the final task in this plan.

- [ ] **Step 1: Regenerate the visual review page**

Run: `~/.venvs/kicad-fpdb/bin/python -m kicad_fpdb.visual_compare`
Expected output: `Wrote 12 case(s) to renders/` followed by `Open renders/review.html in a browser to review.`

- [ ] **Step 2: Visually check the DIP, SOIC, and QFP cases**

Open `renders/review.html` (e.g. `xdg-open renders/review.html`). For DIP-16/14/18/16r, SOIC-8/14, and QFP-32/48, the Generated panel should now show a small filled circle directly above pad 1 (same X as the pad), not a triangle at a body corner. R-0402/0603/0805 and C-0603 should still show no marker at all.

If a case looks wrong (circle missing, overlapping the pad, or positioned oddly), stop and re-check Task 2 before proceeding.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the bullet (in the "Claude-isms below" section) that currently reads:

```
* Pin-1 marker: a small filled silkscreen triangle, tip at the body
  corner nearest pad 1, pointing at pad 1's actual position — matches
  real KiCad's own convention (see `kicad_fpdb.pipeline._add_outline`).
  Controlled by a `pin1_marker` param (default true, so DIP/SOIC/QFP
  need no declaration); `R` and `C` declare it false at their family
  root in `data/kicad-fpdb.yaml` since resistors are never polarized
  and capacitors only occasionally are — see
  `docs/superpowers/specs/2026-09-14-pin1-marker-opt-out-design.md`. A
  future polarized capacitor variant opts back in with
  `pin1_marker: true` in its own params.
```

Replace it with:

```
* Pin-1 marker: a small filled silkscreen circle sitting directly
  above pad 1 (same X as the pad, offset past its own top edge by a
  fixed clearance), independent of the F.SilkS outline entirely — a
  deliberate departure from real KiCad's own top-center notch
  convention, not an attempt to match it (see
  `kicad_fpdb.pipeline._add_outline`,
  `docs/superpowers/specs/2026-09-14-pin1-circle-marker-design.md`).
  "Above" assumes pin 1 is at the top of the part, true for every
  generator today — pin 1 isn't always at a corner in real packages
  (sometimes mid-side), and this anchor-to-pad-1 approach already
  handles that correctly, but a family with pin 1 on a different edge
  would need the "above" direction generalized. Controlled by a
  `pin1_marker` param (default true, so DIP/SOIC/QFP need no
  declaration); `R` and `C` declare it false at their family root in
  `data/kicad-fpdb.yaml` since resistors are never polarized and
  capacitors only occasionally are — see
  `docs/superpowers/specs/2026-09-14-pin1-marker-opt-out-design.md`. A
  future polarized capacitor variant opts back in with
  `pin1_marker: true` in its own params.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document pin-1 circle marker

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
