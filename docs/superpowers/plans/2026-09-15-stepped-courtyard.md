# Real-Shaped Library Courtyards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give SOIC and QFP their real stepped F.CrtYd courtyard shape, and fix the chip-passive (R/C) courtyard margin, replacing the generic flat 0.5mm pad-bbox margin these families currently use.

**Architecture:** A new pure-geometry utility (`kicad_fpdb/rect_union.py`) computes the boundary of the union of axis-aligned rectangles. `_add_outline` in `kicad_fpdb/pipeline.py` uses it for families that declare a "true physical body" courtyard param (distinct from the existing, deliberately oversized `body_width`/`body_size` used only for F.SilkS): SOIC gets `[true body rect, full pad bbox]`, QFP gets `[true body square, one pad-group rect per side]`, each independently margin-expanded before the union. Chip passives need no shape change at all — just the correct per-variant flat margin, already supported by the existing `courtyard_margin_x`/`courtyard_margin_y` mechanism.

**Tech Stack:** Python 3.10+, pytest. No new dependencies.

## Global Constraints

- Margin value for SOIC and QFP's stepped courtyard: flat 0.25mm on both axes (verified against 4 real reference footprints — see spec).
- SOIC true body: width 3.9mm (constant), length derived as `pad_y_center_extent ± 0.545mm` (mirrors the existing `body_width`/`body_margin` derivation style used for F.SilkS, just with different numbers).
- QFP true body: 7.0mm square, constant across variants (both current QFP variants are 7x7mm packages).
- Chip-passive courtyard margins (flat, both axes): R-0402 → 0.15mm; R-0603, R-0805, C-0603 → 0.25mm.
- DIP's courtyard (already real, already a plain asymmetric-margin rectangle) must be byte-for-byte unaffected by every change in this plan.
- No new runtime dependencies; `union_outline` must be a pure function over plain tuples with no dependency on `kicad_fpdb.geometry`.

---

## Task 1: `rect_union` geometry utility

**Files:**
- Create: `kicad_fpdb/rect_union.py`
- Test: `tests/test_rect_union.py`

**Interfaces:**
- Produces: `union_outline(rects: list[tuple[float, float, float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]` — each input rect is `(min_x, min_y, max_x, max_y)`; the function assumes the union is simply connected (no holes) and returns one ordered closed loop of `(start, end)` segments. This is the only symbol later tasks import from this module.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rect_union.py`:

```python
from collections import Counter

from kicad_fpdb.rect_union import union_outline


def _assert_closed_rectilinear_loop(segments):
    for (sx, sy), (ex, ey) in segments:
        assert sx == ex or sy == ey
    counts = Counter(pt for seg in segments for pt in seg)
    assert all(count == 2 for count in counts.values())


def test_union_outline_two_rect_cross_matches_soic_topology():
    # Real SOIC-8 courtyard: union of the true-body rect and the full pad
    # bbox, both already margin-expanded (see design spec).
    body = (-2.2, -2.7, 2.2, 2.7)
    pad_bbox = (-3.7, -2.455, 3.7, 2.455)
    segments = union_outline([body, pad_bbox])

    assert len(segments) == 12
    _assert_closed_rectilinear_loop(segments)

    endpoints = {pt for seg in segments for pt in seg}
    assert (-2.2, -2.7) in endpoints
    assert (2.2, 2.7) in endpoints
    assert (-3.7, -2.455) in endpoints
    assert (3.7, 2.455) in endpoints
    assert (-2.2, -2.455) in endpoints
    assert (2.2, 2.455) in endpoints


def test_union_outline_five_rect_matches_qfp_topology():
    # Real LQFP-32 courtyard: union of the true-body square and one
    # margin-expanded pad-group rect per side (see design spec).
    body = (-3.75, -3.75, 3.75, 3.75)
    left = (-5.175, -3.3, -3.175, 3.3)
    right = (3.175, -3.3, 5.175, 3.3)
    bottom = (-3.3, 3.175, 3.3, 5.175)
    top = (-3.3, -5.175, 3.3, -3.175)
    segments = union_outline([body, left, right, bottom, top])

    assert len(segments) == 20
    _assert_closed_rectilinear_loop(segments)

    endpoints = {pt for seg in segments for pt in seg}
    for corner in [(-3.75, -3.75), (3.75, 3.75), (-3.75, 3.75), (3.75, -3.75)]:
        assert corner in endpoints
    assert (-5.175, -3.3) in endpoints
    assert (5.175, 3.3) in endpoints
    assert (-3.3, -5.175) in endpoints
    assert (3.3, 5.175) in endpoints
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_rect_union.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.rect_union'`

- [ ] **Step 3: Implement `union_outline`**

Create `kicad_fpdb/rect_union.py`:

```python
def union_outline(
    rects: list[tuple[float, float, float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Boundary of the union of axis-aligned rects (each as
    (min_x, min_y, max_x, max_y)), as an ordered closed loop of
    (start, end) segments. Assumes the union is simply connected (no
    holes) -- true for every shape this project constructs."""
    xs = sorted({x for r in rects for x in (r[0], r[2])})
    ys = sorted({y for r in rects for y in (r[1], r[3])})

    def filled(ci: int, cj: int) -> bool:
        if ci < 0 or cj < 0 or ci >= len(xs) - 1 or cj >= len(ys) - 1:
            return False
        cx = (xs[ci] + xs[ci + 1]) / 2
        cy = (ys[cj] + ys[cj + 1]) / 2
        return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects)

    raw_edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for ci in range(len(xs) - 1):
        for cj in range(len(ys) - 1):
            if not filled(ci, cj):
                continue
            x0, x1 = xs[ci], xs[ci + 1]
            y0, y1 = ys[cj], ys[cj + 1]
            if not filled(ci, cj - 1):
                raw_edges.append(((x0, y0), (x1, y0)))
            if not filled(ci, cj + 1):
                raw_edges.append(((x1, y1), (x0, y1)))
            if not filled(ci - 1, cj):
                raw_edges.append(((x0, y1), (x0, y0)))
            if not filled(ci + 1, cj):
                raw_edges.append(((x1, y0), (x1, y1)))

    # Walk the boundary edges into one ordered loop, merging consecutive
    # collinear edges as we go (every vertex has degree 2, since the
    # union has no holes).
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for a, b in raw_edges:
        adjacency.setdefault(a, []).append(b)

    def direction(a, b):
        return (
            0 if b[0] == a[0] else (1 if b[0] > a[0] else -1),
            0 if b[1] == a[1] else (1 if b[1] > a[1] else -1),
        )

    start = raw_edges[0][0]
    loop = [start]
    current = start
    prev_dir = None
    for _ in range(len(raw_edges)):
        nxt = adjacency[current].pop(0)
        if not adjacency[current]:
            del adjacency[current]
        d = direction(current, nxt)
        if d == prev_dir:
            loop[-1] = nxt
        else:
            loop.append(nxt)
        prev_dir = d
        current = nxt

    if loop[-1] == loop[0]:
        loop.pop()
    return [(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_rect_union.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/rect_union.py tests/test_rect_union.py
git commit -m "$(cat <<'EOF'
Add rect_union: axis-aligned rectangle union boundary tracer

Pure-geometry utility for the upcoming real stepped courtyard shapes
(SOIC, QFP) — verified against both real topologies (dual-row cross,
quad four-arm shape).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire stepped courtyards into `_add_outline`

**Files:**
- Modify: `kicad_fpdb/pipeline.py`
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `union_outline` from Task 1 (`kicad_fpdb.rect_union`).
- Produces: `_add_outline` gains three new optional keyword params —
  `courtyard_body_width: float | None = None`,
  `courtyard_body_margin: float | None = None` (dual-row/SOIC-style true
  body, used together), and `courtyard_body_size: float | None = None`
  (quad/QFP-style true body square). `generate_footprint` pops all three
  from resolved params (defaulting to `None`) alongside the existing
  outline params and threads them through, same pattern as every other
  outline param.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`, near the existing `_qfp32_geometry` helper:

```python
def _soic8_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("SOIC-8"))
    params = dict(resolved.params)
    params.pop("body_width", None)
    params.pop("body_margin", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "SOIC8_TEST"
    return geometry
```

Then add these test functions:

```python
def test_add_outline_with_courtyard_body_width_draws_stepped_courtyard():
    geometry = _soic8_geometry()
    _add_outline(
        geometry, body_width=4.12, body_margin=0.64,
        courtyard_margin_x=0.25, courtyard_margin_y=0.25,
        courtyard_body_width=3.9, courtyard_body_margin=0.545,
    )

    assert len(geometry.rects) == 0
    crtyd_lines = [line for line in geometry.lines if line.layer == "F.CrtYd"]
    assert len(crtyd_lines) == 12

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in crtyd_lines for pt in (line.start, line.end)}
    # Real SOIC-8 courtyard shape (see design spec): true body 3.9x4.9mm,
    # full pad bbox, both expanded 0.25mm.
    assert (-2.2, -2.7) in endpoints
    assert (2.2, 2.7) in endpoints
    assert (-3.7, -2.455) in endpoints
    assert (3.7, 2.455) in endpoints


def test_add_outline_with_courtyard_body_size_draws_stepped_courtyard():
    geometry = _qfp32_geometry()
    _add_outline(
        geometry, body_size=7.22,
        courtyard_margin_x=0.25, courtyard_margin_y=0.25,
        courtyard_body_size=7.0,
    )

    assert len(geometry.rects) == 0
    crtyd_lines = [line for line in geometry.lines if line.layer == "F.CrtYd"]
    assert len(crtyd_lines) == 20

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in crtyd_lines for pt in (line.start, line.end)}
    # Real LQFP-32 courtyard shape (see design spec): true 7x7mm body
    # square, one pad-group rect per side, all expanded 0.25mm.
    assert (-3.75, -3.75) in endpoints
    assert (3.75, 3.75) in endpoints
    assert (-5.175, -3.3) in endpoints
    assert (5.175, 3.3) in endpoints


def test_add_outline_without_courtyard_body_params_keeps_plain_rect():
    # Regression guard: DIP (and any family that doesn't declare the new
    # courtyard_body_* params) must be completely unaffected.
    geometry = _dip16_geometry()
    _add_outline(geometry, courtyard_margin_x=0.25, courtyard_margin_y=0.72)

    assert len(geometry.rects) == 1
    assert not any(line.layer == "F.CrtYd" for line in geometry.lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k courtyard_body -v`
Expected: FAIL with `TypeError: _add_outline() got an unexpected keyword argument 'courtyard_body_width'`

- [ ] **Step 3: Implement the branch in `kicad_fpdb/pipeline.py`**

Add the import at the top of the file:

```python
from kicad_fpdb.rect_union import union_outline
```

Change the `_add_outline` signature (currently ending `notch_radius: float | None = None) -> None:`) to add the three new params:

```python
def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True,
                  silk_y: float | None = None, silk_half_length: float | None = None,
                  courtyard_margin_x: float | None = None, courtyard_margin_y: float | None = None,
                  courtyard_body_width: float | None = None, courtyard_body_margin: float | None = None,
                  courtyard_body_size: float | None = None,
                  notch_radius: float | None = None) -> None:
```

Replace the current courtyard block (the single `geometry.rects.append(Rect(...))` call right after `mx`/`my` are computed) with:

```python
    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM

    if courtyard_body_width is not None and courtyard_body_margin is not None:
        # Real stepped courtyard (SOIC-style): union of the true physical
        # body rect and the full pad bbox, independently margin-expanded.
        # courtyard_body_width/_margin are deliberately separate from
        # body_width/body_margin (used for the oversized F.SilkS body) —
        # see docs/superpowers/specs/2026-09-15-stepped-courtyard-design.md.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        ccx = (min_px + max_px) / 2
        body_rect = (
            ccx - courtyard_body_width / 2, min_py - courtyard_body_margin,
            ccx + courtyard_body_width / 2, max_py + courtyard_body_margin,
        )
        rects = [body_rect, (min_x, min_y, max_x, max_y)]
        expanded = [(r[0] - mx, r[1] - my, r[2] + mx, r[3] + my) for r in rects]
        for start, end in union_outline(expanded):
            geometry.lines.append(Line(start=start, end=end, layer="F.CrtYd"))
    elif courtyard_body_size is not None:
        # Real stepped courtyard (QFP-style): union of the true physical
        # body square and one pad-group rect per side, independently
        # margin-expanded. courtyard_body_size is deliberately separate
        # from body_size (used for the oversized F.SilkS corner marks).
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        ccx, ccy = (min_px + max_px) / 2, (min_py + max_py) / 2
        half = courtyard_body_size / 2
        body_rect = (ccx - half, ccy - half, ccx + half, ccy + half)
        rects = [body_rect] + list(_quad_side_groups(geometry.pads).values())
        expanded = [(r[0] - mx, r[1] - my, r[2] + mx, r[3] + my) for r in rects]
        for start, end in union_outline(expanded):
            geometry.lines.append(Line(start=start, end=end, layer="F.CrtYd"))
    else:
        cy0x, cy0y = min_x - mx, min_y - my
        cy1x, cy1y = max_x + mx, max_y + my
        geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))
```

Add the new helper function right after `_pad_center_extent`:

```python
def _quad_side_groups(pads) -> dict[str, tuple[float, float, float, float]]:
    groups: dict[str, list] = {"left": [], "right": [], "top": [], "bottom": []}
    for p in pads:
        w, h = p.size
        if w > h:
            groups["left" if p.at[0] < 0 else "right"].append(p)
        else:
            groups["top" if p.at[1] < 0 else "bottom"].append(p)
    return {
        side: (
            min(p.at[0] - p.size[0] / 2 for p in group),
            min(p.at[1] - p.size[1] / 2 for p in group),
            max(p.at[0] + p.size[0] / 2 for p in group),
            max(p.at[1] + p.size[1] / 2 for p in group),
        )
        for side, group in groups.items() if group
    }
```

In `generate_footprint`, add these three lines alongside the existing
`courtyard_margin_x`/`courtyard_margin_y` pops:

```python
    courtyard_body_width = params.pop("courtyard_body_width", None)
    courtyard_body_margin = params.pop("courtyard_body_margin", None)
    courtyard_body_size = params.pop("courtyard_body_size", None)
```

And extend the `_add_outline(...)` call in `generate_footprint` to pass them through:

```python
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, silk_y=silk_y, silk_half_length=silk_half_length,
                 courtyard_margin_x=courtyard_margin_x, courtyard_margin_y=courtyard_margin_y,
                 courtyard_body_width=courtyard_body_width, courtyard_body_margin=courtyard_body_margin,
                 courtyard_body_size=courtyard_body_size,
                 notch_radius=notch_radius)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pipeline_outline.py -v`
Expected: all pass (existing tests plus the 3 new ones)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `python3 -m pytest -q`
Expected: all pass (no yaml data changed yet, so SOIC/QFP/R/C still use the old flat-margin path — this step only confirms the new code path didn't break anything else)

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Wire real stepped courtyard shapes into _add_outline

New opt-in courtyard_body_width/_margin (dual-row/SOIC) and
courtyard_body_size (quad/QFP) params build a rect-union courtyard via
rect_union.union_outline instead of the flat single-rect margin.
Families that don't declare these (DIP, everything else) are
unaffected — still the existing plain Rect.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Give SOIC and QFP their real courtyard data

**Files:**
- Modify: `data/kicad-fpdb.yaml`
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `courtyard_margin_x`/`_y`, `courtyard_body_width`/`_margin`, `courtyard_body_size` params from Task 2.
- Produces: `generate_footprint("SOIC-8"/"SOIC-14"/"QFP-32"/"QFP-48", ...)` now emit the stepped F.CrtYd shape.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_soic8_courtyard_matches_stepped_shape():
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert text.count("(fp_rect") == 0
    assert '(layer "F.CrtYd")' in text
    assert "(start -2.2 -2.7)" in text
    assert "(start -3.7 -2.455)" in text
    assert "(end 3.7 2.455)" in text


def test_generate_footprint_soic14_courtyard_matches_stepped_shape():
    text = generate_footprint("SOIC-14", FAMILY_TREE_PATH, name="SOIC14_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -2.2 -4.605)" in text
    assert "(start -3.7 -4.36)" in text
    assert "(end 3.7 4.36)" in text


def test_generate_footprint_qfp32_courtyard_matches_stepped_shape():
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -3.75 -3.75)" in text
    assert "(start -5.175 -3.3)" in text
    assert "(end 5.175 3.3)" in text


def test_generate_footprint_qfp48_courtyard_matches_stepped_shape():
    text = generate_footprint("QFP-48", FAMILY_TREE_PATH, name="QFP48_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -3.75 -3.75)" in text
    assert "(start -5.15 -3.15)" in text
    assert "(end 5.15 3.15)" in text


def test_generate_footprint_does_not_leak_courtyard_body_params_to_generator():
    # If pipeline.py forgot to pop courtyard_body_width/_margin/_size
    # before calling the generator, this raises
    # TypeError("unexpected keyword argument").
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert text
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k "soic8_courtyard_matches_stepped or soic14_courtyard_matches_stepped or qfp32_courtyard_matches_stepped or qfp48_courtyard_matches_stepped" -v`
Expected: FAIL (SOIC-8/SOIC-14/QFP-32/QFP-48 still emit `(fp_rect ... F.CrtYd)`, so `text.count("(fp_rect")` is 1, not 0, and the expected coordinates aren't present)

- [ ] **Step 3: Update `data/kicad-fpdb.yaml`**

In the `SOIC:` block, change:

```yaml
SOIC:
  generator: dual_row_grid
  variant_param: pin_count
  params:
    pitch: 1.27
    row_spacing: 4.95
    body_width: 4.12
    body_margin: 0.64
    pad_size: [1.95, 0.6]
    pad_shape: roundrect
    pad_type: smd
    centered: true
```

to:

```yaml
SOIC:
  generator: dual_row_grid
  variant_param: pin_count
  params:
    pitch: 1.27
    row_spacing: 4.95
    body_width: 4.12
    body_margin: 0.64
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    courtyard_body_width: 3.9
    courtyard_body_margin: 0.545
    pad_size: [1.95, 0.6]
    pad_shape: roundrect
    pad_type: smd
    centered: true
```

In the `QFP:` block, change both children:

```yaml
QFP:
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_offset: 4.175, pad_size: [1.5, 0.5], body_size: 7.22}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_offset: 4.1625, pad_size: [1.475, 0.3], body_size: 7.22}
```

to:

```yaml
QFP:
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_offset: 4.175, pad_size: [1.5, 0.5], body_size: 7.22, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, courtyard_body_size: 7.0}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_offset: 4.1625, pad_size: [1.475, 0.3], body_size: 7.22, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25, courtyard_body_size: 7.0}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pipeline_outline.py -v`
Expected: all pass

- [ ] **Step 5: Run the full test suite (including KiCad-dependent regression tests)**

Run: `python3 -m pytest -q`
Expected: all pass. The pad-geometry regression suite
(`tests/test_pipeline_regression.py`) only checks pads, not courtyard
geometry, so it's unaffected by this change; this step just confirms
nothing else broke.

- [ ] **Step 6: Commit**

```bash
git add data/kicad-fpdb.yaml tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Give SOIC and QFP their real stepped F.CrtYd courtyard

Data-only wiring of the courtyard_body_width/_margin (SOIC) and
courtyard_body_size (QFP) params added in the previous commit, with a
flat 0.25mm margin verified against SOIC-8, SOIC-14, LQFP-32, and
LQFP-48 reference footprints.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Fix chip-passive (R/C) courtyard margins

**Files:**
- Modify: `data/kicad-fpdb.yaml`
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: existing `courtyard_margin_x`/`courtyard_margin_y` mechanism (no pipeline.py change needed — R/C never declare `courtyard_body_width`/`courtyard_body_size`, so they keep using the plain-`Rect` branch, just with a declared margin instead of the `COURTYARD_MARGIN_MM` fallback).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_r0402_courtyard_matches_real_margin():
    text = generate_footprint("R-0402", FAMILY_TREE_PATH, name="R0402_TEST")
    assert "(start -0.93 -0.47)" in text
    assert "(end 0.93 0.47)" in text


def test_generate_footprint_r0603_courtyard_matches_real_margin():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "(start -1.475 -0.725)" in text
    assert "(end 1.475 0.725)" in text


def test_generate_footprint_r0805_courtyard_matches_real_margin():
    text = generate_footprint("R-0805", FAMILY_TREE_PATH, name="R0805_TEST")
    assert "(start -1.675 -0.95)" in text
    assert "(end 1.675 0.95)" in text


def test_generate_footprint_c0603_courtyard_matches_real_margin():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "(start -1.475 -0.725)" in text
    assert "(end 1.475 0.725)" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k "r0402_courtyard or r0603_courtyard or r0805_courtyard or c0603_courtyard" -v`
Expected: FAIL (currently emits the generic flat 0.5mm margin — e.g. R-0402 currently emits `(start -1.28 -0.82)`/`(end 1.28 0.82)`, not the real `-0.93 -0.47`/`0.93 0.47`)

- [ ] **Step 3: Update `data/kicad-fpdb.yaml`**

In the `R:` block, change:

```yaml
R:
  params:
    pin1_marker: false
  children:
    R-0402:
      generator: two_pad_chip
      params: {pad_pitch: 1.02, pad_size: [0.54, 0.64], silk_y: 0.38, silk_half_length: 0.153641}
    R-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.65, pad_size: [0.8, 0.95], silk_y: 0.5225, silk_half_length: 0.237258}
    R-0805:
      generator: two_pad_chip
      params: {pad_pitch: 1.825, pad_size: [1.025, 1.4], silk_y: 0.735, silk_half_length: 0.227064}
```

to:

```yaml
R:
  params:
    pin1_marker: false
  children:
    R-0402:
      generator: two_pad_chip
      params: {pad_pitch: 1.02, pad_size: [0.54, 0.64], silk_y: 0.38, silk_half_length: 0.153641, courtyard_margin_x: 0.15, courtyard_margin_y: 0.15}
    R-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.65, pad_size: [0.8, 0.95], silk_y: 0.5225, silk_half_length: 0.237258, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25}
    R-0805:
      generator: two_pad_chip
      params: {pad_pitch: 1.825, pad_size: [1.025, 1.4], silk_y: 0.735, silk_half_length: 0.227064, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25}
```

In the `C:` block, change:

```yaml
C:
  params:
    pin1_marker: false
  children:
    C-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.55, pad_size: [0.9, 0.95], silk_y: 0.51, silk_half_length: 0.14058}
```

to:

```yaml
C:
  params:
    pin1_marker: false
  children:
    C-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.55, pad_size: [0.9, 0.95], silk_y: 0.51, silk_half_length: 0.14058, courtyard_margin_x: 0.25, courtyard_margin_y: 0.25}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pipeline_outline.py -v`
Expected: all pass

- [ ] **Step 5: Run the full test suite**

Run: `python3 -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add data/kicad-fpdb.yaml tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Fix chip-passive (R/C) courtyard margins to match real KiCad

R-0402 uses 0.15mm; R-0603, R-0805, and C-0603 use 0.25mm — replacing
the generic flat 0.5mm margin. No shape change (already a plain
rectangle in real KiCad), just the correct per-variant margin, same
mechanism DIP's courtyard already uses.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Regenerate the review viewer and update project docs

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md`
- Regenerate: `renders/review.html` (gitignored, not committed)

**Interfaces:** None — this task only updates documentation and regenerates a local, gitignored artifact.

- [ ] **Step 1: Regenerate the review viewer**

Run: `python3 -m kicad_fpdb.visual_compare`
Expected: `Wrote 12 case(s) to renders/` followed by `Open renders/review.html in a browser to review.`

- [ ] **Step 2: Open it and visually confirm**

Run: `xdg-open renders/review.html`

Visually confirm: SOIC-8, SOIC-14, QFP-32, and QFP-48's generated (left)
panels now show a stepped F.CrtYd courtyard closely matching their real
reference (right) panel's shape, and R-0402/R-0603/R-0805/C-0603's
courtyard rectangles are visibly tighter than before (closer to their
pads) and still match their reference panels. DIP's courtyard must look
completely unchanged from before this plan.

- [ ] **Step 3: Update `CLAUDE.md`**

In the TODO section, remove this item (now done):

```markdown
* Match SOIC's real courtyard shape: real SOIC footprints use a stepped
  multi-segment courtyard (hugging the pad envelope more closely at the
  ends than in the middle), not a simple rectangle with a bigger margin
  like DIP's. Parked when DIP's courtyard was tightened (see
  `docs/superpowers/specs/2026-09-14-dip-courtyard-margin-design.md`).
```

In the long-form bullet list (near the other courtyard/silkscreen
narrative bullets, after the DIP courtyard paragraph), add:

```markdown
* SOIC and QFP now have their own real stepped `F.CrtYd` courtyard —
  the union of the true physical body outline (a different, smaller
  number than the `body_width`/`body_size` params used for the
  intentionally oversized F.SilkS outline) and one pad-bounding-box arm
  per side that has pads, both independently expanded by a flat
  0.25mm margin. Verified exactly against SOIC-8, SOIC-14, LQFP-32, and
  LQFP-48 reference footprints (SOIC-14's carries the same ~0.02mm
  approximation already accepted for SOIC's silk body). The
  rectangle-union math lives in `kicad_fpdb/rect_union.py`
  (`union_outline`), generic over any number of margin-expanded
  rectangles — see
  `docs/superpowers/specs/2026-09-15-stepped-courtyard-design.md`. Chip
  passives (R/C) needed no shape change, just their real per-variant
  flat margin (0.15mm for R-0402, 0.25mm for R-0603/R-0805/C-0603)
  instead of the generic 0.5mm fallback. DIP's courtyard (already real)
  is unaffected.
```

- [ ] **Step 4: Add today's CHANGELOG.md entry**

Per this project's changelog convention (one entry per calendar day,
not per version bump), add a new dated block at the top of
`CHANGELOG.md`, right after the `# Changes` heading:

```markdown
2026-09-15 v0.0.9:

* Gave SOIC and QFP their real stepped `F.CrtYd` courtyard shape (union
  of the true physical body outline and one pad-bbox arm per side,
  each expanded by a flat 0.25mm margin) via a new generic
  `kicad_fpdb/rect_union.py` rectangle-union utility, verified exactly
  against SOIC-8, SOIC-14, LQFP-32, and LQFP-48 real reference
  footprints.
* Fixed chip-passive (R/C) courtyard margins to their real per-variant
  values (0.15mm for R-0402, 0.25mm for R-0603/R-0805/C-0603),
  replacing the generic flat 0.5mm fallback — a data-only change, no
  shape change needed.
* Added a design spec for the above
  (`docs/superpowers/specs/2026-09-15-stepped-courtyard-design.md`).

```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
Log v0.0.9: real stepped SOIC/QFP courtyards, chip-passive margin fix

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** rect_union utility (Task 1), SOIC/QFP stepped
  courtyard wiring (Task 2) and data (Task 3), chip-passive margin fix
  (Task 4), visual verification + docs (Task 5) — every section of the
  design spec has a task.
- **Type consistency:** `union_outline`'s signature is defined once in
  Task 1 and used identically (same param/return shape) in Task 2; the
  three new `_add_outline` params (`courtyard_body_width`,
  `courtyard_body_margin`, `courtyard_body_size`) are defined in Task 2
  and only ever set via YAML data in Tasks 3-4, never referenced by a
  different name later.
- **DIP regression guard:** explicit test in Task 2
  (`test_add_outline_without_courtyard_body_params_keeps_plain_rect`)
  and the full-suite run in every task's Step 5/6 area protect DIP's
  existing courtyard from any accidental change.
