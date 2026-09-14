# DIP Top-Notch Arc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give DIP's F.SilkS rectangle a semicircular notch cut into its top edge, matching real KiCad's DIP convention exactly (radius 1.0mm, centered at body center-x, confirmed constant across every pin count and row-spacing width checked).

**Architecture:** A new `Arc` geometry primitive (`kicad_fpdb/geometry.py`) and `fp_arc` writer support (`kicad_fpdb/writer.py`) mirror the existing `Line`/`Rect`/`Poly`/`Circle` pattern. `_add_outline()` in `kicad_fpdb/pipeline.py` gains an optional `notch_radius` parameter used only inside the `body_width`/`body_margin` rectangle branch: when given, the top edge is split into two short `Line`s with an `Arc` filling the gap between them; when absent (every family except DIP, including SOIC which shares this same branch), behavior is unchanged. `DIP` declares `notch_radius: 1.0` at its family root in `data/kicad-fpdb.yaml`, inherited by every child.

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q`.

## Global Constraints

- Only the `body_width`/`body_margin` branch's top-edge drawing changes. Courtyard, the pin-1 marker, and every other outline mode (QFP corner marks, chip-passive two lines, the generic fallback) are untouched.
- SOIC shares the `body_width`/`body_margin` branch but must not get a notch — its YAML entry stays untouched, so `notch_radius` stays `None` for it and it keeps today's plain 4-line rectangle, byte-identical to before this change.
- Exact value to use (from the spec, `docs/superpowers/specs/2026-09-14-dip-notch-arc-design.md`): `notch_radius: 1.0` for DIP, confirmed constant across every pin count and width checked.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Add the `Arc` geometry primitive

**Files:**
- Modify: `kicad_fpdb/geometry.py` (add `Arc` dataclass, `arcs` field on `FootprintGeometry`)
- Modify: `kicad_fpdb/writer.py` (add `_write_arc`, wire into `write_kicad_mod`)
- Test: `tests/test_writer.py`

**Interfaces:**
- Produces: `Arc(start: tuple[float, float], mid: tuple[float, float], end: tuple[float, float], layer: str, width: float = 0.12)` (no `fill` field — arcs are open curves), and `FootprintGeometry.arcs: list[Arc]`. Relied on by Task 2.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_writer.py`, after `test_write_circle`:

```python
def test_write_arc():
    arc = Arc(start=(4.81, -1.33), mid=(3.81, -0.33), end=(2.81, -1.33), layer="F.SilkS")
    geom = FootprintGeometry(name="TEST_MIN", arcs=[arc])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_arc" in text
    assert "(start 4.81 -1.33)" in text
    assert "(mid 3.81 -0.33)" in text
    assert "(end 2.81 -1.33)" in text
    assert '(layer "F.SilkS")' in text
```

Update the import line at the top of the file:

```python
from kicad_fpdb.geometry import Arc, Circle, FootprintGeometry, Line, Pad, Poly, Rect, Text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_writer.py -v`
Expected: FAILS with `ImportError: cannot import name 'Arc' from 'kicad_fpdb.geometry'`.

- [ ] **Step 3: Add the `Arc` dataclass**

In `kicad_fpdb/geometry.py`, add after the `Circle` dataclass (before `FootprintGeometry`):

```python
@dataclass
class Arc:
    start: tuple[float, float]
    mid: tuple[float, float]
    end: tuple[float, float]
    layer: str
    width: float = 0.12
```

Add an `arcs` field to `FootprintGeometry`:

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
    arcs: list[Arc] = field(default_factory=list)
```

- [ ] **Step 4: Add writer support**

In `kicad_fpdb/writer.py`, update the import line:

```python
from kicad_fpdb.geometry import Arc, Circle, FootprintGeometry, Line, Pad, Poly, Rect, Text
```

Add a loop over arcs in `write_kicad_mod`, after the existing circle loop:

```python
    for circle in geometry.circles:
        lines.append(_write_circle(circle))
    for arc in geometry.arcs:
        lines.append(_write_arc(arc))
    for pad in geometry.pads:
```

Add the `_write_arc` function, after `_write_circle`:

```python
def _write_arc(arc: Arc) -> str:
    sx, sy = arc.start
    mx, my = arc.mid
    ex, ey = arc.end
    return (
        "  (fp_arc\n"
        f"    (start {_fmt(sx)} {_fmt(sy)})\n"
        f"    (mid {_fmt(mx)} {_fmt(my)})\n"
        f"    (end {_fmt(ex)} {_fmt(ey)})\n"
        "    (stroke\n"
        f"      (width {_fmt(arc.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f'    (layer "{arc.layer}")\n'
        "  )"
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_writer.py -v`
Expected: all tests PASS, including the new one.

- [ ] **Step 6: Extend the kicad-cli round-trip test to cover arcs**

In `tests/test_writer.py`, add an arc to the geometry built in `test_generated_file_is_valid_kicad_mod` (validates the new primitive's S-expression syntax against real `kicad-cli`):

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
        arcs=[Arc(start=(1.0, -0.5), mid=(0.5, -1.0), end=(0.0, -0.5), layer="F.SilkS")],
    )
```

- [ ] **Step 7: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (89 baseline + 1 new = 90). If `test_generated_file_is_valid_kicad_mod` is skipped on this machine (no `kicad-cli` on PATH), say so in your report rather than assuming it ran.

- [ ] **Step 8: Commit**

```bash
git add kicad_fpdb/geometry.py kicad_fpdb/writer.py tests/test_writer.py
git commit -m "$(cat <<'EOF'
Add an Arc geometry primitive and fp_arc writer support

Mirrors the existing Line/Rect/Poly/Circle pattern. Needed by the
upcoming DIP top-notch, but generic — not DIP-specific.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Give DIP's rectangle mode a top notch

**Files:**
- Modify: `kicad_fpdb/pipeline.py` (the `_add_outline` function's `body_width`/`body_margin` branch; `generate_footprint`)
- Modify: `data/kicad-fpdb.yaml` (DIP's root `params`)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `Arc` from Task 1.
- Produces: `_add_outline` gains a `notch_radius: float | None = None` parameter. `generate_footprint`'s signature and every other parameter are unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`, anywhere after `test_add_outline_with_body_params_matches_real_dip16_narrow`:

```python
def test_add_outline_with_notch_radius_splits_top_edge():
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33, notch_radius=1.0)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    # 5 lines now (top edge split into 2) instead of 4, plus 1 arc.
    assert len(silk_lines) == 5
    assert len(geometry.arcs) == 1

    arc = geometry.arcs[0]
    assert arc.layer == "F.SilkS"
    # Real DIP-16_W7.62mm.kicad_mod notch is exactly this arc.
    assert arc.start == pytest.approx((4.81, -1.33))
    assert arc.mid == pytest.approx((3.81, -0.33))
    assert arc.end == pytest.approx((2.81, -1.33))

    top_segment_endpoints = {
        (round(pt[0], 5), round(pt[1], 5))
        for line in silk_lines if line.start[1] == pytest.approx(-1.33) and line.end[1] == pytest.approx(-1.33)
        for pt in (line.start, line.end)
    }
    assert (1.16, -1.33) in top_segment_endpoints
    assert (2.81, -1.33) in top_segment_endpoints
    assert (4.81, -1.33) in top_segment_endpoints
    assert (6.46, -1.33) in top_segment_endpoints


def test_add_outline_without_notch_radius_keeps_plain_top_edge():
    # SOIC shares this same body_width/body_margin branch but never
    # declares notch_radius — must keep today's plain 4-line rectangle.
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4
    assert len(geometry.arcs) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_add_outline_with_notch_radius_splits_top_edge` FAILS with `TypeError: _add_outline() got an unexpected keyword argument 'notch_radius'`. `test_add_outline_without_notch_radius_keeps_plain_top_edge` PASSES already (it exercises unchanged behavior) — that's fine, it locks the contract before Step 3 touches the function.

- [ ] **Step 3: Implement the notch**

In `kicad_fpdb/pipeline.py`, add `Arc` to the geometry import:

```python
from kicad_fpdb.geometry import Arc, Circle, Line, Rect, Text, pad_bounding_box
```

Change the `_add_outline` signature:

```python
def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True,
                  silk_y: float | None = None, silk_half_length: float | None = None,
                  courtyard_margin_x: float | None = None, courtyard_margin_y: float | None = None,
                  notch_radius: float | None = None) -> None:
```

Replace the `body_width`/`body_margin` branch's line-drawing block (currently):

```python
        corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
        for i in range(4):
            start, end = corners[i], corners[(i + 1) % 4]
            geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))
    elif body_size is not None:
```

with:

```python
        if notch_radius is not None:
            # Real KiCad cuts a semicircular notch into the DIP body's
            # top edge (the pin-1-side indicator molded into the
            # physical package) — a true semicircle centered at the
            # body's horizontal center, constant radius regardless of
            # pin count or width class. See docs/superpowers/specs/
            # 2026-09-14-dip-notch-arc-design.md. SOIC shares this
            # branch but never declares notch_radius, so it's
            # unaffected.
            notch_left, notch_right = center_x - notch_radius, center_x + notch_radius
            geometry.lines.append(Line(start=(sx0, sy0), end=(notch_left, sy0), layer="F.SilkS"))
            geometry.lines.append(Line(start=(notch_right, sy0), end=(sx1, sy0), layer="F.SilkS"))
            geometry.arcs.append(Arc(
                start=(notch_right, sy0), mid=(center_x, sy0 + notch_radius), end=(notch_left, sy0),
                layer="F.SilkS",
            ))
            geometry.lines.append(Line(start=(sx1, sy0), end=(sx1, sy1), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx1, sy1), end=(sx0, sy1), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx0, sy1), end=(sx0, sy0), layer="F.SilkS"))
        else:
            corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
            for i in range(4):
                start, end = corners[i], corners[(i + 1) % 4]
                geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))
    elif body_size is not None:
```

Update `generate_footprint` to pop and pass `notch_radius`:

```python
    params = dict(resolved.params)
    body_width = params.pop("body_width", None)
    body_margin = params.pop("body_margin", None)
    body_size = params.pop("body_size", None)
    pin1_marker = params.pop("pin1_marker", True)
    silk_y = params.pop("silk_y", None)
    silk_half_length = params.pop("silk_half_length", None)
    courtyard_margin_x = params.pop("courtyard_margin_x", None)
    courtyard_margin_y = params.pop("courtyard_margin_y", None)
    notch_radius = params.pop("notch_radius", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, silk_y=silk_y, silk_half_length=silk_half_length,
                 courtyard_margin_x=courtyard_margin_x, courtyard_margin_y=courtyard_margin_y,
                 notch_radius=notch_radius)
```

- [ ] **Step 4: Add `notch_radius` to DIP's root params**

In `data/kicad-fpdb.yaml`, change DIP's `params` block (currently):

```yaml
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: narrow
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    body_width: {narrow: 5.3, regular: 6.47, wide: 12.92}
    body_margin: 1.33
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.72
    pad_size: [1.6, 1.6]
    pad_shape: dip_pin1_marker
    pad_type: thru_hole
    drill: 0.8
    centered: false
```

to:

```yaml
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: narrow
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    body_width: {narrow: 5.3, regular: 6.47, wide: 12.92}
    body_margin: 1.33
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.72
    notch_radius: 1.0
    pad_size: [1.6, 1.6]
    pad_shape: dip_pin1_marker
    pad_type: thru_hole
    drill: 0.8
    centered: false
```

Do not touch `SOIC`, `QFP`, `R`, or `C`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS, including every pre-existing test (they either don't touch the `body_width`/`body_margin` branch at all, or call it without `notch_radius`, which defaults to `None` and keeps the plain-rectangle path).

- [ ] **Step 6: Add generate_footprint-level regression tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_dip16_has_top_notch():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(fp_arc" in text
    assert "(start 4.81 -1.33)" in text
    assert "(mid 3.81 -0.33)" in text
    assert "(end 2.81 -1.33)" in text


def test_generate_footprint_soic8_has_no_notch():
    # SOIC shares the body_width/body_margin branch but must not get one.
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert "(fp_arc" not in text


def test_generate_footprint_does_not_leak_notch_radius_to_generator():
    # If pipeline.py forgot to pop notch_radius before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert text  # got here without raising
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS.

- [ ] **Step 8: Run the full suite, including the KiCad-dependent regression suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass. `tests/test_pipeline_regression.py` (parametrized over every case including every DIP variant) must still pass — it only checks pad geometry, unaffected by this change. If it's skipped on this machine (KiCad footprints not present), say so in your report rather than assuming it ran.

- [ ] **Step 9: Commit**

```bash
git add kicad_fpdb/pipeline.py data/kicad-fpdb.yaml tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Give DIP's silk rectangle a real top-notch arc

Real KiCad cuts a semicircular notch (radius 1.0mm, centered at body
center-x) into the DIP body's top edge, constant across every pin
count and width class checked. SOIC shares the same rectangle branch
but never declares notch_radius, so its output is unaffected.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Visual verification and doc update

**Files:**
- Modify: `CLAUDE.md` (the outline-geometry bullet in the running notes section)
- Regenerate (not committed — gitignored): `renders/`

**Interfaces:**
- Consumes: the completed pipeline change from Task 2 — no new code interfaces.
- Produces: nothing consumed by later tasks; this is the final task in this plan.

- [ ] **Step 1: Regenerate the visual review page**

Run: `~/.venvs/kicad-fpdb/bin/python -m kicad_fpdb.visual_compare`
Expected output: `Wrote 12 case(s) to renders/` followed by `Open renders/review.html in a browser to review.`

- [ ] **Step 2: Visually check the DIP and SOIC cases**

Open `renders/review.html` (e.g. `xdg-open renders/review.html`). For DIP-16/14/18/16r, the Generated panel should now show a semicircular notch cut into the top edge, closely matching the Reference panel (should be a near-exact match — the value is copied verbatim from real footprints). SOIC-8/14 should be unchanged (plain rectangle, no notch).

If a case looks wrong (notch missing, misplaced, or appearing on SOIC), stop and re-check Task 2 before proceeding.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the sentence (in the "Claude-isms below" section, inside the outline-geometry bullet) that currently reads:

```
For F.SilkS geometry: DIP and
  SOIC draw a real body-derived rectangle (`body_width`/`body_margin`
  in `data/kicad-fpdb.yaml`) — DIP's body_width is keyed by width class
  (narrow/regular/wide), matching real KiCad almost exactly (SOIC's
  margin is an averaged approximation, off by ~0.01-0.02mm — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`).
```

Replace it with:

```
For F.SilkS geometry: DIP and
  SOIC draw a real body-derived rectangle (`body_width`/`body_margin`
  in `data/kicad-fpdb.yaml`) — DIP's body_width is keyed by width class
  (narrow/regular/wide), matching real KiCad almost exactly (SOIC's
  margin is an averaged approximation, off by ~0.01-0.02mm — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`).
  DIP additionally cuts a semicircular notch into the top edge
  (`notch_radius: 1.0` in `data/kicad-fpdb.yaml`, constant across every
  pin count and width checked), matching real KiCad's own DIP
  pin-1-side indicator exactly — see
  `docs/superpowers/specs/2026-09-14-dip-notch-arc-design.md`. SOIC
  shares the same rectangle branch but has no such notch in real
  KiCad, so it doesn't declare `notch_radius`.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document DIP top-notch arc

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
