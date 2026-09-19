# Chip-Passive Two-Line Silk Outline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace R/C's generic pad-bbox F.SilkS rectangle with the real two-line convention KiCad's own chip-resistor/capacitor footprints use (real coordinates verified against `R_0402_1005Metric.kicad_mod`, `R_0603_1608Metric.kicad_mod`, `R_0805_2012Metric.kicad_mod`, `C_0603_1608Metric.kicad_mod`).

**Architecture:** `_add_outline()` in `kicad_fpdb/pipeline.py` gains a fourth mode, controlled by two new optional parameters, `silk_y` and `silk_half_length`. When both are given (and `body_width`/`body_margin`/`body_size` are not), it draws exactly two horizontal `Line`s centered on the pad centroid instead of a rectangle or corner marks. `generate_footprint()` pops both from resolved params the same way it already does for `body_width`/`body_margin`/`body_size`/`pin1_marker`. Each of `R-0402`, `R-0603`, `R-0805`, and `C-0603` declares its own exact real values in `data/kicad-fpdb.yaml` (unlike DIP/QFP, there's no shared value across variants here, so each child declares both params itself rather than inheriting from a family root).

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q`.

## Global Constraints

- Exact real values to use (from the spec, `docs/superpowers/specs/2026-09-14-chip-passive-silk-lines-design.md`):
  - `R-0402`: `silk_y: 0.38`, `silk_half_length: 0.153641`
  - `R-0603`: `silk_y: 0.5225`, `silk_half_length: 0.237258`
  - `R-0805`: `silk_y: 0.735`, `silk_half_length: 0.227064`
  - `C-0603`: `silk_y: 0.51`, `silk_half_length: 0.14058`
- This mode does not compute a body-corner rectangle at all (unlike every other mode in `_add_outline`), so it must not be combined with `pin1_marker=True` — R/C already declare `pin1_marker: false`, so this is a non-issue in practice, but the code must not silently produce wrong geometry if that ever changes; a comment documenting the constraint is enough (per the spec's explicit non-goal — do not add extra guard code beyond what the spec describes).
- Only `R-0402`, `R-0603`, `R-0805`, `C-0603` get these new params. DIP, SOIC, and QFP's YAML entries and generated output must be byte-identical to before this change.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Add the two-line silk mode to `_add_outline`

**Files:**
- Modify: `kicad_fpdb/pipeline.py` (the `_add_outline` function, currently lines 59-121)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `kicad_fpdb.generators.two_pad.two_pad_chip(pad_pitch, pad_size)` (already used elsewhere in the codebase) to build a test geometry.
- Produces: `_add_outline(geometry, body_width=None, body_margin=None, body_size=None, pin1_marker=True, silk_y=None, silk_half_length=None)`. When `silk_y` and `silk_half_length` are both given (and `body_width`/`body_margin`/`body_size` are not), the F.SilkS geometry is two horizontal lines instead of a rectangle/corner-marks. Relied on by Task 2.

- [ ] **Step 1: Write the failing test**

Add near the top of `tests/test_pipeline_outline.py`, after the existing `_qfp32_geometry()` helper, a new import and helper:

```python
from kicad_fpdb.generators.two_pad import two_pad_chip


def _r0603_geometry():
    geometry = two_pad_chip(pad_pitch=1.65, pad_size=(0.8, 0.95))
    geometry.name = "R0603_TEST"
    return geometry
```

Then add this test anywhere after that helper:

```python
def test_add_outline_with_silk_line_params_draws_two_lines():
    geometry = _r0603_geometry()
    _add_outline(geometry, silk_y=0.5225, silk_half_length=0.237258, pin1_marker=False)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 2

    ys = sorted({round(line.start[1], 6) for line in silk_lines})
    assert ys == pytest.approx([-0.5225, 0.5225])
    for line in silk_lines:
        assert line.start[1] == line.end[1]
        xs = sorted([round(line.start[0], 6), round(line.end[0], 6)])
        assert xs == pytest.approx([-0.237258, 0.237258])

    # No pin-1 marker (pin1_marker=False, matching how R/C actually
    # declare it), and only the courtyard rect — no F.SilkS rectangle.
    assert len(geometry.polys) == 0
    assert len(geometry.rects) == 1
    assert geometry.rects[0].layer == "F.CrtYd"
```

Note the `pin1_marker=False` is required here: this new mode never computes the `sx0/sy0/sx1/sy1` corner points every other mode uses for the pin-1 marker, so calling it with the default `pin1_marker=True` would raise `NameError`. This matches how R/C actually use it in production (they already declare `pin1_marker: false`), and is the spec's explicitly accepted limitation, not something to work around here.

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: FAILS with `TypeError: _add_outline() got an unexpected keyword argument 'silk_y'`.

- [ ] **Step 3: Implement the two-line mode**

In `kicad_fpdb/pipeline.py`, change the `_add_outline` signature:

```python
def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True,
                  silk_y: float | None = None, silk_half_length: float | None = None) -> None:
```

Add a new `elif` branch after the existing `elif body_size is not None:` branch (before the final `else:`):

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
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        center_y = (min_py + max_py) / 2
        for y in (center_y - silk_y, center_y + silk_y):
            geometry.lines.append(Line(
                start=(center_x - silk_half_length, y),
                end=(center_x + silk_half_length, y),
                layer="F.SilkS",
            ))
```

Leave the existing `if body_width...`, `elif body_size...`, and final `else:` branches, and the pin-1 marker block after them, exactly as they are.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS, including the new one and every pre-existing test in this file (none of them pass `silk_y`/`silk_half_length`, so they're unaffected).

- [ ] **Step 5: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (77 baseline + 1 new = 78).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Let _add_outline draw a real two-line silk outline for chip passives

Adds optional silk_y/silk_half_length params: when both are given, the
F.SilkS geometry is two short horizontal lines instead of a rectangle,
matching real KiCad's own chip-resistor/capacitor silk convention
(the component body is always smaller than its pads, so a box around
the pads shows nothing useful).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire real silk-line values through for R and C

**Files:**
- Modify: `data/kicad-fpdb.yaml` (`R-0402`, `R-0603`, `R-0805`, `C-0603` entries)
- Modify: `kicad_fpdb/pipeline.py` (the `generate_footprint` function)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_outline(geometry, ..., silk_y=None, silk_half_length=None)` from Task 1.
- Produces: `generate_footprint()` keeps the same public signature and return type — no change visible to callers. Internally it now also strips `silk_y`/`silk_half_length` out of `resolved.params` before calling the generator function.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_r0402_silk_matches_real_lines():
    text = generate_footprint("R-0402", FAMILY_TREE_PATH, name="R0402_TEST")
    assert "(start -0.153641 -0.38)" in text
    assert "(end 0.153641 -0.38)" in text
    assert "(start -0.153641 0.38)" in text
    assert "(end 0.153641 0.38)" in text


def test_generate_footprint_r0603_silk_matches_real_lines():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "(start -0.237258 -0.5225)" in text
    assert "(end 0.237258 -0.5225)" in text


def test_generate_footprint_r0805_silk_matches_real_lines():
    text = generate_footprint("R-0805", FAMILY_TREE_PATH, name="R0805_TEST")
    assert "(start -0.227064 -0.735)" in text
    assert "(end 0.227064 -0.735)" in text


def test_generate_footprint_c0603_silk_matches_real_lines():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "(start -0.14058 -0.51)" in text
    assert "(end 0.14058 -0.51)" in text


def test_generate_footprint_r0603_has_only_courtyard_rect():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text.count("(fp_rect") == 1


def test_generate_footprint_does_not_leak_silk_line_params_to_generator():
    # If pipeline.py forgot to pop silk_y/silk_half_length before calling
    # the generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text  # got here without raising
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_generate_footprint_r0402_silk_matches_real_lines`, `test_generate_footprint_r0603_silk_matches_real_lines`, `test_generate_footprint_r0805_silk_matches_real_lines`, and `test_generate_footprint_c0603_silk_matches_real_lines` FAIL (the yaml doesn't declare `silk_y`/`silk_half_length` yet, so `generate_footprint` still uses the generic pad-bbox fallback). `test_generate_footprint_r0603_has_only_courtyard_rect` and `test_generate_footprint_does_not_leak_silk_line_params_to_generator` PASS already (the fallback also produces no extra `fp_rect`, and there's nothing to leak yet) — expected; both remain meaningful regression guards once Step 3 lands.

- [ ] **Step 3: Add silk_y/silk_half_length to the YAML data**

In `data/kicad-fpdb.yaml`, change the `R` entry's children (currently):

```yaml
R:
  params:
    pin1_marker: false
  children:
    R-0402:
      generator: two_pad_chip
      params: {pad_pitch: 1.02, pad_size: [0.54, 0.64]}
    R-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.65, pad_size: [0.8, 0.95]}
    R-0805:
      generator: two_pad_chip
      params: {pad_pitch: 1.825, pad_size: [1.025, 1.4]}
```

to:

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

And the `C` entry's children (currently):

```yaml
C:
  params:
    pin1_marker: false
  children:
    C-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.55, pad_size: [0.9, 0.95]}
```

to:

```yaml
C:
  params:
    pin1_marker: false
  children:
    C-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.55, pad_size: [0.9, 0.95], silk_y: 0.51, silk_half_length: 0.14058}
```

Do not touch `DIP`, `SOIC`, or `QFP`.

- [ ] **Step 4: Pop the new params out before calling the generator**

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
    pin1_marker = params.pop("pin1_marker", True)
    silk_y = params.pop("silk_y", None)
    silk_half_length = params.pop("silk_half_length", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, silk_y=silk_y, silk_half_length=silk_half_length)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Run the full suite, including the KiCad-dependent regression suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass. `tests/test_pipeline_regression.py` (parametrized over every case including `R-0402`, `R-0603`, `R-0805`, `C-0603`) must still pass — it only checks pad geometry, unaffected by this change. If it's skipped on this machine (KiCad footprints not present), say so in your report rather than assuming it ran.

- [ ] **Step 7: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Give R/C real silk_y/silk_half_length, wire through pipeline

Each variant's two constants are copied verbatim from its real
reference footprint (no shared formula holds across chip-passive
sizes). generate_footprint() now strips both out of the resolved
params before calling the generator function, same pattern as the
other outline-only params.

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

- [ ] **Step 2: Visually check the R and C cases**

Open `renders/review.html` (e.g. `xdg-open renders/review.html`). For R-0402, R-0603, R-0805, and C-0603, the Generated panel should now show two short horizontal lines (one above, one below the pads) instead of a box, closely matching the Reference panel — since these values are copied verbatim from the real footprints, this should be a near-exact visual match, not an approximation. DIP-16/14/18/16r, SOIC-8/14, and QFP-32/48 should be unchanged.

If a case looks wrong (lines missing, positioned oddly, or a box still appears), stop and re-check Task 1/2 before proceeding.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the bullet (in the "Claude-isms below" section) that currently reads:

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

Replace it with:

```
* Generated footprints have courtyard (`F.CrtYd`) and silkscreen body
  outline (`F.SilkS`, with a pin-1 corner marker on families that use
  one) geometry (see `kicad_fpdb.pipeline._add_outline`). Courtyard is
  still generic (pad bounding box + margin) for every family; no
  family uses the generic pad-bbox F.SilkS rectangle anymore. DIP and
  SOIC draw a real body-derived rectangle (`body_width`/`body_margin`
  in `data/kicad-fpdb.yaml`) — DIP's body_width is keyed by width class
  (narrow/regular/wide), matching real KiCad almost exactly (SOIC's
  margin is an averaged approximation, off by ~0.01-0.02mm — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`).
  QFP draws real corner-mark brackets instead of a rectangle
  (`body_size` in `data/kicad-fpdb.yaml`, both current variants sharing
  7.22mm since both are 7x7mm packages), matching real KiCad's own QFP
  silk convention except for a fixed 0.3mm bracket leg length shared by
  all QFP variants (real values vary — see
  `docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md`).
  R and C (chip passives) draw two short silk lines instead of a
  rectangle (`silk_y`/`silk_half_length` in `data/kicad-fpdb.yaml`,
  declared per variant with no shared formula — each is copied verbatim
  from its real reference footprint, matching real KiCad almost exactly
  — see `docs/superpowers/specs/2026-09-14-chip-passive-silk-lines-
  design.md`); this mode has no pin-1 marker regardless (R/C already
  declare `pin1_marker: false`, and this mode never computes the corner
  point the marker needs). Verified visually via the review tool rather
  than an automated geometry diff, per the spec's stated approach for
  outline geometry.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document two-line silk outline for chip passives

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
