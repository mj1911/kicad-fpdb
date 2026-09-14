# QFP Corner-Mark Silk Outline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace QFP's generic pad-bbox F.SilkS rectangle with four corner-mark L-brackets, matching real KiCad's own QFP silk convention (real coordinates verified against `LQFP-32_7x7mm_P0.8mm.kicad_mod` and `LQFP-48_7x7mm_P0.5mm.kicad_mod`).

**Architecture:** `_add_outline()` in `kicad_fpdb/pipeline.py` gains a third optional parameter, `body_size`. When given (and `body_width`/`body_margin` are not), it computes a square body centered on the pad centroid and calls a new `_add_corner_marks()` helper that draws two short `Line`s per corner instead of a full rectangle. `generate_footprint()` pulls `body_size` out of resolved params the same way it already does for `body_width`/`body_margin`. QFP-32 and QFP-48 declare the real value (7.22mm) in `data/kicad-fpdb.yaml`; every other family is untouched.

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q`.

## Global Constraints

- This is a **symbolic** approximation, not exact per-footprint dimensional matching: real KiCad uses a 0.3mm corner-mark leg for QFP-32 and 0.45mm for QFP-48; this project uses one fixed 0.3mm constant for both. Do not add per-variant leg-length special-casing.
- Only F.SilkS changes. Courtyard (F.CrtYd) and the pin-1 marker triangle keep their existing logic, unchanged — the pin-1 marker already computes its anchor corner generically from whatever `sx0/sy0/sx1/sy1` the active outline mode produces, so it needs no code change, only verification that it still behaves correctly.
- Only QFP-32 and QFP-48 get `body_size` in this plan. Do not touch DIP, SOIC, R, or C's YAML entries or behavior.
- Real value to use (from the spec, `docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md`): `body_size: 7.22` for both QFP-32 and QFP-48. New corner-mark leg-length constant: `CORNER_MARK_MM = 0.3`.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Add `_add_corner_marks` and wire `body_size` into `_add_outline`

**Files:**
- Modify: `kicad_fpdb/pipeline.py` (constants block near line 25-30, and the `_add_outline` function at lines 44-90)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: nothing new — uses the existing `Line`, `Rect`, `Poly`, `pad_bounding_box`, `_pad_center_extent` already in `pipeline.py`.
- Produces: `_add_outline(geometry, body_width=None, body_margin=None, body_size=None)`. When `body_size` is given and `body_width`/`body_margin` are not, the F.SilkS rectangle-drawing path is replaced with four corner-mark brackets via a new `_add_corner_marks(geometry, sx0, sy0, sx1, sy1)` helper — relied on by Task 2. Existing callers that only ever passed `body_width`/`body_margin` or nothing are unaffected (`body_size` defaults to `None`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline_outline.py`, right after the existing `_dip16_geometry()` helper (before `test_add_outline_produces_courtyard_rect`):

```python
def _qfp32_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("QFP-32"))
    params = dict(resolved.params)
    params.pop("body_size", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "QFP32_TEST"
    return geometry
```

Then add this test anywhere after that helper (e.g. right after `test_add_outline_produces_pin1_marker_triangle`):

```python
def test_add_outline_with_body_size_draws_corner_marks():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    # 4 corners x 2 legs each = 8 short lines, no full-perimeter rectangle.
    assert len(silk_lines) == 8

    # Real LQFP-32_7x7mm_P0.8mm.kicad_mod corner marks are at (±3.61, ±3.61)
    # with 0.3mm legs — this project uses a fixed 0.3mm leg for all QFP.
    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in silk_lines for pt in (line.start, line.end)}
    assert (-3.61, -3.61) in endpoints
    assert (-3.31, -3.61) in endpoints
    assert (-3.61, -3.31) in endpoints
    assert (3.61, -3.61) in endpoints
    assert (3.31, -3.61) in endpoints
    assert (3.61, -3.31) in endpoints
    assert (3.61, 3.61) in endpoints
    assert (3.31, 3.61) in endpoints
    assert (3.61, 3.31) in endpoints
    assert (-3.61, 3.61) in endpoints
    assert (-3.31, 3.61) in endpoints
    assert (-3.61, 3.31) in endpoints


def test_add_outline_with_body_size_keeps_pin1_marker():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22)

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" (quad_perimeter's left side, first pin) sits at
    # (-4.175, -2.8), nearest to the (-3.61, -3.61) corner.
    tip, base1, base2 = marker.points
    assert tip == pytest.approx((-3.61, -3.61))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: both new tests FAIL with `TypeError: _add_outline() got an unexpected keyword argument 'body_size'`.

- [ ] **Step 3: Implement corner marks**

In `kicad_fpdb/pipeline.py`, add the new constant next to the existing outline constants (near line 30):

```python
# Length, in mm, of each leg of a QFP-style corner-mark bracket. Real
# KiCad varies this per package (0.3mm for LQFP-32, 0.45mm for LQFP-48);
# this project uses one fixed value for all QFP variants, consistent
# with the "symbolic, not exact" approach documented in
# docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md.
CORNER_MARK_MM = 0.3
```

Add a new helper function right after `_pad_center_extent`:

```python
def _add_corner_marks(geometry, sx0: float, sy0: float, sx1: float, sy1: float) -> None:
    corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
    for cx, cy in corners:
        x_dir = 1.0 if cx == sx0 else -1.0
        y_dir = 1.0 if cy == sy0 else -1.0
        geometry.lines.append(Line(start=(cx, cy), end=(cx + x_dir * CORNER_MARK_MM, cy), layer="F.SilkS"))
        geometry.lines.append(Line(start=(cx, cy), end=(cx, cy + y_dir * CORNER_MARK_MM), layer="F.SilkS"))
```

Then modify `_add_outline` (replace the whole function):

```python
def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    cy0x, cy0y = min_x - COURTYARD_MARGIN_MM, min_y - COURTYARD_MARGIN_MM
    cy1x, cy1y = max_x + COURTYARD_MARGIN_MM, max_y + COURTYARD_MARGIN_MM
    geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))

    if body_width is not None and body_margin is not None:
        # Real body dimensions: a physical package constant, independent of
        # the pad bounding box. Width is centered on the pad-row centerline;
        # length runs from the first/last pad *center* (not pad edge) plus
        # a fixed margin. See docs/superpowers/specs/2026-09-14-real-body-
        # silk-outline-design.md for the derivation.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        sx0, sx1 = center_x - body_width / 2, center_x + body_width / 2
        sy0, sy1 = min_py - body_margin, max_py + body_margin
        corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
        for i in range(4):
            start, end = corners[i], corners[(i + 1) % 4]
            geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))
    elif body_size is not None:
        # Real square body size (a physical constant, independent of pad
        # position), centered on the pad centroid. See docs/superpowers/
        # specs/2026-09-14-qfp-corner-mark-silk-design.md.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        center_y = (min_py + max_py) / 2
        half = body_size / 2
        sx0, sx1 = center_x - half, center_x + half
        sy0, sy1 = center_y - half, center_y + half
        _add_corner_marks(geometry, sx0, sy0, sx1, sy1)
    else:
        sx0, sy0 = min_x - SILK_MARGIN_MM, min_y - SILK_MARGIN_MM
        sx1, sy1 = max_x + SILK_MARGIN_MM, max_y + SILK_MARGIN_MM
        corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
        for i in range(4):
            start, end = corners[i], corners[(i + 1) % 4]
            geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))

    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pad1 is not None:
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

Note this factors the previous single "draw 4 rectangle sides" block into two identical copies (one in the `body_width`/`body_margin` branch, one in the `else` branch) rather than a shared sub-function — this mirrors the existing code structure (each branch already independently computed its own `sx0/sy0/sx1/sy1`) and keeps this change a minimal, reviewable diff. Do not refactor further in this task.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS, including the two new ones and every pre-existing test in this file (none of the DIP-16 tests pass `body_size`, so they're unaffected).

- [ ] **Step 5: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (67 baseline + 2 new = 69).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Let _add_outline draw QFP-style corner-mark brackets

Adds an optional body_size param and a new _add_corner_marks helper:
when body_size is given (and body_width/body_margin are not), the
F.SilkS outline is four small corner brackets instead of a full
rectangle, matching real KiCad's own QFP silk convention. The pin-1
marker triangle is unaffected — it already anchors generically to
whichever corner the active outline mode produces.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire real body_size through for QFP-32 and QFP-48

**Files:**
- Modify: `data/kicad-fpdb.yaml` (QFP-32 and QFP-48 entries)
- Modify: `kicad_fpdb/pipeline.py` (the `generate_footprint` function)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_outline(geometry, body_width=None, body_margin=None, body_size=None)` and `_qfp32_geometry()` from Task 1.
- Produces: `generate_footprint()` keeps the same public signature and return type — no change visible to callers. Internally it now also strips `body_size` out of `resolved.params` before calling the generator function.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_qfp32_silk_matches_real_corner_marks():
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert "(start -3.61 -3.61)" in text
    assert "(end -3.31 -3.61)" in text
    assert "(end -3.61 -3.31)" in text


def test_generate_footprint_qfp48_silk_matches_real_corner_position():
    text = generate_footprint("QFP-48", FAMILY_TREE_PATH, name="QFP48_TEST")
    # Same 7x7mm body as QFP-32 (per the spec, both real footprints share
    # this corner position); leg length is this project's fixed 0.3mm,
    # not real KiCad's 0.45mm for this specific package.
    assert "(start -3.61 -3.61)" in text
    assert "(end -3.31 -3.61)" in text


def test_generate_footprint_does_not_leak_body_size_to_generator():
    # If pipeline.py forgot to pop body_size before calling the generator,
    # this raises TypeError("unexpected keyword argument").
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert text  # got here without raising
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_generate_footprint_qfp32_silk_matches_real_corner_marks` and `test_generate_footprint_qfp48_silk_matches_real_corner_position` FAIL (the yaml doesn't declare `body_size` yet, so `generate_footprint` still uses the generic pad-bbox fallback for QFP). `test_generate_footprint_does_not_leak_body_size_to_generator` PASSES already (nothing to leak yet) — expected; it becomes meaningful once Step 3 lands.

- [ ] **Step 3: Add body_size to the YAML data**

In `data/kicad-fpdb.yaml`, change the `QFP-32` and `QFP-48` entries (currently):

```yaml
QFP:
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_offset: 4.175, pad_size: [1.5, 0.5]}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_offset: 4.1625, pad_size: [1.475, 0.3]}
```

to:

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

Do not touch `DIP`, `SOIC`, `R`, or `C`.

- [ ] **Step 4: Pop `body_size` out before calling the generator**

In `kicad_fpdb/pipeline.py`, modify `generate_footprint` (replace the whole function):

```python
def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    params = dict(resolved.params)
    body_width = params.pop("body_width", None)
    body_margin = params.pop("body_margin", None)
    body_size = params.pop("body_size", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Run the full suite, including the KiCad-dependent regression suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass. `tests/test_pipeline_regression.py` (parametrized over every case including `QFP-32` and `QFP-48`) must still pass — it only checks pad geometry, unaffected by this change. If it's skipped on this machine (KiCad footprints not present), say so in your report rather than assuming it ran.

- [ ] **Step 7: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Give QFP-32/QFP-48 real body_size, wire through pipeline

Both are 7x7mm packages in real KiCad, sharing the same corner-mark
position (body_size: 7.22). generate_footprint() now strips body_size
out of the resolved params before calling the generator function, same
pattern as body_width/body_margin.

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

- [ ] **Step 2: Open and visually check the QFP cases**

Open `renders/review.html` (e.g. `xdg-open renders/review.html`). For QFP-32 and QFP-48, the Generated panel should now show four small corner brackets near the body corners (not a full rectangle), roughly matching the Reference panel's real corner marks — the Reference panel's marks may look slightly longer for QFP-48 (real 0.45mm leg vs this project's fixed 0.3mm), which is expected per the spec's accepted non-goal.

If a case looks wrong (e.g. no marks appear, or they're positioned outside/overlapping the pads incorrectly), stop and re-check Task 1/2's math before proceeding.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the bullet (in the "Claude-isms below" section) that currently reads:

```
* Generated footprints have courtyard (`F.CrtYd`) and silkscreen body
  outline (`F.SilkS`, with a pin-1 corner marker) geometry (see
  `kicad_fpdb.pipeline._add_outline`). Courtyard is still generic
  (pad bounding box + margin) for every family. The F.SilkS rectangle
  is generic for QFP and chip passives (R/C), but for DIP and SOIC it's
  now derived from real physical body dimensions (`body_width`/
  `body_margin` in `data/kicad-fpdb.yaml`) instead of the pad bounding
  box — DIP's body_width is keyed by width class (narrow/regular/wide),
  matching real KiCad almost exactly (SOIC's margin is an averaged
  approximation, off by ~0.01-0.02mm from real values — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`).
  Verified visually via the review tool rather than an automated
  geometry diff, per the spec's stated approach for outline geometry.
```

Replace it with:

```
* Generated footprints have courtyard (`F.CrtYd`) and silkscreen body
  outline (`F.SilkS`, with a pin-1 corner marker) geometry (see
  `kicad_fpdb.pipeline._add_outline`). Courtyard is still generic
  (pad bounding box + margin) for every family. The F.SilkS geometry is
  generic (pad bounding box + margin) only for chip passives (R/C) now.
  DIP and SOIC draw a real body-derived rectangle (`body_width`/
  `body_margin` in `data/kicad-fpdb.yaml`) — DIP's body_width is keyed
  by width class (narrow/regular/wide), matching real KiCad almost
  exactly (SOIC's margin is an averaged approximation, off by
  ~0.01-0.02mm — see `docs/superpowers/specs/2026-09-14-real-body-silk-
  outline-design.md`). QFP draws real corner-mark brackets instead of a
  rectangle (`body_size` in `data/kicad-fpdb.yaml`, both current
  variants sharing 7.22mm since both are 7x7mm packages), matching real
  KiCad's own QFP silk convention except for a fixed 0.3mm bracket leg
  length shared by all QFP variants (real values vary — see
  `docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md`).
  Verified visually via the review tool rather than an automated
  geometry diff, per the spec's stated approach for outline geometry.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document QFP corner-mark silk outline

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
