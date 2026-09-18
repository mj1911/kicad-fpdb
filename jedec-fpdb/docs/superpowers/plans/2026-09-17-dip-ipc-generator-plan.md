# jedec-fpdb DIP Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully independent Python package, `jedec-fpdb/`, that generates narrow-width (0.300in/7.62mm row spacing) DIP `.kicad_mod` footprints purely from JEDEC MS-001 body/lead data and a best-effort IPC-7251 thru-hole sizing formula, then compares the output against real KiCad reference files as a documented sanity check.

**Architecture:** A JEDEC data table (`data/ms001_dip.py`) and an IPC-7251 formula module (`jedec_fpdb/ipc7251.py`) feed a generator (`jedec_fpdb/dip.py`) that builds a plain `Footprint` object (`jedec_fpdb/geometry.py`); a writer (`jedec_fpdb/writer.py`) serializes it to `.kicad_mod`; a comparison tool (`jedec_fpdb/compare.py`) diffs it against real reference files read directly from the system KiCad library. No code or data is shared with `kicad-fpdb` at the repo root.

**Tech Stack:** Python 3.10+ stdlib only (dataclasses, `re`, `argparse`, `uuid`), pytest for tests. No third-party runtime dependencies, no `pip install` of the package itself (see Global Constraints).

**Spec:** `jedec-fpdb/docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md`

## Global Constraints

- Fully independent of `kicad-fpdb`: no `import kicad_fpdb...` anywhere in this package, and no copying of its YAML/data/geometry/writer code. The only permitted contact is `compare.py`/its tests reading real `.kicad_mod` files directly from the filesystem path `/usr/share/kicad/footprints/Package_DIP.pretty/` (a plain string constant in this project, not an import).
- Narrow (0.300in/7.62mm row spacing) DIP only. `dip.generate()` must reject any other `width_class` with a clear `ValueError` — do not add `"regular"`/`"wide"` support in this plan.
- JEDEC MS-001 numbers (pitch, row spacing, body width, lead width, per-pin-count body length table) are transcribed directly from `docs/Ms-001d.pdf` (repo root `docs/`, gitignored, not `jedec-fpdb`'s own `docs/`) — cite the document inline in a comment wherever a constant comes from it.
- IPC-7251 numbers (hole clearance, minimum annular ring, per density level) are a best-effort public reconstruction, not from the real standard — comment them as such.
- Pin count 8's body length is not in MS-001's own table; compute it via linear least-squares regression over the table's own N=14..28 nominal values (see Task 1), not a hand-picked constant.
- No `pip install`/`pip install -e` of this package anywhere — it must run via `pytest` (using a `pythonpath` pytest.ini setting) and via `python -m jedec_fpdb` from within the `jedec-fpdb/` directory, both relying on Python's own `sys.path` insertion, avoiding this machine's externally-managed-Python pip restriction entirely.
- Density level is always one of the literal strings `"M"` (Most), `"N"` (Nominal, the default), `"L"` (Least) — never a longer word, never case-insensitive matching.

---

## Task 1: Project scaffolding + JEDEC MS-001 DIP data table

**Files:**
- Create: `jedec-fpdb/pyproject.toml`
- Create: `jedec-fpdb/jedec_fpdb/__init__.py` (empty)
- Create: `jedec-fpdb/data/__init__.py` (empty)
- Create: `jedec-fpdb/data/ms001_dip.py`
- Test: `jedec-fpdb/tests/test_ms001_dip.py`

**Interfaces:**
- Produces: `data.ms001_dip.PITCH_MM` (float), `data.ms001_dip.ROW_SPACING_MM` (float), `data.ms001_dip.BODY_WIDTH_MM` (float), `data.ms001_dip.LEAD_WIDTH_MAX_MM` (float), `data.ms001_dip.body_length_mm(pin_count: int) -> float` (raises `ValueError` for odd or `< 4` pin_count).

- [ ] **Step 1: Create the project scaffolding files**

`jedec-fpdb/pyproject.toml`:
```toml
[project]
name = "jedec-fpdb"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`jedec-fpdb/jedec_fpdb/__init__.py`: empty file.

`jedec-fpdb/data/__init__.py`: empty file.

- [ ] **Step 2: Write the failing test for the JEDEC constants and table lookups**

`jedec-fpdb/tests/test_ms001_dip.py`:
```python
import pytest

from data import ms001_dip


def test_basic_dimensions():
    assert ms001_dip.PITCH_MM == pytest.approx(2.54)
    assert ms001_dip.ROW_SPACING_MM == pytest.approx(7.62)
    assert ms001_dip.BODY_WIDTH_MM == pytest.approx(6.35)
    assert ms001_dip.LEAD_WIDTH_MAX_MM == pytest.approx(0.559)


@pytest.mark.parametrize("pin_count,expected_mm", [
    (14, 19.05),
    (16, 20.066),
    (18, 22.86),
    (20, 26.162),
    (22, 29.337),
    (24, 31.75),
    (28, 35.687),
])
def test_body_length_table_lookup(pin_count, expected_mm):
    assert ms001_dip.body_length_mm(pin_count) == pytest.approx(expected_mm)


def test_body_length_8_pin_is_regression_extrapolation():
    # N=8 has no full-lead entry in MS-001's own table (see design spec) --
    # this only bounds the extrapolation to a sane range, since we can't
    # independently verify a precise "official" value for it.
    result = ms001_dip.body_length_mm(8)
    assert 8.0 < result < 14.0


def test_body_length_rejects_odd_pin_count():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm(15)


def test_body_length_rejects_too_few_pins():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm(2)


def test_extrapolate_body_length_on_synthetic_linear_data():
    # Verifies the regression math itself against a table with a known
    # exact linear relationship (D = N), independent of MS-001's real,
    # non-linear numbers.
    table = {10: 10.0, 20: 20.0, 30: 30.0}
    result = ms001_dip._extrapolate_body_length_mm(table, 40)
    assert result == pytest.approx(40.0)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd jedec-fpdb && python -m pytest tests/test_ms001_dip.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'data.ms001_dip'` (or similar import error) — `data/ms001_dip.py` doesn't exist yet.

- [ ] **Step 4: Write `data/ms001_dip.py`**

```python
"""JEDEC MS-001 (Issue D, "R-PDIP-T ... .300 INCH ROW SPACING") data,
transcribed directly from a copy of the document at docs/Ms-001d.pdf
(repo root `docs/`, gitignored -- JEDEC's document, not ours to
redistribute). Covers only the narrow (0.300in / 7.62mm) row-spacing DIP
family; see the design spec for why regular/wide aren't included yet.
"""

# e: lead pitch, Basic (theoretical exact) dimension, sheet 2 of 2.
PITCH_MM = 2.54  # 0.100in BSC

# eA: row spacing (pin-center-to-pin-center across the two rows), Basic.
ROW_SPACING_MM = 7.62  # 0.300in BSC

# E1: body width, nominal (min 0.240in, max 0.280in).
BODY_WIDTH_MM = 6.35  # 0.250in nominal

# b: lead width, maximum. Used as the effective lead "diameter" for
# round-hole sizing -- DIP leads are rectangular, and the drilled hole
# must clear the lead's largest cross-section dimension.
LEAD_WIDTH_MAX_MM = 0.559  # 0.022in max

# D: body length, nominal, by pin count (N). Full-lead-population
# variations AA-AG only, transcribed from the document's Variations
# table. There is no full-lead entry for N=8 -- it only appears under a
# "1/2 lead" (staggered) variation, a different lead-population style
# than the ordinary fully-populated 8-pin DIP -- see body_length_mm().
_BODY_LENGTH_TABLE_MM = {
    14: 19.05,
    16: 20.066,
    18: 22.86,
    20: 26.162,
    22: 29.337,
    24: 31.75,
    28: 35.687,
}


def _extrapolate_body_length_mm(table: dict[int, float], pin_count: int) -> float:
    """Linear least-squares fit of the table's own (N, D_nominal) pairs,
    evaluated at pin_count. MS-001's own D values are not perfectly
    linear in N (real DIP bodies come in a handful of standardized mold
    sizes, not one continuous formula), so this is an approximation used
    only for pin counts outside the table -- currently just N=8."""
    ns = list(table.keys())
    ds = list(table.values())
    n_mean = sum(ns) / len(ns)
    d_mean = sum(ds) / len(ds)
    sxy = sum((n - n_mean) * (d - d_mean) for n, d in zip(ns, ds))
    sxx = sum((n - n_mean) ** 2 for n in ns)
    slope = sxy / sxx
    intercept = d_mean - slope * n_mean
    return intercept + slope * pin_count


def body_length_mm(pin_count: int) -> float:
    if pin_count % 2 != 0 or pin_count < 4:
        raise ValueError(f"pin_count must be even and >= 4, got {pin_count}")
    if pin_count in _BODY_LENGTH_TABLE_MM:
        return _BODY_LENGTH_TABLE_MM[pin_count]
    return _extrapolate_body_length_mm(_BODY_LENGTH_TABLE_MM, pin_count)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd jedec-fpdb && python -m pytest tests/test_ms001_dip.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
cd jedec-fpdb
git add pyproject.toml jedec_fpdb/__init__.py data/__init__.py data/ms001_dip.py tests/test_ms001_dip.py
git commit -m "jedec-fpdb: add project scaffolding and JEDEC MS-001 DIP data table"
```

---

## Task 2: IPC-7251 thru-hole sizing formulas

**Files:**
- Create: `jedec-fpdb/jedec_fpdb/ipc7251.py`
- Test: `jedec-fpdb/tests/test_ipc7251.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly (takes a plain `lead_diameter_mm: float` argument, not `ms001_dip` types).
- Produces: `jedec_fpdb.ipc7251.drill_diameter_mm(lead_diameter_mm: float, density: str) -> float`, `jedec_fpdb.ipc7251.pad_diameter_mm(lead_diameter_mm: float, density: str) -> float`, both raising `ValueError` for an unknown `density`.

- [ ] **Step 1: Write the failing test**

`jedec-fpdb/tests/test_ipc7251.py`:
```python
import pytest

from jedec_fpdb import ipc7251

LEAD = 0.559  # MS-001's lead width max, mm


def test_drill_diameter_by_density():
    assert ipc7251.drill_diameter_mm(LEAD, "N") == pytest.approx(0.759)
    assert ipc7251.drill_diameter_mm(LEAD, "M") == pytest.approx(0.809)
    assert ipc7251.drill_diameter_mm(LEAD, "L") == pytest.approx(0.709)


def test_pad_diameter_by_density():
    assert ipc7251.pad_diameter_mm(LEAD, "N") == pytest.approx(0.959)
    assert ipc7251.pad_diameter_mm(LEAD, "M") == pytest.approx(1.109)
    assert ipc7251.pad_diameter_mm(LEAD, "L") == pytest.approx(0.809)


def test_most_is_more_generous_than_nominal_than_least():
    # "Most material condition" (M) is the most generous/conservative
    # density level, "Least" (L) the tightest -- pad size should reflect
    # that ordering regardless of the exact constants used.
    m = ipc7251.pad_diameter_mm(LEAD, "M")
    n = ipc7251.pad_diameter_mm(LEAD, "N")
    l = ipc7251.pad_diameter_mm(LEAD, "L")
    assert m > n > l


def test_unknown_density_raises():
    with pytest.raises(ValueError):
        ipc7251.drill_diameter_mm(LEAD, "X")
    with pytest.raises(ValueError):
        ipc7251.pad_diameter_mm(LEAD, "X")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd jedec-fpdb && python -m pytest tests/test_ipc7251.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jedec_fpdb.ipc7251'`

- [ ] **Step 3: Write `jedec_fpdb/ipc7251.py`**

```python
"""IPC-7251 thru-hole land pattern sizing -- a best-effort reconstruction
from public secondary references. No copy of the actual (paywalled)
IPC-7251 document is available yet; see the design spec's Non-goals.
These constants should be replaced with the real standard's values if a
copy turns up.

Density level is one of "M" (Most material condition / Density Level A,
the most generous -- easiest to assemble/rework), "N" (Nominal / Level
B), or "L" (Least material condition / Level C, the tightest -- highest
density).
"""

_DENSITY_LEVELS = ("M", "N", "L")

# Hole diameter = lead diameter + this clearance.
_HOLE_CLEARANCE_MM = {"M": 0.25, "N": 0.20, "L": 0.15}

# Minimum annular ring (each side), added on top of the drill diameter
# to get the pad diameter.
_MIN_ANNULAR_RING_MM = {"M": 0.15, "N": 0.10, "L": 0.05}


def _check_density(density: str) -> None:
    if density not in _DENSITY_LEVELS:
        raise ValueError(
            f"unknown density level {density!r}, expected one of {_DENSITY_LEVELS}"
        )


def drill_diameter_mm(lead_diameter_mm: float, density: str) -> float:
    _check_density(density)
    return lead_diameter_mm + _HOLE_CLEARANCE_MM[density]


def pad_diameter_mm(lead_diameter_mm: float, density: str) -> float:
    _check_density(density)
    return drill_diameter_mm(lead_diameter_mm, density) + 2 * _MIN_ANNULAR_RING_MM[density]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd jedec-fpdb && python -m pytest tests/test_ipc7251.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd jedec-fpdb
git add jedec_fpdb/ipc7251.py tests/test_ipc7251.py
git commit -m "jedec-fpdb: add best-effort IPC-7251 thru-hole sizing formulas"
```

---

## Task 3: Geometry primitives + DIP generator

**Files:**
- Create: `jedec-fpdb/jedec_fpdb/geometry.py`
- Create: `jedec-fpdb/jedec_fpdb/dip.py`
- Test: `jedec-fpdb/tests/test_dip.py`

**Interfaces:**
- Consumes: `data.ms001_dip.{PITCH_MM, ROW_SPACING_MM, BODY_WIDTH_MM, LEAD_WIDTH_MAX_MM, body_length_mm}` (Task 1), `jedec_fpdb.ipc7251.{drill_diameter_mm, pad_diameter_mm}` (Task 2).
- Produces: `jedec_fpdb.geometry.Pad` (fields: `number: int, x_mm: float, y_mm: float, drill_mm: float, diameter_mm: float, shape: str`), `jedec_fpdb.geometry.RectOutline` (fields: `layer: str, x1_mm: float, y1_mm: float, x2_mm: float, y2_mm: float`), `jedec_fpdb.geometry.Footprint` (fields: `name: str, pads: list[Pad], silk_body: RectOutline | None, courtyard: RectOutline | None`); `jedec_fpdb.dip.generate(width_class: str, pin_count: int, density: str = "N") -> Footprint`, `jedec_fpdb.dip.SUPPORTED_WIDTH_CLASSES` (tuple of str).

- [ ] **Step 1: Write the failing test**

`jedec-fpdb/tests/test_dip.py`:
```python
import pytest

from jedec_fpdb import dip


def test_generate_produces_correct_pad_count():
    fp = dip.generate("narrow", 16, "N")
    assert len(fp.pads) == 16
    assert {p.number for p in fp.pads} == set(range(1, 17))


def test_pin1_is_rect_others_are_circle():
    fp = dip.generate("narrow", 16, "N")
    pad1 = next(p for p in fp.pads if p.number == 1)
    others = [p for p in fp.pads if p.number != 1]
    assert pad1.shape == "rect"
    assert all(p.shape == "circle" for p in others)


def test_row_spacing_and_pitch_match_ms001():
    from data import ms001_dip
    fp = dip.generate("narrow", 16, "N")
    pad1 = next(p for p in fp.pads if p.number == 1)
    pad2 = next(p for p in fp.pads if p.number == 2)
    pad9 = next(p for p in fp.pads if p.number == 9)  # first right-column pin (16/2 + 1)
    assert abs(pad2.y_mm - pad1.y_mm) == pytest.approx(ms001_dip.PITCH_MM)
    assert abs(pad9.x_mm - pad1.x_mm) == pytest.approx(ms001_dip.ROW_SPACING_MM)


def test_no_two_pads_share_a_position():
    fp = dip.generate("narrow", 24, "N")
    positions = [(round(p.x_mm, 6), round(p.y_mm, 6)) for p in fp.pads]
    assert len(positions) == len(set(positions))


def test_courtyard_encloses_all_pads():
    fp = dip.generate("narrow", 8, "N")
    for p in fp.pads:
        r = p.diameter_mm / 2
        assert fp.courtyard.x1_mm <= p.x_mm - r
        assert fp.courtyard.x2_mm >= p.x_mm + r
        assert fp.courtyard.y1_mm <= p.y_mm - r
        assert fp.courtyard.y2_mm >= p.y_mm + r


def test_unsupported_width_class_raises():
    with pytest.raises(ValueError):
        dip.generate("wide", 16, "N")


def test_invalid_pin_count_raises():
    with pytest.raises(ValueError):
        dip.generate("narrow", 15, "N")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd jedec-fpdb && python -m pytest tests/test_dip.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jedec_fpdb.dip'`

- [ ] **Step 3: Write `jedec_fpdb/geometry.py`**

```python
"""Plain geometry dataclasses for jedec-fpdb. Independent of
kicad-fpdb's own geometry module -- no shared code between the two
projects (see the design spec's Code sharing section)."""

from dataclasses import dataclass, field


@dataclass
class Pad:
    number: int
    x_mm: float
    y_mm: float
    drill_mm: float
    diameter_mm: float
    shape: str = "circle"  # "circle" (round) or "rect" (pin 1, square)


@dataclass
class RectOutline:
    layer: str
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float


@dataclass
class Footprint:
    name: str
    pads: list[Pad] = field(default_factory=list)
    silk_body: RectOutline | None = None
    courtyard: RectOutline | None = None
```

- [ ] **Step 4: Write `jedec_fpdb/dip.py`**

```python
"""DIP footprint generation, purely from JEDEC MS-001 + IPC-7251 -- see
docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md. No
kicad-fpdb code or data is imported or copied.

Pin layout matches how real DIP ICs are physically numbered: pin 1 at
the bottom of the left column, numbering up the left column, across,
then down the right column to the bottom-right pin. Pitch runs along Y
(the body's long axis); row spacing runs along X (the two columns'
separation) -- confirmed against a real DIP-8 reference file, whose
pad 5 (first right-column pin) sits at (row_spacing, pitch * (pins_per_row - 1))
relative to pad 1 at its own origin.
"""

from data import ms001_dip
from jedec_fpdb import ipc7251
from jedec_fpdb.geometry import Footprint, Pad, RectOutline

SUPPORTED_WIDTH_CLASSES = ("narrow",)

# Generic IPC land-pattern courtyard excess -- a commonly published
# default across density levels, not itself density-level-specific.
COURTYARD_MARGIN_MM = 0.25


def generate(width_class: str, pin_count: int, density: str = "N") -> Footprint:
    if width_class not in SUPPORTED_WIDTH_CLASSES:
        raise ValueError(
            f"unsupported width_class {width_class!r}, expected one of {SUPPORTED_WIDTH_CLASSES}"
        )
    if pin_count % 2 != 0 or pin_count < 4:
        raise ValueError(f"pin_count must be even and >= 4, got {pin_count}")

    pitch = ms001_dip.PITCH_MM
    row_spacing = ms001_dip.ROW_SPACING_MM
    pins_per_row = pin_count // 2

    drill = ipc7251.drill_diameter_mm(ms001_dip.LEAD_WIDTH_MAX_MM, density)
    pad_dia = ipc7251.pad_diameter_mm(ms001_dip.LEAD_WIDTH_MAX_MM, density)

    x_left, x_right = -row_spacing / 2, row_spacing / 2
    y0 = -pitch * (pins_per_row - 1) / 2
    top_y = -y0

    pads = [
        Pad(number=i + 1, x_mm=x_left, y_mm=y0 + i * pitch,
            drill_mm=drill, diameter_mm=pad_dia,
            shape="rect" if i == 0 else "circle")
        for i in range(pins_per_row)
    ]
    pads += [
        Pad(number=pins_per_row + i + 1, x_mm=x_right, y_mm=top_y - i * pitch,
            drill_mm=drill, diameter_mm=pad_dia, shape="circle")
        for i in range(pins_per_row)
    ]

    body_half_x = ms001_dip.BODY_WIDTH_MM / 2
    body_half_y = ms001_dip.body_length_mm(pin_count) / 2
    silk_body = RectOutline("F.SilkS", -body_half_x, -body_half_y, body_half_x, body_half_y)

    pad_bbox_half_x = row_spacing / 2 + pad_dia / 2
    pad_bbox_half_y = top_y + pad_dia / 2
    crtyd_half_x = max(body_half_x, pad_bbox_half_x) + COURTYARD_MARGIN_MM
    crtyd_half_y = max(body_half_y, pad_bbox_half_y) + COURTYARD_MARGIN_MM
    courtyard = RectOutline("F.CrtYd", -crtyd_half_x, -crtyd_half_y, crtyd_half_x, crtyd_half_y)

    name = f"DIP-{pin_count}_{width_class}_{density}"
    return Footprint(name=name, pads=pads, silk_body=silk_body, courtyard=courtyard)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd jedec-fpdb && python -m pytest tests/test_dip.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
cd jedec-fpdb
git add jedec_fpdb/geometry.py jedec_fpdb/dip.py tests/test_dip.py
git commit -m "jedec-fpdb: add geometry primitives and the DIP generator"
```

---

## Task 4: `.kicad_mod` writer

**Files:**
- Create: `jedec-fpdb/jedec_fpdb/writer.py`
- Test: `jedec-fpdb/tests/test_writer.py`

**Interfaces:**
- Consumes: `jedec_fpdb.geometry.Footprint` (Task 3), `jedec_fpdb.dip.generate` (Task 3, used only in the test to build a sample footprint).
- Produces: `jedec_fpdb.writer.write_footprint(footprint: Footprint, path: pathlib.Path) -> None`.

- [ ] **Step 1: Write the failing test**

`jedec-fpdb/tests/test_writer.py`:
```python
from jedec_fpdb import dip, writer


def test_write_footprint_contains_expected_tokens(tmp_path):
    fp = dip.generate("narrow", 4, "N")
    out_path = tmp_path / "test.kicad_mod"

    writer.write_footprint(fp, out_path)

    text = out_path.read_text()
    assert text.startswith('(footprint "DIP-4_narrow_N"')
    assert text.count('(pad "') == 4
    assert '(pad "1" thru_hole rect' in text
    assert '(pad "4" thru_hole circle' in text
    assert '(layer "F.SilkS")' in text
    assert '(layer "F.CrtYd")' in text
    pad1 = next(p for p in fp.pads if p.number == 1)
    assert f'(drill {pad1.drill_mm:.4f})' in text
    assert f'(size {pad1.diameter_mm:.4f} {pad1.diameter_mm:.4f})' in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd jedec-fpdb && python -m pytest tests/test_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jedec_fpdb.writer'`

- [ ] **Step 3: Write `jedec_fpdb/writer.py`**

```python
"""Serializes a Footprint to a real .kicad_mod file. An independent
implementation of the KiCad S-expression format -- reuses only format
knowledge, not code, from kicad-fpdb's own writer (see the design
spec's Code sharing section)."""

import uuid
from pathlib import Path

from jedec_fpdb.geometry import Footprint, RectOutline


def _rect_expr(rect: RectOutline, stroke_width_mm: float) -> str:
    return (
        f'\t(fp_rect\n'
        f'\t\t(start {rect.x1_mm:.4f} {rect.y1_mm:.4f}) (end {rect.x2_mm:.4f} {rect.y2_mm:.4f})\n'
        f'\t\t(stroke (width {stroke_width_mm}) (type default))\n'
        f'\t\t(fill none)\n'
        f'\t\t(layer "{rect.layer}")\n'
        f'\t\t(uuid "{uuid.uuid4()}")\n'
        f'\t)'
    )


def _pad_expr(pad) -> str:
    return (
        f'\t(pad "{pad.number}" thru_hole {pad.shape}\n'
        f'\t\t(at {pad.x_mm:.4f} {pad.y_mm:.4f})\n'
        f'\t\t(size {pad.diameter_mm:.4f} {pad.diameter_mm:.4f})\n'
        f'\t\t(drill {pad.drill_mm:.4f})\n'
        f'\t\t(layers "*.Cu" "*.Mask")\n'
        f'\t\t(remove_unused_layers no)\n'
        f'\t\t(uuid "{uuid.uuid4()}")\n'
        f'\t)'
    )


def write_footprint(footprint: Footprint, path: Path) -> None:
    lines = [
        f'(footprint "{footprint.name}"',
        '\t(version 20221018)',
        '\t(generator "jedec_fpdb")',
        '\t(layer "F.Cu")',
        '\t(attr through_hole)',
    ]
    if footprint.silk_body is not None:
        lines.append(_rect_expr(footprint.silk_body, 0.12))
    if footprint.courtyard is not None:
        lines.append(_rect_expr(footprint.courtyard, 0.05))
    for pad in footprint.pads:
        lines.append(_pad_expr(pad))
    lines.append(')')
    path.write_text('\n'.join(lines) + '\n')
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd jedec-fpdb && python -m pytest tests/test_writer.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
cd jedec-fpdb
git add jedec_fpdb/writer.py tests/test_writer.py
git commit -m "jedec-fpdb: add the .kicad_mod writer"
```

---

## Task 5: Comparison tool against real KiCad reference files

**Files:**
- Create: `jedec-fpdb/jedec_fpdb/compare.py`
- Test: `jedec-fpdb/tests/test_compare.py`

**Interfaces:**
- Consumes: `jedec_fpdb.geometry.Footprint` (Task 3), `jedec_fpdb.dip.generate` (Task 3, used in the test).
- Produces: `jedec_fpdb.compare.diff(generated: Footprint, real_text: str) -> dict[str, float]` (keys: `"pitch_mm"`, `"row_spacing_mm"`, `"drill_mm"`, `"pad_diameter_mm"`, `"courtyard_width_mm"`, `"courtyard_height_mm"`, each `generated - real`).

- [ ] **Step 1: Write the failing test**

`jedec-fpdb/tests/test_compare.py`:
```python
import os

import pytest

from jedec_fpdb import compare, dip

KICAD_DIP_DIR = "/usr/share/kicad/footprints/Package_DIP.pretty"

pytestmark = pytest.mark.skipif(
    not os.path.isdir(KICAD_DIP_DIR),
    reason=f"{KICAD_DIP_DIR} not present on this machine",
)

# (pin_count, real filename, drill/pad diameter tolerance is looser than
# pitch/row_spacing since our best-effort IPC-7251 constants are known
# to differ from KiCad's own generous, round-number pad sizing -- see
# the design spec).
CASES = [
    (8, "DIP-8_W7.62mm.kicad_mod"),
    (14, "DIP-14_W7.62mm.kicad_mod"),
    (16, "DIP-16_W7.62mm.kicad_mod"),
    (24, "DIP-24_W7.62mm.kicad_mod"),
]


@pytest.mark.parametrize("pin_count,filename", CASES)
def test_compare_against_real_dip_file(pin_count, filename):
    fp = dip.generate("narrow", pin_count, "N")
    real_text = open(f"{KICAD_DIP_DIR}/{filename}").read()

    deltas = compare.diff(fp, real_text)

    # Pitch and row spacing are both exact JEDEC Basic dimensions and
    # should match the real file exactly.
    assert abs(deltas["pitch_mm"]) < 0.01
    assert abs(deltas["row_spacing_mm"]) < 0.01
    # Drill/pad diameter and courtyard size are expected to deviate --
    # these bounds catch an implementation bug (wrong units, a
    # gross/order-of-magnitude mistake) without requiring an exact match
    # to KiCad's own conventions.
    assert abs(deltas["drill_mm"]) < 0.3
    assert abs(deltas["pad_diameter_mm"]) < 1.0
    assert abs(deltas["courtyard_width_mm"]) < 2.0
    assert abs(deltas["courtyard_height_mm"]) < 2.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd jedec-fpdb && python -m pytest tests/test_compare.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jedec_fpdb.compare'` (or, on a machine without the KiCad library installed, the whole module skips instead — that's also an acceptable outcome, but on this machine the library is present, so expect the import failure).

- [ ] **Step 3: Write `jedec_fpdb/compare.py`**

```python
"""Diff a generated Footprint against a real KiCad DIP reference file.

Reads the real file directly from the filesystem (read-only) -- see the
design spec's Code sharing section for why this doesn't import
kicad-fpdb code, only a plain path string that happens to match where
kicad-fpdb's own tests look.

Both real files used in this project's own tests draw F.SilkS with
fp_line/fp_arc (never a single fp_rect) and F.CrtYd as exactly one plain
fp_rect, so the courtyard regex below assumes there is exactly one
fp_rect block in the file.
"""

import re
from dataclasses import dataclass

from jedec_fpdb.geometry import Footprint

_PAD_RE = re.compile(
    r'\(pad "(\d+)" thru_hole \w+\s*'
    r'\(at\s+([-\d.]+)\s+([-\d.]+)\)\s*'
    r'\(size\s+([-\d.]+)\s+([-\d.]+)\)\s*'
    r'\(drill\s+([-\d.]+)\)'
)

_CRTYD_RE = re.compile(
    r'\(fp_rect\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)'
    r'.*?\(layer "F\.CrtYd"\)',
    re.DOTALL,
)


@dataclass
class _Measurements:
    pitch_mm: float
    row_spacing_mm: float
    drill_mm: float
    pad_diameter_mm: float
    courtyard_width_mm: float
    courtyard_height_mm: float


def _measure_pads(pads: list[tuple[int, float, float, float, float]]) -> tuple[float, float, float, float]:
    """pads: list of (number, x_mm, y_mm, drill_or_size_w_mm, drill_mm).
    Returns (pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm)."""
    by_number = {p[0]: p for p in pads}
    pins_per_row = len(pads) // 2
    pad1 = by_number[1]
    pad2 = by_number[2]
    pad_right_first = by_number[pins_per_row + 1]

    pitch_mm = abs(pad2[2] - pad1[2])
    row_spacing_mm = abs(pad_right_first[1] - pad1[1])
    pad_diameter_mm = pad1[3]
    drill_mm = pad1[4]
    return pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm


def parse_real_dip(text: str) -> _Measurements:
    pads = []
    for m in _PAD_RE.finditer(text):
        number, x, y, w, _h, drill = m.groups()
        pads.append((int(number), float(x), float(y), float(w), float(drill)))
    if len(pads) < 4:
        raise ValueError(f"expected at least 4 pads, found {len(pads)}")

    pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm = _measure_pads(pads)

    crtyd_match = _CRTYD_RE.search(text)
    if crtyd_match is None:
        raise ValueError("no F.CrtYd fp_rect found")
    x1, y1, x2, y2 = (float(v) for v in crtyd_match.groups())

    return _Measurements(
        pitch_mm=pitch_mm,
        row_spacing_mm=row_spacing_mm,
        drill_mm=drill_mm,
        pad_diameter_mm=pad_diameter_mm,
        courtyard_width_mm=abs(x2 - x1),
        courtyard_height_mm=abs(y2 - y1),
    )


def _measure_generated(fp: Footprint) -> _Measurements:
    pads = [(p.number, p.x_mm, p.y_mm, p.diameter_mm, p.drill_mm) for p in fp.pads]
    pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm = _measure_pads(pads)

    c = fp.courtyard
    return _Measurements(
        pitch_mm=pitch_mm,
        row_spacing_mm=row_spacing_mm,
        drill_mm=drill_mm,
        pad_diameter_mm=pad_diameter_mm,
        courtyard_width_mm=abs(c.x2_mm - c.x1_mm),
        courtyard_height_mm=abs(c.y2_mm - c.y1_mm),
    )


def diff(generated: Footprint, real_text: str) -> dict[str, float]:
    g = _measure_generated(generated)
    r = parse_real_dip(real_text)
    return {
        "pitch_mm": g.pitch_mm - r.pitch_mm,
        "row_spacing_mm": g.row_spacing_mm - r.row_spacing_mm,
        "drill_mm": g.drill_mm - r.drill_mm,
        "pad_diameter_mm": g.pad_diameter_mm - r.pad_diameter_mm,
        "courtyard_width_mm": g.courtyard_width_mm - r.courtyard_width_mm,
        "courtyard_height_mm": g.courtyard_height_mm - r.courtyard_height_mm,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd jedec-fpdb && python -m pytest tests/test_compare.py -v`
Expected: PASS (4 tests) if `/usr/share/kicad/footprints/Package_DIP.pretty` exists on this machine (it does, per the project's own CLAUDE.md); SKIPPED otherwise.

- [ ] **Step 5: Commit**

```bash
cd jedec-fpdb
git add jedec_fpdb/compare.py tests/test_compare.py
git commit -m "jedec-fpdb: add the real-file comparison tool"
```

---

## Task 6: CLI entry point + README

**Files:**
- Create: `jedec-fpdb/jedec_fpdb/__main__.py`
- Create: `jedec-fpdb/README.md`
- Test: `jedec-fpdb/tests/test_cli.py`

**Interfaces:**
- Consumes: `jedec_fpdb.dip.generate`, `jedec_fpdb.dip.SUPPORTED_WIDTH_CLASSES` (Task 3), `jedec_fpdb.writer.write_footprint` (Task 4).
- Produces: `jedec_fpdb.__main__.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing test**

`jedec-fpdb/tests/test_cli.py`:
```python
from jedec_fpdb.__main__ import main


def test_cli_writes_a_kicad_mod_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["narrow", "16"])

    assert exit_code == 0
    out_file = tmp_path / "DIP-16_narrow_N.kicad_mod"
    assert out_file.exists()
    assert out_file.read_text().count('(pad "') == 16


def test_cli_accepts_density_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    main(["narrow", "8", "--density", "M"])

    assert (tmp_path / "DIP-8_narrow_M.kicad_mod").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd jedec-fpdb && python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jedec_fpdb.__main__'`

- [ ] **Step 3: Write `jedec_fpdb/__main__.py`**

```python
"""CLI entry point: `python -m jedec_fpdb <width_class> <pin_count> [--density M|N|L] [--out PATH]`."""

import argparse
import sys
from pathlib import Path

from jedec_fpdb import dip, writer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jedec_fpdb")
    parser.add_argument("width_class", choices=dip.SUPPORTED_WIDTH_CLASSES)
    parser.add_argument("pin_count", type=int)
    parser.add_argument("--density", choices=("M", "N", "L"), default="N")
    parser.add_argument("--out", type=Path, default=None,
                         help="output .kicad_mod path (default: <name>.kicad_mod in cwd)")
    args = parser.parse_args(argv)

    footprint = dip.generate(args.width_class, args.pin_count, args.density)
    out_path = args.out or Path(f"{footprint.name}.kicad_mod")
    writer.write_footprint(footprint, out_path)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd jedec-fpdb && python -m pytest tests/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write `README.md`**

```markdown
# jedec-fpdb

A spec-derived DIP footprint generator: builds `.kicad_mod` files purely
from JEDEC MS-001 (package body/lead outline) and a best-effort
IPC-7251 (thru-hole land pattern sizing) formula, independent of
`kicad-fpdb`'s own reverse-engineered-from-real-files approach at the
repo root. See `docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md`
for the full design rationale.

Currently covers narrow (0.300in/7.62mm row spacing) DIP only, pin
counts 8 (extrapolated -- see the spec), 14, 16, 18, 20, 22, 24, 28.

## Usage

```bash
cd jedec-fpdb
python -m jedec_fpdb narrow 16                 # writes DIP-16_narrow_N.kicad_mod
python -m jedec_fpdb narrow 8 --density M      # Most (most generous) density level
```

## Tests

```bash
cd jedec-fpdb
python -m pytest -v
```

`tests/test_compare.py` diffs generated output against real KiCad
reference files and is skipped automatically if
`/usr/share/kicad/footprints/Package_DIP.pretty` isn't present on the
machine.

## Scope

Fully independent of `kicad-fpdb`: no shared code, no shared data. See
the design spec's Non-goals and Open follow-ups sections for what's
deliberately out of scope (regular/wide width classes, other package
families, IPC-7251 itself if a real copy turns up, cosmetic silkscreen
conventions).
```

- [ ] **Step 6: Run the full test suite**

Run: `cd jedec-fpdb && python -m pytest -v`
Expected: PASS (all tests across every task)

- [ ] **Step 7: Commit**

```bash
cd jedec-fpdb
git add jedec_fpdb/__main__.py README.md tests/test_cli.py
git commit -m "jedec-fpdb: add CLI entry point and README"
```
