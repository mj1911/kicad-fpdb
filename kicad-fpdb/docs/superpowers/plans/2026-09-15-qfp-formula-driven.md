# QFP Formula-Driven Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `quad_perimeter` derive `pad_offset` (and `_add_outline` derive the QFP silk corner-mark `body_size`) from a declared `courtyard_body_size`, so new QFP variants need only real body/pitch/pin/pad data — no hand-computed `pad_offset` — then add 6 new real QFP variants to prove it generalizes.

**Architecture:** Two independently-derivable formulas, each computed where it's already consumed: `pad_offset = courtyard_body_size/2 + pad_lead_extension` inside `quad_perimeter` (which places pads), and `body_size = courtyard_body_size + 0.22` inside `_add_outline` (which draws the silk corner marks). Both derivations are opt-out escape hatches — an explicit value in the yaml always wins over the formula, matching the project's existing per-family override conventions (e.g. `silk_segments`).

**Tech Stack:** Python, pytest, existing `kicad_fpdb` pipeline/generator/yaml architecture. No new dependencies.

## Global Constraints

* Every new/changed pad position must match its real reference `.kicad_mod` file to within `1e-4` (the existing regression tolerance in `tests/test_pipeline_regression.py`) — most values here match exactly (0.0mm delta).
* `pad_lead_extension` default is `0.675`; QFP-48 and QFP-144 override it to `0.6625`; QFP-80 overrides it to `0.6875`. These are the only 3 real values found across the 8 real LQFP files investigated (7mm-28mm bodies) — see `docs/superpowers/specs/2026-09-15-qfp-formula-driven-design.md`.
* The silk corner-mark `body_size = courtyard_body_size + 0.22` relationship is exact across all 8 samples — no override needed for it in this plan.
* Follow strict TDD: write the failing test, run it, confirm the *correct* failure, implement, run again, confirm green, then commit. Run the full suite (`python3 -m pytest -q`) before each commit, not just the new tests.
* Attribute commits with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

### Task 1: `quad_perimeter` derives `pad_offset` from `courtyard_body_size`

**Files:**
- Modify: `kicad_fpdb/generators/quad_perimeter.py`
- Test: `tests/test_generators_quad_perimeter.py`

**Interfaces:**
- Consumes: nothing new from other tasks (self-contained generator change).
- Produces: `quad_perimeter(pin_count, pitch, pad_size, pad_offset=None, courtyard_body_size=None, pad_lead_extension=0.675) -> FootprintGeometry`. `pad_offset` explicit value always wins; otherwise requires `courtyard_body_size` and computes `pad_offset = courtyard_body_size / 2 + pad_lead_extension`. Raises `ValueError("quad_perimeter requires pad_offset or courtyard_body_size")` if neither is usable. Task 2 depends on this signature.

Current file content (for reference — this is what step 3 replaces):

```python
from kicad_fpdb.geometry import FootprintGeometry, Pad, clamped_roundrect_rratio


def quad_perimeter(pin_count: int, pitch: float, pad_offset: float,
                    pad_size: tuple[float, float]) -> FootprintGeometry:
    if pin_count % 4 != 0:
        raise ValueError("quad_perimeter requires pin_count divisible by 4")
    pins_per_side = pin_count // 4
    half_span = (pins_per_side - 1) * pitch / 2
    long, short = pad_size
    rratio = clamped_roundrect_rratio(pad_size)

    pads = []
    n = 1
    for i in range(pins_per_side):  # left side
        y = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(-pad_offset, y), size=(long, short), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # bottom side
        x = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, pad_offset), size=(short, long), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # right side
        y = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(pad_offset, y), size=(long, short), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # top side
        x = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, -pad_offset), size=(short, long), roundrect_rratio=rratio))
        n += 1

    return FootprintGeometry(name="", pads=pads)
```

- [ ] **Step 1: Write the failing tests**

Add `import pytest` at the top of `tests/test_generators_quad_perimeter.py` (it currently has none), then append these 4 tests to the end of the file:

```python
def test_quad_perimeter_derives_pad_offset_from_body_size_default_extension():
    # Real LQFP-32_7x7mm_P0.8mm.kicad_mod: body 7x7mm, pad "1" at x=-4.175.
    # 7.0/2 + 0.675 (the default lead extension) == 4.175 exactly.
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_size=(1.5, 0.5), courtyard_body_size=7.0)
    pad1 = geom.pads[0]
    assert abs(pad1.at[0] - (-4.175)) < 1e-9


def test_quad_perimeter_derives_pad_offset_with_custom_extension():
    # Real LQFP-48_7x7mm_P0.5mm.kicad_mod: body 7x7mm, pad "1" at x=-4.1625.
    # 7.0/2 + 0.6625 (this package's own lead extension) == 4.1625 exactly.
    geom = quad_perimeter(pin_count=48, pitch=0.5, pad_size=(1.475, 0.3),
                           courtyard_body_size=7.0, pad_lead_extension=0.6625)
    pad1 = geom.pads[0]
    assert abs(pad1.at[0] - (-4.1625)) < 1e-9


def test_quad_perimeter_explicit_pad_offset_overrides_derivation():
    # An escape hatch: an explicit pad_offset must win even when a
    # (deliberately wrong) courtyard_body_size is also given.
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_size=(1.5, 0.5),
                           courtyard_body_size=999.0, pad_offset=4.175)
    pad1 = geom.pads[0]
    assert abs(pad1.at[0] - (-4.175)) < 1e-9


def test_quad_perimeter_raises_without_pad_offset_or_body_size():
    with pytest.raises(ValueError, match="pad_offset or courtyard_body_size"):
        quad_perimeter(pin_count=32, pitch=0.8, pad_size=(1.5, 0.5))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_generators_quad_perimeter.py -v`
Expected: the 4 new tests FAIL with `TypeError: quad_perimeter() got an unexpected keyword argument 'courtyard_body_size'` (or, for the last test, `TypeError: quad_perimeter() missing 1 required positional argument: 'pad_offset'`) — confirming the derivation doesn't exist yet. The 3 pre-existing tests in this file still pass.

- [ ] **Step 3: Implement the derivation**

Replace the full contents of `kicad_fpdb/generators/quad_perimeter.py` with:

```python
from kicad_fpdb.geometry import FootprintGeometry, Pad, clamped_roundrect_rratio

# Real LQFP reference footprints (7mm-28mm bodies) show
# pad_offset == courtyard_body_size/2 + pad_lead_extension, where
# pad_lead_extension is 0.675mm on 5 of 8 samples checked (the rest
# override it) -- see docs/superpowers/specs/
# 2026-09-15-qfp-formula-driven-design.md.
DEFAULT_PAD_LEAD_EXTENSION_MM = 0.675


def quad_perimeter(pin_count: int, pitch: float, pad_size: tuple[float, float],
                    pad_offset: float | None = None,
                    courtyard_body_size: float | None = None,
                    pad_lead_extension: float = DEFAULT_PAD_LEAD_EXTENSION_MM) -> FootprintGeometry:
    if pin_count % 4 != 0:
        raise ValueError("quad_perimeter requires pin_count divisible by 4")
    if pad_offset is None:
        if courtyard_body_size is None:
            raise ValueError("quad_perimeter requires pad_offset or courtyard_body_size")
        pad_offset = courtyard_body_size / 2 + pad_lead_extension
    pins_per_side = pin_count // 4
    half_span = (pins_per_side - 1) * pitch / 2
    long, short = pad_size
    rratio = clamped_roundrect_rratio(pad_size)

    pads = []
    n = 1
    for i in range(pins_per_side):  # left side
        y = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(-pad_offset, y), size=(long, short), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # bottom side
        x = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, pad_offset), size=(short, long), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # right side
        y = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(pad_offset, y), size=(long, short), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # top side
        x = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, -pad_offset), size=(short, long), roundrect_rratio=rratio))
        n += 1

    return FootprintGeometry(name="", pads=pads)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_generators_quad_perimeter.py -v`
Expected: all 7 tests PASS (3 pre-existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/generators/quad_perimeter.py tests/test_generators_quad_perimeter.py
git commit -m "$(cat <<'EOF'
Derive quad_perimeter's pad_offset from courtyard_body_size

pad_offset = courtyard_body_size/2 + pad_lead_extension, matching 8
real LQFP reference footprints (7mm-28mm bodies) exactly. Explicit
pad_offset still overrides the formula, same escape-hatch convention
as silk_segments elsewhere in the project.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Wire `courtyard_body_size` into the generator call and derive `body_size` in `_add_outline`; simplify QFP-32/QFP-48's yaml

**Files:**
- Modify: `kicad_fpdb/pipeline.py`
- Modify: `data/kicad-fpdb.yaml`
- Modify: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `quad_perimeter`'s new signature from Task 1.
- Produces: `generate_footprint()` continues to take `(descriptor_text, family_tree_path, name)` unchanged; internally it now forwards `courtyard_body_size` to `quad_perimeter` specifically (every other generator still never sees it, unchanged). `_add_outline()`'s signature is unchanged, but when called with `body_size=None` and a scalar `courtyard_body_size`, it now derives `body_size` internally before drawing. Task 3 depends on the yaml's QFP root carrying `pad_lead_extension` and each QFP child carrying `courtyard_body_size` instead of `pad_offset`/`body_size`.

Today, `kicad_fpdb/pipeline.py`'s `generate_footprint()` (around line 431) pops `courtyard_body_size` out of `params` *before* calling the generator, purely for `_add_outline`'s use — no generator has ever received it (the existing `SOT` family also declares `courtyard_body_size`, but `asymmetric_dual_row` doesn't accept it as a parameter, so it must stay popped for every generator except `quad_perimeter`).

- [ ] **Step 1: Update the yaml so QFP-32/QFP-48 rely on the derivation**

In `data/kicad-fpdb.yaml`, find the `QFP:` block:

```yaml
QFP:
  params:
    body_size: 7.22
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    courtyard_body_size: 7.0
    fab_outline: true
    fab_chamfer: 1.0
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_offset: 4.175, pad_size: [1.5, 0.5]}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_offset: 4.1625, pad_size: [1.475, 0.3]}
```

Replace it with:

```yaml
QFP:
  params:
    courtyard_margin_x: 0.25
    courtyard_margin_y: 0.25
    fab_outline: true
    fab_chamfer: 1.0
    pad_lead_extension: 0.675
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_size: [1.5, 0.5], courtyard_body_size: 7.0}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_size: [1.475, 0.3], courtyard_body_size: 7.0, pad_lead_extension: 0.6625}
```

Note `body_size: 7.22` and both `pad_offset` values are gone — `courtyard_body_size` (already present) is now the *only* body-size input, feeding both the derived `pad_offset` and the derived `body_size`.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_pipeline_outline.py` (near the other `generate_footprint("QFP-...")` tests, e.g. after `test_generate_footprint_qfp48_silk_matches_real_corner_position` around line 407):

```python
def test_generate_footprint_qfp32_pad_offset_derived_from_courtyard_body_size():
    # QFP-32's yaml no longer declares pad_offset directly -- this proves
    # generate_footprint() forwards courtyard_body_size through to
    # quad_perimeter so it can derive pad_offset itself.
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert "(at -4.175 -2.8)" in text


def test_generate_footprint_qfp48_pad_offset_uses_override_extension():
    # QFP-48 overrides pad_lead_extension to 0.6625 at the yaml level.
    text = generate_footprint("QFP-48", FAMILY_TREE_PATH, name="QFP48_TEST")
    assert "(at -4.1625" in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k "qfp32_pad_offset_derived or qfp48_pad_offset_uses_override" -v`
Expected: both FAIL — `generate_footprint` raises `ValueError: quad_perimeter requires pad_offset or courtyard_body_size`, because `courtyard_body_size` is still being popped and never forwarded to the generator. (Also run `python3 -m pytest tests/test_pipeline_outline.py -k qfp -v` at this point — the two pre-existing corner-mark tests now fail too, since `body_size` is no longer declared in the yaml and nothing derives it yet. That's expected at this stage.)

- [ ] **Step 4: Implement the pipeline wiring**

In `kicad_fpdb/pipeline.py`, find `generate_footprint()` (around line 464-465):

```python
    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
```

Replace with:

```python
    generator_fn = GENERATORS[resolved.generator]
    generator_kwargs = dict(params)
    if resolved.generator == "quad_perimeter":
        # courtyard_body_size is popped above for _add_outline's use on
        # every family (including SOT, whose generator doesn't accept
        # it) -- quad_perimeter is the one generator that also needs it,
        # to derive pad_offset when the yaml doesn't declare one.
        generator_kwargs["courtyard_body_size"] = courtyard_body_size
    geometry = generator_fn(**generator_kwargs)
```

Then find `_add_outline()`'s body (around line 106-109):

```python
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
```

Add the `body_size` derivation right after it:

```python
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM

    if body_size is None and isinstance(courtyard_body_size, (int, float)):
        # QFP-style: the oversized F.SilkS corner-mark span is a fixed
        # 0.22mm larger than the true body on every real LQFP reference
        # footprint checked (7mm-28mm bodies) -- see docs/superpowers/
        # specs/2026-09-15-qfp-formula-driven-design.md. Guarded to a
        # plain number so SOT's tuple courtyard_body_size (a different,
        # non-square shape with no body_size/corner-mark concept) is
        # left alone.
        body_size = courtyard_body_size + 0.22
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k qfp -v`
Expected: still 2 FAILURES — `test_add_outline_with_body_size_draws_corner_marks`, `test_add_outline_with_body_size_keeps_pin1_marker`, and `test_add_outline_with_courtyard_body_size_draws_stepped_courtyard` call the `_qfp32_geometry()` test helper, which directly calls the generator and explicitly pops `courtyard_body_size` before doing so — bypassing the wiring just added. Fix that helper next.

- [ ] **Step 6: Fix the `_qfp32_geometry()` test helper**

In `tests/test_pipeline_outline.py`, find (around line 33-45):

```python
def _qfp32_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("QFP-32"))
    params = dict(resolved.params)
    params.pop("body_size", None)
    params.pop("courtyard_margin_x", None)
    params.pop("courtyard_margin_y", None)
    params.pop("courtyard_body_size", None)
    params.pop("fab_outline", None)
    params.pop("fab_chamfer", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "QFP32_TEST"
    return geometry
```

Remove the `params.pop("courtyard_body_size", None)` line (the generator now needs it to derive `pad_offset`, since QFP-32's yaml no longer declares one) — also remove `params.pop("pad_lead_extension", None)`-style concerns are moot since QFP-32 doesn't override it. Also remove the now-obsolete `params.pop("body_size", None)` line's neighbor concern: `body_size` itself is still fine to pop (it's genuinely absent from QFP-32's params now, so popping a missing key is a harmless no-op). Result:

```python
def _qfp32_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("QFP-32"))
    params = dict(resolved.params)
    params.pop("body_size", None)
    params.pop("courtyard_margin_x", None)
    params.pop("courtyard_margin_y", None)
    params.pop("fab_outline", None)
    params.pop("fab_chamfer", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "QFP32_TEST"
    return geometry
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k qfp -v`
Expected: all QFP-related tests PASS, including the 2 new ones from Step 2 and the pre-existing corner-mark/courtyard/pin1-marker tests that use `_qfp32_geometry()`.

- [ ] **Step 8: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass, 0 failures (this exercises `test_pipeline_regression.py`'s QFP-32/QFP-48 cases too, confirming the derived values still match the real reference files exactly).

- [ ] **Step 9: Commit**

```bash
git add kicad_fpdb/pipeline.py data/kicad-fpdb.yaml tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Wire courtyard_body_size through to quad_perimeter; derive QFP body_size

generate_footprint() now forwards courtyard_body_size specifically to
quad_perimeter (every other generator still never sees it), and
_add_outline derives the QFP silk corner-mark body_size from it
(courtyard_body_size + 0.22, exact across all 8 real LQFP samples
checked). QFP-32/QFP-48's yaml no longer declare pad_offset or
body_size directly -- both come from courtyard_body_size now.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add 6 new real QFP variants (QFP-64, QFP-80, QFP-100, QFP-144, QFP-176, QFP-208)

**Files:**
- Modify: `kicad_fpdb/reference_cases.py`
- Modify: `data/kicad-fpdb.yaml`
- Modify: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: the formula-driven `quad_perimeter`/`_add_outline` wiring from Tasks 1-2.
- Produces: 6 new descriptors (`QFP-64`, `QFP-80`, `QFP-100`, `QFP-144`, `QFP-176`, `QFP-208`) resolvable via `generate_footprint()`, each backed by a real reference case in `CASES`.

Real data for each (from `/usr/share/kicad/footprints/Package_QFP.pretty/`, verified in the design spec):

| Descriptor | Real file | Body (mm) | Pins | Pitch | `pad_size` | `pad_lead_extension` |
|---|---|---|---|---|---|---|
| QFP-64 | `LQFP-64_10x10mm_P0.5mm.kicad_mod` | 10.0 | 64 | 0.5 | `[1.55, 0.3]` | default (0.675) |
| QFP-80 | `LQFP-80_12x12mm_P0.5mm.kicad_mod` | 12.0 | 80 | 0.5 | `[1.475, 0.25]` | 0.6875 |
| QFP-100 | `LQFP-100_14x14mm_P0.5mm.kicad_mod` | 14.0 | 100 | 0.5 | `[1.6, 0.3]` | default (0.675) |
| QFP-144 | `LQFP-144_20x20mm_P0.5mm.kicad_mod` | 20.0 | 144 | 0.5 | `[1.475, 0.3]` | 0.6625 |
| QFP-176 | `LQFP-176_24x24mm_P0.5mm.kicad_mod` | 24.0 | 176 | 0.5 | `[1.5, 0.3]` | default (0.675) |
| QFP-208 | `LQFP-208_28x28mm_P0.5mm.kicad_mod` | 28.0 | 208 | 0.5 | `[1.5, 0.3]` | default (0.675) |

- [ ] **Step 1: Add the new reference cases (red state)**

In `kicad_fpdb/reference_cases.py`, find:

```python
    ("QFP-32", "Package_QFP.pretty/LQFP-32_7x7mm_P0.8mm.kicad_mod"),
    ("QFP-48", "Package_QFP.pretty/LQFP-48_7x7mm_P0.5mm.kicad_mod"),
]
```

Replace with:

```python
    ("QFP-32", "Package_QFP.pretty/LQFP-32_7x7mm_P0.8mm.kicad_mod"),
    ("QFP-48", "Package_QFP.pretty/LQFP-48_7x7mm_P0.5mm.kicad_mod"),
    ("QFP-64", "Package_QFP.pretty/LQFP-64_10x10mm_P0.5mm.kicad_mod"),
    ("QFP-80", "Package_QFP.pretty/LQFP-80_12x12mm_P0.5mm.kicad_mod"),
    ("QFP-100", "Package_QFP.pretty/LQFP-100_14x14mm_P0.5mm.kicad_mod"),
    ("QFP-144", "Package_QFP.pretty/LQFP-144_20x20mm_P0.5mm.kicad_mod"),
    ("QFP-176", "Package_QFP.pretty/LQFP-176_24x24mm_P0.5mm.kicad_mod"),
    ("QFP-208", "Package_QFP.pretty/LQFP-208_28x28mm_P0.5mm.kicad_mod"),
]
```

- [ ] **Step 2: Run the regression suite to verify it fails**

Run: `python3 -m pytest tests/test_pipeline_regression.py -k "QFP-64 or QFP-80 or QFP-100 or QFP-144 or QFP-176 or QFP-208" -v`
Expected: all 6 new parametrized cases FAIL — `resolve_descriptor` raises (the descriptor `QFP-64` etc. doesn't exist in the yaml yet).

- [ ] **Step 3: Add the new yaml children**

In `data/kicad-fpdb.yaml`, find the `QFP:` block's `children:` section (as left by Task 2):

```yaml
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_size: [1.5, 0.5], courtyard_body_size: 7.0}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_size: [1.475, 0.3], courtyard_body_size: 7.0, pad_lead_extension: 0.6625}
```

Replace with:

```yaml
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_size: [1.5, 0.5], courtyard_body_size: 7.0}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_size: [1.475, 0.3], courtyard_body_size: 7.0, pad_lead_extension: 0.6625}
    QFP-64:
      generator: quad_perimeter
      params: {pin_count: 64, pitch: 0.5, pad_size: [1.55, 0.3], courtyard_body_size: 10.0}
    QFP-80:
      generator: quad_perimeter
      params: {pin_count: 80, pitch: 0.5, pad_size: [1.475, 0.25], courtyard_body_size: 12.0, pad_lead_extension: 0.6875}
    QFP-100:
      generator: quad_perimeter
      params: {pin_count: 100, pitch: 0.5, pad_size: [1.6, 0.3], courtyard_body_size: 14.0}
    QFP-144:
      generator: quad_perimeter
      params: {pin_count: 144, pitch: 0.5, pad_size: [1.475, 0.3], courtyard_body_size: 20.0, pad_lead_extension: 0.6625}
    QFP-176:
      generator: quad_perimeter
      params: {pin_count: 176, pitch: 0.5, pad_size: [1.5, 0.3], courtyard_body_size: 24.0}
    QFP-208:
      generator: quad_perimeter
      params: {pin_count: 208, pitch: 0.5, pad_size: [1.5, 0.3], courtyard_body_size: 28.0}
```

- [ ] **Step 4: Run the regression suite to verify it passes**

Run: `python3 -m pytest tests/test_pipeline_regression.py -v`
Expected: all cases PASS, including the 6 new ones — pad positions match their real reference files exactly (0.0mm delta).

- [ ] **Step 5: Add an outline test proving the derivation generalizes beyond 7x7mm bodies**

Add to `tests/test_pipeline_outline.py`, near the existing `test_generate_footprint_qfp48_silk_matches_real_corner_position` test:

```python
def test_generate_footprint_qfp100_silk_matches_real_corner_position():
    # Real LQFP-100_14x14mm_P0.5mm.kicad_mod corner marks are at
    # (+-7.11, +-7.11) -- proves body_size derivation
    # (courtyard_body_size + 0.22) generalizes beyond the 7x7mm bodies
    # QFP-32/QFP-48 share, to a 14x14mm body.
    text = generate_footprint("QFP-100", FAMILY_TREE_PATH, name="QFP100_TEST")
    assert "(start -7.11 -7.11)" in text
    assert "(end -6.81 -7.11)" in text
```

- [ ] **Step 6: Run this test to verify it passes**

Run: `python3 -m pytest tests/test_pipeline_outline.py -k qfp100 -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all tests pass, 0 failures.

- [ ] **Step 8: Commit**

```bash
git add kicad_fpdb/reference_cases.py data/kicad-fpdb.yaml tests/test_pipeline_outline.py
git commit -m "$(cat <<'EOF'
Add 6 new real QFP variants (64/80/100/144/176/208-pin)

Each declares only pin_count, pitch, pad_size, and courtyard_body_size
(plus a pad_lead_extension override for the 2 that need one) --
pad_offset and the silk corner-mark body_size are both derived.
Verified exact (0.0mm delta) against real LQFP reference footprints
spanning 10mm to 28mm bodies, well beyond the two 7x7mm variants that
existed before this change.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Documentation, visual review, and final verification

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CHANGELOG.md`
- Regenerate: `renders/review.html` (gitignored, not committed)

**Interfaces:**
- Consumes: the completed feature from Tasks 1-3.
- Produces: nothing new consumed by later tasks — this is the closing task.

- [ ] **Step 1: Regenerate and visually inspect the review viewer**

Run: `python3 -m kicad_fpdb.visual_compare`
Expected output: `Wrote 32 case(s) to renders/` (26 existing + 6 new QFP variants).

Then inspect `renders/review.html` for at least QFP-100 and QFP-208 (the largest new body size) — confirm the generated silk corner marks, courtyard, and pad grid visually line up with the real reference panel, the same way every other family in this project has been checked. Use `rsvg-convert` + the Read tool to view specific panels if a full browser isn't available in this environment, per the pattern already established this session (e.g. cropping a specific `<svg>` block from `renders/review.html` and rasterizing it).

- [ ] **Step 2: Update `CLAUDE.md`**

Find the QFP-specific paragraph inside the big "Generated footprints have courtyard..." bullet (the one starting "QFP draws real corner-mark brackets instead of a rectangle..."). Immediately after that paragraph (still within the same bullet, before the "R and C (chip passives) draw two short silk lines..." paragraph), insert:

```markdown
  QFP is now formula-driven like DIP/SOIC rather than each variant
  hand-computing its own `pad_offset`: `quad_perimeter` derives
  `pad_offset = courtyard_body_size/2 + pad_lead_extension` (default
  `0.675`, overridden per variant for the 2 of 8 real LQFP samples
  that need a different value), and `_add_outline` derives the silk
  corner-mark `body_size = courtyard_body_size + 0.22` (exact across
  all 8 samples, 7mm-28mm bodies) — both explicit-value escape
  hatches, same convention as `silk_segments` elsewhere. `courtyard_
  body_size` is now the single body-size input for a QFP variant,
  feeding pad placement, the silk corner marks, the courtyard, and
  (via `fab_outline: true`) the F.Fab body outline all at once. 8 QFP
  variants total now (was 2), spanning 7mm-28mm real bodies — see
  `docs/superpowers/specs/2026-09-15-qfp-formula-driven-design.md`.
```

Then find the TODO section's line:

```markdown
* Make QFP a formula family like DIP/SOIC (currently each QFP variant is a
  fully enumerated leaf in `data/kicad-fpdb.yaml` because `pad_offset`
  can't be derived from `pin_count` alone) — needs a declared body-size
  parameter to derive `pad_offset` from.
```

Delete that entire bullet (it's now done).

- [ ] **Step 3: Update `CHANGELOG.md`**

Find today's entry at the top of the file (`2026-09-15 v0.0.9:`). Add a new bullet immediately after the header line, before the existing first bullet (the size-comparison one):

```markdown
* Made QFP formula-driven like DIP/SOIC: `quad_perimeter` derives
  `pad_offset` and `_add_outline` derives the silk corner-mark
  `body_size`, both from a single declared `courtyard_body_size`
  (`pad_offset = courtyard_body_size/2 + pad_lead_extension`,
  `body_size = courtyard_body_size + 0.22`), verified exact against 8
  real LQFP reference footprints spanning 7mm-28mm bodies. Added 6 new
  real QFP variants (64/80/100/144/176/208-pin) this unlocks — 8 total,
  up from 2. See
  `docs/superpowers/specs/2026-09-15-qfp-formula-driven-design.md`.
```

- [ ] **Step 4: Run the full suite one final time**

Run: `python3 -m pytest -q`
Expected: all tests pass, 0 failures.

- [ ] **Step 5: Commit the docs**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
Document formula-driven QFP family in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Open the review viewer for the user**

Per this project's standing convention (regenerate and open `renders/review.html` once per session after a visual change), open it now if it hasn't already been opened this session.
