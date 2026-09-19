# DIP Courtyard Margin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten DIP's courtyard (F.CrtYd) margin to match real KiCad — 0.25mm perpendicular to the pin rows (X), 0.72mm along them (Y) — instead of the current flat 0.5mm used by every family.

**Architecture:** `_add_outline()` in `kicad_fpdb/pipeline.py` gains two optional parameters, `courtyard_margin_x` and `courtyard_margin_y`, each falling back to the existing `COURTYARD_MARGIN_MM` constant when `None`. `generate_footprint()` pops both from resolved params the same way it already does for the other outline-only params. `DIP` declares `courtyard_margin_x: 0.25` / `courtyard_margin_y: 0.72` at its family root in `data/kicad-fpdb.yaml`, inherited by every child via the existing chain-merge. Every other family (SOIC, QFP, R, C) is untouched and keeps the flat 0.5mm margin.

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q`.

## Global Constraints

- This only changes the courtyard `Rect`. F.SilkS geometry (in whichever mode a family uses) and the pin-1 marker are completely unaffected.
- Only `DIP` gets `courtyard_margin_x`/`courtyard_margin_y` declared. SOIC, QFP, R, and C's YAML entries and generated output must be byte-identical to before this change.
- Exact values to use (from the spec, `docs/superpowers/specs/2026-09-14-dip-courtyard-margin-design.md`): `courtyard_margin_x: 0.25`, `courtyard_margin_y: 0.72`. This is a symbolic match, not exact for every real DIP variant (real values range 0.25-0.26mm in X across variants) — do not add per-variant special-casing.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Add asymmetric courtyard margins to `_add_outline`

**Files:**
- Modify: `kicad_fpdb/pipeline.py` (the `_add_outline` function, currently lines 59-144)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: nothing new — uses the existing `_dip16_geometry()` helper already in `tests/test_pipeline_outline.py`.
- Produces: `_add_outline(geometry, body_width=None, body_margin=None, body_size=None, pin1_marker=True, silk_y=None, silk_half_length=None, courtyard_margin_x=None, courtyard_margin_y=None)`. When either is `None`, that axis falls back to `COURTYARD_MARGIN_MM` (today's behavior). Relied on by Task 2.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline_outline.py`, anywhere after the existing `test_add_outline_produces_courtyard_rect` test (that one already covers the flat-margin fallback — no need to duplicate it):

```python
def test_add_outline_with_courtyard_margins_uses_asymmetric_values():
    geometry = _dip16_geometry()
    _add_outline(geometry, courtyard_margin_x=0.25, courtyard_margin_y=0.72)

    assert len(geometry.rects) == 1
    rect = geometry.rects[0]
    assert rect.layer == "F.CrtYd"
    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); 0.25mm margin in X,
    # 0.72mm in Y.
    assert rect.start == pytest.approx((-1.05, -1.52))
    assert rect.end == pytest.approx((8.67, 19.3))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: FAILS with `TypeError: _add_outline() got an unexpected keyword argument 'courtyard_margin_x'`.

- [ ] **Step 3: Implement the asymmetric margins**

In `kicad_fpdb/pipeline.py`, change the `_add_outline` signature:

```python
def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True,
                  silk_y: float | None = None, silk_half_length: float | None = None,
                  courtyard_margin_x: float | None = None, courtyard_margin_y: float | None = None) -> None:
```

And change the courtyard block (currently the first two lines of the function body):

```python
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    cy0x, cy0y = min_x - COURTYARD_MARGIN_MM, min_y - COURTYARD_MARGIN_MM
    cy1x, cy1y = max_x + COURTYARD_MARGIN_MM, max_y + COURTYARD_MARGIN_MM
    geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))
```

to:

```python
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
    cy0x, cy0y = min_x - mx, min_y - my
    cy1x, cy1y = max_x + mx, max_y + my
    geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))
```

No other lines in the function change — every F.SilkS branch and the pin-1 marker block are untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS, including the new one and every pre-existing test in this file (none of them pass `courtyard_margin_x`/`courtyard_margin_y`, so they exercise the unchanged flat-margin fallback).

- [ ] **Step 5: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (84 baseline + 1 new = 85).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Let _add_outline use asymmetric courtyard margins

Adds optional courtyard_margin_x/courtyard_margin_y params, each
falling back to the existing flat COURTYARD_MARGIN_MM when not given,
so a family can declare a real per-axis courtyard margin without
touching every other family's behavior.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire real courtyard margins through for DIP

**Files:**
- Modify: `data/kicad-fpdb.yaml` (the `DIP` entry's root `params`)
- Modify: `kicad_fpdb/pipeline.py` (the `generate_footprint` function)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_outline(geometry, ..., courtyard_margin_x=None, courtyard_margin_y=None)` from Task 1.
- Produces: `generate_footprint()` keeps the same public signature and return type — no change visible to callers. Internally it now also strips `courtyard_margin_x`/`courtyard_margin_y` out of `resolved.params` before calling the generator function.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_dip16_courtyard_matches_real_kicad():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(start -1.05 -1.52)" in text
    assert "(end 8.67 19.3)" in text


def test_generate_footprint_soic8_courtyard_still_uses_flat_margin():
    # SOIC doesn't declare courtyard_margin_x/y, so it must keep today's
    # flat 0.5mm margin — this is the regression guard that a change
    # scoped to DIP doesn't leak into other families.
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert "(start -3.95 -2.705)" in text
    assert "(end 3.95 2.705)" in text


def test_generate_footprint_does_not_leak_courtyard_margins_to_generator():
    # If pipeline.py forgot to pop courtyard_margin_x/y before calling
    # the generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert text  # got here without raising
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_generate_footprint_dip16_courtyard_matches_real_kicad` FAILS (the yaml doesn't declare `courtyard_margin_x`/`courtyard_margin_y` yet, so DIP still uses the flat 0.5mm margin). `test_generate_footprint_soic8_courtyard_still_uses_flat_margin` and `test_generate_footprint_does_not_leak_courtyard_margins_to_generator` PASS already — expected, since neither depends on the yaml change; both remain meaningful regression guards once Step 3 lands.

- [ ] **Step 3: Add courtyard margins to DIP's root params**

In `data/kicad-fpdb.yaml`, change the `DIP` entry's `params` block (currently):

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
    pad_size: [1.6, 1.6]
    pad_shape: dip_pin1_marker
    pad_type: thru_hole
    drill: 0.8
    centered: false
```

Do not touch `SOIC`, `QFP`, `R`, or `C`.

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
    courtyard_margin_x = params.pop("courtyard_margin_x", None)
    courtyard_margin_y = params.pop("courtyard_margin_y", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, silk_y=silk_y, silk_half_length=silk_half_length,
                 courtyard_margin_x=courtyard_margin_x, courtyard_margin_y=courtyard_margin_y)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Run the full suite, including the KiCad-dependent regression suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass. `tests/test_pipeline_regression.py` (parametrized over every case including every DIP variant) must still pass — it only checks pad geometry, unaffected by this change. If it's skipped on this machine (KiCad footprints not present), say so in your report rather than assuming it ran.

- [ ] **Step 7: Commit**

```bash
git add data/kicad-fpdb.yaml kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Tighten DIP's courtyard to real KiCad's asymmetric margin

DIP courtyards were using the generic flat 0.5mm margin on every side,
visibly wider than real KiCad perpendicular to the pin rows. Real DIP
uses 0.25mm in X and 0.72mm in Y, consistent across every pin count
and row-spacing width checked. Declared once at DIP's root params and
inherited by every child via the existing chain-merge.

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

- [ ] **Step 2: Visually check the DIP cases**

Open `renders/review.html` (e.g. `xdg-open renders/review.html`). For DIP-16, DIP-14, DIP-18, and DIP-16 r, the Generated panel's courtyard (magenta rectangle) should now sit noticeably tighter around the part — closer to the pins in X, matching the Reference panel much more closely than before. SOIC, QFP, and R/C courtyards should look unchanged.

If a case looks wrong (courtyard too tight, clipping pads, or unchanged from before), stop and re-check Task 1/2 before proceeding.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the sentence (in the "Claude-isms below" section, inside the outline-geometry bullet) that currently reads:

```
Courtyard is
  still generic (pad bounding box + margin) for every family; no
  family uses the generic pad-bbox F.SilkS rectangle anymore.
```

Replace it with:

```
Courtyard is
  still generic (flat 0.5mm pad-bounding-box margin) for SOIC, QFP,
  and chip passives (R/C); no family uses the generic pad-bbox
  F.SilkS rectangle anymore. DIP's courtyard instead uses a real,
  asymmetric margin (`courtyard_margin_x`/`courtyard_margin_y` in
  `data/kicad-fpdb.yaml`: 0.25mm perpendicular to the pin rows, 0.72mm
  along them), matching real KiCad almost exactly across every pin
  count and width checked — see
  `docs/superpowers/specs/2026-09-14-dip-courtyard-margin-design.md`.
  SOIC's real courtyard is a more complex stepped shape, not a simple
  rectangle with a bigger margin, so it's intentionally not matched
  yet.
```

(This sentence currently sits between "...geometry (see `kicad_fpdb.pipeline._add_outline`)." and "DIP and SOIC draw a real body-derived rectangle..." — replace only this sentence, leaving the rest of the bullet as-is.)

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document DIP's tightened courtyard margin

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
