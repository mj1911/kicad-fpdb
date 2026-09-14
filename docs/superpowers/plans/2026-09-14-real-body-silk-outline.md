# Real Body-Derived Silk Outline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the F.SilkS body outline for DIP and SOIC footprints reflect real physical body dimensions (a per-family `body_width`/`body_margin`), instead of the current generic pad-bounding-box + flat margin.

**Architecture:** `_add_outline()` in `kicad_fpdb/pipeline.py` gains two optional parameters (`body_width`, `body_margin`). When given, it computes the silk rectangle from pad *centers* (width centered on the pad-row centerline, length from first/last pad center ± margin) instead of the pad-edge-inclusive bounding box. `generate_footprint()` pulls these two values out of the resolved descriptor params (they're outline inputs, not generator inputs) and passes them through. DIP and SOIC declare real values for them in `data/kicad-fpdb.yaml`; every other family (QFP, chip passives) leaves them undeclared and keeps today's generic behavior untouched.

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q` (this machine's project venv — see `CLAUDE.md`'s cross-machine notes if that path doesn't exist here).

## Global Constraints

- This is a **symbolic** approximation, not exact per-footprint dimensional matching — small real-world deviations (documented in the spec, `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`) are acceptable and must not be "fixed" by adding per-pin-count special cases.
- Only F.SilkS changes. Courtyard (F.CrtYd) and the pin-1 marker triangle keep using the existing pad-bounding-box logic, unchanged.
- Only DIP and SOIC get real `body_width`/`body_margin` values in this plan. QFP and chip passives (R/C) must keep producing byte-identical output to before this change — do not add these keys to their YAML entries.
- Exact real-world values to use (from the spec):
  - DIP: `body_width` = `{narrow: 5.3, regular: 6.47, wide: 12.92}`, `body_margin` = `1.33`.
  - SOIC: `body_width` = `4.12`, `body_margin` = `0.64`.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Teach `_add_outline` to compute a body-derived silk rectangle

**Files:**
- Modify: `kicad_fpdb/pipeline.py:39-72` (the `_add_outline` function)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: nothing new — uses the existing `Line`, `Rect`, `Poly`, `pad_bounding_box` imports already in `pipeline.py`, and the existing `_dip16_geometry()` test helper in `tests/test_pipeline_outline.py`.
- Produces: `_add_outline(geometry, body_width: float | None = None, body_margin: float | None = None) -> None`. When both are given (not `None`), the F.SilkS rectangle is computed from pad centers instead of `pad_bounding_box`. When either is `None`, behavior is byte-identical to today (pad bbox + `SILK_MARGIN_MM`). This signature and default are relied on by Task 2.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py` (after the existing `test_add_outline_produces_silkscreen_body_rect` test):

```python
def test_add_outline_with_body_params_matches_real_dip16_narrow():
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4
    xs = sorted({round(x, 5) for line in silk_lines for x in (line.start[0], line.end[0])})
    ys = sorted({round(y, 5) for line in silk_lines for y in (line.start[1], line.end[1])})
    # Real DIP-16_W7.62mm.kicad_mod silk rect is exactly (1.16, -1.33) to
    # (6.46, 19.11) — pad centers span x=0..7.62, y=0..17.78.
    assert xs == pytest.approx([1.16, 6.46])
    assert ys == pytest.approx([-1.33, 19.11])


def test_add_outline_without_body_params_keeps_generic_margin_behavior():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    xs = sorted({round(x, 5) for line in silk_lines for x in (line.start[0], line.end[0])})
    ys = sorted({round(y, 5) for line in silk_lines for y in (line.start[1], line.end[1])})
    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); generic silk margin is 0.2mm.
    assert xs == pytest.approx([-1.0, 8.62])
    assert ys == pytest.approx([-1.0, 18.78])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_add_outline_with_body_params_matches_real_dip16_narrow` FAILS with `TypeError: _add_outline() got an unexpected keyword argument 'body_width'`. `test_add_outline_without_body_params_keeps_generic_margin_behavior` PASSES already (it exercises unchanged behavior) — that's fine, it's here to lock the contract before Step 3 touches the function.

- [ ] **Step 3: Implement the body-derived rectangle**

Replace the `_add_outline` function in `kicad_fpdb/pipeline.py` (lines 39-72) with:

```python
def _pad_center_extent(pads, axis: int) -> tuple[float, float]:
    values = [p.at[axis] for p in pads]
    return min(values), max(values)


def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None) -> None:
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

This only changes how `sx0, sy0, sx1, sy1` are computed; everything downstream (the four silk lines, the pin-1 marker) is untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS, including the two new ones and the three pre-existing ones (`test_add_outline_produces_courtyard_rect`, `test_add_outline_produces_silkscreen_body_rect`, `test_add_outline_produces_pin1_marker_triangle`, `test_generate_footprint_includes_outline_geometry`) — none of those call `_add_outline` with the new params, so they exercise the unchanged fallback path and must be unaffected.

- [ ] **Step 5: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (same count as before this task, plus the 2 new ones).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Let _add_outline compute a body-derived F.SilkS rectangle

Adds optional body_width/body_margin params so the silk outline can be
sized/positioned from real physical body dimensions instead of the pad
bounding box, when a family declares them. Falls back to the existing
generic behavior otherwise.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire real body dimensions through for DIP and SOIC

**Files:**
- Modify: `data/kicad-fpdb.yaml` (DIP and SOIC entries)
- Modify: `kicad_fpdb/pipeline.py:86-97` (the `generate_footprint` function)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_outline(geometry, body_width=None, body_margin=None)` from Task 1. Also touches the `_dip16_geometry()` test helper defined in `tests/test_pipeline_outline.py` (used by Task 1's tests and the pre-existing tests in that file) — adding `body_width`/`body_margin` to the DIP YAML makes `resolved.params` include them, so anything that forwards `resolved.params` straight into a generator function (this helper included) must pop them first, same as `generate_footprint` does.
- Produces: `generate_footprint()` continues to have the same public signature and return type (a `str` of `.kicad_mod` text) — no change visible to callers. Internally it now strips `body_width`/`body_margin` out of `resolved.params` before calling the generator function, so generator functions never receive these two keys.

- [ ] **Step 1: Write the failing tests**

`tests/test_pipeline_outline.py` already defines `FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"` at module level (line 9) and already imports `generate_footprint` (line 7) — use those, no new imports needed. Add these tests:

```python
def test_generate_footprint_dip16_narrow_silk_matches_real_body():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(start 1.16 -1.33)" in text
    assert "(end 6.46 -1.33)" in text
    assert "(end 6.46 19.11)" in text
    assert "(end 1.16 19.11)" in text


def test_generate_footprint_dip16_regular_silk_matches_real_body():
    text = generate_footprint("DIP-16 r", FAMILY_TREE_PATH, name="DIP16R_TEST")
    assert "(start 1.845 -1.33)" in text
    assert "(end 8.315 -1.33)" in text


def test_generate_footprint_soic8_silk_matches_body_formula():
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert "(start -2.06 -2.545)" in text
    assert "(end 2.06 -2.545)" in text
    assert "(end 2.06 2.545)" in text


def test_generate_footprint_does_not_leak_body_params_to_generator():
    # If pipeline.py forgot to pop body_width/body_margin before calling
    # the generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert text  # got here without raising
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: the three `_matches_real_*`/`_matches_body_formula` tests FAIL (assertion errors — the yaml doesn't declare `body_width`/`body_margin` yet, so `generate_footprint` still uses the generic fallback). `test_generate_footprint_does_not_leak_body_params_to_generator` PASSES already (nothing to leak yet) — that's expected; it becomes a meaningful regression guard once Step 3 adds the yaml keys.

- [ ] **Step 3: Add body dimensions to the YAML data**

In `data/kicad-fpdb.yaml`, change the `DIP` entry's `params` block (currently lines 11-18) to:

```yaml
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    body_width: {narrow: 5.3, regular: 6.47, wide: 12.92}
    body_margin: 1.33
    pad_size: [1.6, 1.6]
    pad_shape: dip_pin1_marker
    pad_type: thru_hole
    drill: 0.8
    centered: false
```

And the `SOIC` entry's `params` block (currently lines 24-30) to:

```yaml
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

Do not touch the `R`, `C`, or `QFP` entries — they must not gain these keys.

- [ ] **Step 4: Fix the `_dip16_geometry()` test helper**

After Step 3, `resolve_descriptor(tree, parse_descriptor("DIP-16"))` returns params that now include `body_width`/`body_margin`. The `_dip16_geometry()` helper at the top of `tests/test_pipeline_outline.py` (used by every test in Task 1, plus the pre-existing tests already in this file) calls `GENERATORS[resolved.generator](**resolved.params)` directly — `dual_row_grid()` doesn't accept those two keys, so every test using this helper would now raise `TypeError` unless it's fixed to pop them first, matching what `generate_footprint` itself does. Replace the helper:

```python
def _dip16_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("DIP-16"))
    params = dict(resolved.params)
    params.pop("body_width", None)
    params.pop("body_margin", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "DIP16_TEST"
    return geometry
```

- [ ] **Step 5: Pop the new params out before calling the generator**

In `kicad_fpdb/pipeline.py`, replace the `generate_footprint` function (currently lines 86-97) with:

```python
def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    params = dict(resolved.params)
    body_width = params.pop("body_width", None)
    body_margin = params.pop("body_margin", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS.

- [ ] **Step 7: Run the full suite, including the KiCad-dependent regression suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass. In particular `tests/test_pipeline_regression.py` (parametrized over every case in `kicad_fpdb/reference_cases.py`, including `DIP-16`, `DIP-14`, `DIP-18`, `DIP-16 r`, `SOIC-8`, `SOIC-14`, and every `R`/`C`/`QFP` case) must still pass — it only checks pad geometry, not silk geometry, so it's unaffected by this change, but it's the test that would catch an accidental change to pad placement if the yaml edit went wrong. If this suite is skipped (KiCad footprints not present on this machine), note that in your report rather than assuming it ran.

- [ ] **Step 8: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Give DIP and SOIC real body_width/body_margin, wire through pipeline

DIP's body_width is keyed by width class (narrow/regular/wide) matching
row_spacing's existing pattern; body_margin is a single constant for
each family. generate_footprint() now strips these two outline-only
keys out of the resolved params before calling the generator function.

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

- [ ] **Step 2: Open and visually check the DIP and SOIC cases**

Open `renders/review.html` in a browser (e.g. `xdg-open renders/review.html`). For each of the DIP-16, DIP-14, DIP-18, DIP-16 r, SOIC-8, and SOIC-14 cases, compare the Generated and Reference panels: the Generated panel's silk rectangle should now sit inset within the pad rows (not wrapping around them), visually proportioned like the Reference panel's real body outline. Exact pixel match isn't expected — the reference panel still has KiCad's own pin-1 notch arc, which this project intentionally replaces with the filled triangle marker.

If any case looks wrong (e.g. the silk rectangle doesn't appear, or is wildly mis-sized), stop and re-check Task 1/2's math before proceeding — do not paper over it here.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the bullet that currently reads (in the "Claude-isms below" section):

```
* Generated footprints now also have generic courtyard (`F.CrtYd`) and
  silkscreen body outline (`F.SilkS`, with a pin-1 corner marker)
  geometry, built purely from the pad bounding box — works the same way
  for any generator. This is a generic convention, not a per-family match
  to real KiCad's own outline styles (see `kicad_fpdb.pipeline._add_outline`),
  and is verified visually via the review tool rather than an automated
  geometry diff, per the spec's stated approach for outline geometry.
```

Replace it with:

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

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document real body-derived silk outline for DIP/SOIC

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
