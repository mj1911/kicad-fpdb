# Pin-1 Marker Opt-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop drawing the pin-1 marker triangle for R and C (non-polarized two-pin passives), while leaving DIP/SOIC/QFP unaffected and leaving a data-only path for a future polarized capacitor to opt back in.

**Architecture:** `_add_outline()` in `kicad_fpdb/pipeline.py` gains a `pin1_marker: bool = True` parameter gating the existing marker-drawing block. `generate_footprint()` pops a `pin1_marker` key from resolved params (default `True` when absent) the same way it already pops `body_width`/`body_margin`/`body_size`. `data/kicad-fpdb.yaml` sets `pin1_marker: false` at the `R` and `C` family root level, which the existing chain-merge already inherits down to every child (`R-0402`, `R-0603`, `R-0805`, `C-0603`) with no per-child edits.

**Tech Stack:** Python 3.10+, pytest. Run tests with `~/.venvs/kicad-fpdb/bin/python -m pytest -q`.

## Global Constraints

- Only the pin-1 marker `Poly` is affected. Courtyard, the F.SilkS outline itself (rectangle or corner marks, whichever mode is active), and pad geometry are all untouched.
- `pin1_marker` defaults to `True` everywhere it's not explicitly declared — DIP, SOIC, and QFP's YAML entries must not be touched, and their generated output must be byte-identical to before this change.
- The full test suite (`pytest -q`) must pass after every task's commit — no task may leave the suite red.

---

### Task 1: Gate the pin-1 marker behind a `pin1_marker` flag

**Files:**
- Modify: `kicad_fpdb/pipeline.py` (the `_add_outline` function, currently lines 59-121)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: nothing new — uses the existing `_dip16_geometry()` helper already in `tests/test_pipeline_outline.py`.
- Produces: `_add_outline(geometry, body_width=None, body_margin=None, body_size=None, pin1_marker=True)`. Relied on by Task 2. Existing callers that don't pass `pin1_marker` keep today's behavior (marker drawn whenever pad `"1"` exists) since the default is `True`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline_outline.py`, anywhere after `test_add_outline_produces_pin1_marker_triangle` (that existing test already covers the default-`True` case — no need to duplicate it):

```python
def test_add_outline_pin1_marker_false_suppresses_marker():
    geometry = _dip16_geometry()
    _add_outline(geometry, pin1_marker=False)

    assert len(geometry.polys) == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: FAILS with `TypeError: _add_outline() got an unexpected keyword argument 'pin1_marker'`.

- [ ] **Step 3: Implement the gate**

In `kicad_fpdb/pipeline.py`, change the `_add_outline` signature:

```python
def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True) -> None:
```

And change the marker-drawing block at the end of the function (currently):

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pad1 is not None:
```

to:

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None:
```

No other lines in the function change.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: all tests PASS, including the new one and every pre-existing test in this file (none of them pass `pin1_marker`, so they exercise the unchanged default-`True` path).

- [ ] **Step 5: Run the full suite**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest -q`
Expected: all tests pass (72 baseline + 1 new = 73).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Let _add_outline suppress the pin-1 marker via a pin1_marker flag

Adds an optional pin1_marker param (default True, matching today's
behavior) so a family can opt out of the pin-1 triangle without
touching the marker-drawing logic itself.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Turn the marker off for R and C

**Files:**
- Modify: `data/kicad-fpdb.yaml` (the `R` and `C` family root entries)
- Modify: `kicad_fpdb/pipeline.py` (the `generate_footprint` function)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_outline(geometry, ..., pin1_marker=True)` from Task 1.
- Produces: `generate_footprint()` keeps the same public signature and return type — no change visible to callers. Internally it now also strips `pin1_marker` out of `resolved.params` before calling the generator function.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_pipeline_outline.py`:

```python
def test_generate_footprint_r0603_has_no_pin1_marker():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "fp_poly" not in text


def test_generate_footprint_c0603_has_no_pin1_marker():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "fp_poly" not in text


def test_generate_footprint_dip16_still_has_pin1_marker():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "fp_poly" in text


def test_generate_footprint_does_not_leak_pin1_marker_to_generator():
    # If pipeline.py forgot to pop pin1_marker before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text  # got here without raising
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `~/.venvs/kicad-fpdb/bin/python -m pytest tests/test_pipeline_outline.py -v`
Expected: `test_generate_footprint_r0603_has_no_pin1_marker` and `test_generate_footprint_c0603_has_no_pin1_marker` FAIL (R/C still emit `fp_poly` — the yaml doesn't declare `pin1_marker` yet). `test_generate_footprint_dip16_still_has_pin1_marker` and `test_generate_footprint_does_not_leak_pin1_marker_to_generator` PASS already — expected, since neither depends on the yaml change.

- [ ] **Step 3: Add `pin1_marker: false` to R and C's root params**

In `data/kicad-fpdb.yaml`, change the `R` entry (currently):

```yaml
R:
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
      params: {pad_pitch: 1.02, pad_size: [0.54, 0.64]}
    R-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.65, pad_size: [0.8, 0.95]}
    R-0805:
      generator: two_pad_chip
      params: {pad_pitch: 1.825, pad_size: [1.025, 1.4]}
```

And change the `C` entry (currently):

```yaml
C:
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
      params: {pad_pitch: 1.55, pad_size: [0.9, 0.95]}
```

Do not touch `DIP`, `SOIC`, or `QFP`. Leave the existing comment block above `C:` (about polarized capacitors) as-is — it's still accurate context for future work.

- [ ] **Step 4: Pop `pin1_marker` out before calling the generator**

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

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker)
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
Turn off the pin-1 marker for R and C

Resistors are never polarized and the one capacitor variant so far
(C-0603) isn't either, so the marker was implying an orientation that
doesn't matter. Declared once at each family's root params and
inherited by every child via the existing chain-merge. A future
polarized capacitor variant can opt back in with pin1_marker: true in
its own params.

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

- [ ] **Step 2: Visually check the R and C cases**

Open `renders/review.html` (e.g. `xdg-open renders/review.html`). For R-0402, R-0603, R-0805, and C-0603, the Generated panel should no longer show a pin-1 triangle (the Reference panel — real KiCad's own footprint — never had one either, so both panels should now agree). DIP-16/14/18/16r, SOIC-8/14, and QFP-32/48 should be unchanged from before (still showing their markers/corner marks).

If a case looks wrong (marker still present on R/C, or missing from DIP/SOIC/QFP), stop and re-check Task 1/2 before proceeding.

- [ ] **Step 3: Update the CLAUDE.md running notes**

In `CLAUDE.md`, find the bullet (in the "Claude-isms below" section) that currently reads:

```
* Pin-1 marker: a small filled silkscreen triangle, tip at the body
  corner nearest pad 1, pointing at pad 1's actual position — matches
  real KiCad's own convention (see `kicad_fpdb.pipeline._add_outline`).
```

Replace it with:

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

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document pin1_marker opt-out for non-polarized passives

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
