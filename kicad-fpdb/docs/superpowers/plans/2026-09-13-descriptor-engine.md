# Descriptor + Generator Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python engine that parses a short footprint descriptor (e.g. `DIP-16 r 0.1`), resolves it against a hierarchical family-tree data file, generates footprint geometry, and writes a real `.kicad_mod` file — validated against KiCad's own official library.

**Architecture:** Four independently testable stages in a pipeline: descriptor parser → family-tree resolver → shape-generator library → KiCad writer. The family tree (`kicad-fpdb.yaml`) is plain data; the shape generators and writer are hand-written, unit-tested Python.

**Tech Stack:** Python 3.10+, PyYAML, pytest. Validation uses the locally installed `kicad-cli` (KiCad 10.0.6) and the official footprint library at `/usr/share/kicad/footprints/*.pretty`.

**Spec:** `docs/superpowers/specs/2026-09-13-descriptor-engine-design.md`

## Global Constraints

- Output must be valid `.kicad_mod` S-expression files, parseable by the locally installed `kicad-cli` (verified via `kicad-cli fp export svg`).
- Automated tests compare generated **pad** positions/sizes/shapes against real KiCad library files with float tolerance ~1e-4mm (µm-level rounding). Silkscreen/courtyard/fab outline geometry is NOT exact-matched by automated tests — only pads are.
- The family tree lives in one file: `data/kicad-fpdb.yaml`.
- 3D model references and footprint metadata (tags/description) are out of scope.
- Every family/generator combination needs at least one regression test against a real reference footprint file from the local KiCad install.

---

## File Structure

```
kicad_fpdb/
  __init__.py
  geometry.py              # Pad, FootprintGeometry dataclasses
  descriptor.py             # parse_descriptor()
  family_tree.py             # load_family_tree(), resolve_descriptor()
  writer.py                  # write_kicad_mod()
  pipeline.py                 # generate_footprint() — wires the four stages together
  generators/
    __init__.py
    dual_row.py               # dual_row_grid()  (DIP, SOIC)
    two_pad.py                 # two_pad_chip()   (R, C chip passives)
    quad_perimeter.py           # quad_perimeter() (QFP)

data/
  kicad-fpdb.yaml              # the family tree data file

tests/
  test_geometry.py
  test_writer.py
  test_descriptor.py
  test_family_tree.py
  test_generators_dual_row.py
  test_generators_two_pad.py
  test_generators_quad_perimeter.py
  test_pipeline_regression.py    # full-pipeline vs real KiCad library files
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `kicad_fpdb/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: an installed, importable `kicad_fpdb` package and a working `pytest` invocation for every later task.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "kicad-fpdb"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["pyyaml"]

[project.optional-dependencies]
dev = ["pytest"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["kicad_fpdb*"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Create empty package file**

Create `kicad_fpdb/__init__.py` (empty file).

- [ ] **Step 3: Install the package in editable/dev mode**

Run: `pip install -e ".[dev]"`
Expected: installs cleanly, no errors.

- [ ] **Step 4: Write the smoke test**

```python
# tests/test_smoke.py
import kicad_fpdb


def test_package_imports():
    assert kicad_fpdb is not None
```

- [ ] **Step 5: Run pytest to confirm baseline works**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml kicad_fpdb/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold kicad-fpdb Python package"
```

---

### Task 2: Geometry data model

**Files:**
- Create: `kicad_fpdb/geometry.py`
- Test: `tests/test_geometry.py`

**Interfaces:**
- Produces: `Pad` (fields: `number: str`, `pad_type: str`, `shape: str`, `at: tuple[float, float]`, `size: tuple[float, float]`, `drill: float | None`, `roundrect_rratio: float | None`), `FootprintGeometry` (fields: `name: str`, `pads: list[Pad]`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_geometry.py
from kicad_fpdb.geometry import Pad, FootprintGeometry


def test_pad_defaults():
    pad = Pad(number="1", pad_type="smd", shape="roundrect", at=(0.0, 0.0), size=(0.8, 0.95))
    assert pad.drill is None
    assert pad.roundrect_rratio is None


def test_footprint_geometry_holds_pads():
    pad = Pad(number="1", pad_type="smd", shape="roundrect", at=(0.0, 0.0), size=(0.8, 0.95))
    geom = FootprintGeometry(name="TEST", pads=[pad])
    assert geom.name == "TEST"
    assert geom.pads == [pad]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.geometry'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/geometry.py
from dataclasses import dataclass, field


@dataclass
class Pad:
    number: str
    pad_type: str  # "thru_hole" | "smd"
    shape: str  # "circle" | "roundrect"
    at: tuple[float, float]
    size: tuple[float, float]
    drill: float | None = None
    roundrect_rratio: float | None = None


@dataclass
class FootprintGeometry:
    name: str
    pads: list[Pad] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_geometry.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/geometry.py tests/test_geometry.py
git commit -m "feat: add FootprintGeometry/Pad data model"
```

---

### Task 3: KiCad writer

**Files:**
- Create: `kicad_fpdb/writer.py`
- Test: `tests/test_writer.py`

**Interfaces:**
- Consumes: `Pad`, `FootprintGeometry` from `kicad_fpdb.geometry`.
- Produces: `write_kicad_mod(name: str, geometry: FootprintGeometry) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_writer.py
import shutil
import subprocess

import pytest

from kicad_fpdb.geometry import FootprintGeometry, Pad
from kicad_fpdb.writer import write_kicad_mod


def test_write_pad_thru_hole_with_drill():
    pad = Pad(number="1", pad_type="thru_hole", shape="roundrect",
               at=(0.0, 0.0), size=(1.6, 1.6), drill=0.8, roundrect_rratio=0.15625)
    geom = FootprintGeometry(name="TEST_MIN", pads=[pad])
    text = write_kicad_mod("TEST_MIN", geom)
    assert '(footprint "TEST_MIN"' in text
    assert '(pad "1" thru_hole roundrect' in text
    assert "(at 0 0)" in text
    assert "(size 1.6 1.6)" in text
    assert "(drill 0.8)" in text
    assert '(layers "*.Cu" "*.Mask")' in text
    assert "(roundrect_rratio 0.15625)" in text


def test_write_pad_smd_no_drill():
    pad = Pad(number="2", pad_type="smd", shape="roundrect",
               at=(0.825, 0.0), size=(0.8, 0.95), roundrect_rratio=0.25)
    geom = FootprintGeometry(name="TEST_SMD", pads=[pad])
    text = write_kicad_mod("TEST_SMD", geom)
    assert '(pad "2" smd roundrect' in text
    assert "(drill" not in text
    assert '(layers "F.Cu" "F.Mask" "F.Paste")' in text


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_generated_file_is_valid_kicad_mod(tmp_path):
    pad1 = Pad(number="1", pad_type="thru_hole", shape="roundrect",
                at=(0.0, 0.0), size=(1.6, 1.6), drill=0.8, roundrect_rratio=0.15625)
    pad2 = Pad(number="2", pad_type="thru_hole", shape="circle",
                at=(0.0, 2.54), size=(1.6, 1.6), drill=0.8)
    geom = FootprintGeometry(name="TEST_MIN", pads=[pad1, pad2])
    text = write_kicad_mod("TEST_MIN", geom)

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "TEST_MIN.kicad_mod").write_text(text)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = subprocess.run(
        ["kicad-cli", "fp", "export", "svg", "--footprint", "TEST_MIN",
         str(lib_dir), "-o", str(out_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out_dir / "TEST_MIN.svg").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.writer'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/writer.py
from kicad_fpdb.geometry import FootprintGeometry, Pad


def write_kicad_mod(name: str, geometry: FootprintGeometry) -> str:
    lines = [
        f'(footprint "{name}"',
        "  (version 20240101)",
        '  (generator "kicad-fpdb")',
        '  (layer "F.Cu")',
    ]
    for pad in geometry.pads:
        lines.append(_write_pad(pad))
    lines.append(")")
    return "\n".join(lines) + "\n"


def _write_pad(pad: Pad) -> str:
    at_x, at_y = pad.at
    size_x, size_y = pad.size
    lines = [f'  (pad "{pad.number}" {pad.pad_type} {pad.shape}']
    lines.append(f"    (at {_fmt(at_x)} {_fmt(at_y)})")
    lines.append(f"    (size {_fmt(size_x)} {_fmt(size_y)})")
    if pad.drill is not None:
        lines.append(f"    (drill {_fmt(pad.drill)})")
    if pad.pad_type == "thru_hole":
        lines.append('    (layers "*.Cu" "*.Mask")')
    else:
        lines.append('    (layers "F.Cu" "F.Mask" "F.Paste")')
    if pad.roundrect_rratio is not None:
        lines.append(f"    (roundrect_rratio {_fmt(pad.roundrect_rratio)})")
    lines.append("  )")
    return "\n".join(lines)


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_writer.py -v`
Expected: PASS (3 tests; the `kicad-cli` test runs since it's installed locally at `/usr/bin/kicad-cli`, version 10.0.6).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/writer.py tests/test_writer.py
git commit -m "feat: add .kicad_mod S-expression writer"
```

---

### Task 4: Descriptor parser

**Files:**
- Create: `kicad_fpdb/descriptor.py`
- Test: `tests/test_descriptor.py`

**Interfaces:**
- Produces: `ParsedDescriptor` (fields: `family: str`, `variant: str`, `modifier_tokens: list[str]`), `parse_descriptor(text: str) -> ParsedDescriptor`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_descriptor.py
import pytest

from kicad_fpdb.descriptor import ParsedDescriptor, parse_descriptor


def test_parse_family_variant_and_modifiers():
    result = parse_descriptor("DIP-16 r 0.1")
    assert result == ParsedDescriptor(family="DIP", variant="16", modifier_tokens=["r", "0.1"])


def test_parse_no_modifiers():
    result = parse_descriptor("SOIC-8")
    assert result == ParsedDescriptor(family="SOIC", variant="8", modifier_tokens=[])


def test_parse_non_numeric_variant():
    result = parse_descriptor("R-0603")
    assert result == ParsedDescriptor(family="R", variant="0603", modifier_tokens=[])


def test_parse_empty_string_raises():
    with pytest.raises(ValueError):
        parse_descriptor("")


def test_parse_missing_dash_raises():
    with pytest.raises(ValueError):
        parse_descriptor("DIP16")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_descriptor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.descriptor'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/descriptor.py
from dataclasses import dataclass, field


@dataclass
class ParsedDescriptor:
    family: str
    variant: str
    modifier_tokens: list[str] = field(default_factory=list)


def parse_descriptor(text: str) -> ParsedDescriptor:
    tokens = text.split()
    if not tokens:
        raise ValueError("descriptor must not be empty")

    head, *modifier_tokens = tokens
    if "-" not in head:
        raise ValueError(f"descriptor must start with FAMILY-VARIANT, got {head!r}")

    family, variant = head.split("-", 1)
    if not family or not variant:
        raise ValueError(f"descriptor must start with FAMILY-VARIANT, got {head!r}")

    return ParsedDescriptor(family=family, variant=variant, modifier_tokens=modifier_tokens)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_descriptor.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/descriptor.py tests/test_descriptor.py
git commit -m "feat: add family-agnostic descriptor parser"
```

---

### Task 5: Family tree loader

**Files:**
- Create: `kicad_fpdb/family_tree.py`
- Test: `tests/test_family_tree.py`

**Interfaces:**
- Produces: `FamilyNode` (fields: `name: str`, `generator: str | None`, `params: dict`, `variants: dict`, `default_width: str | None`, `variant_param: str`, `children: dict[str, FamilyNode]`), `load_family_tree(path: str) -> dict[str, FamilyNode]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_family_tree.py
from kicad_fpdb.family_tree import FamilyNode, load_family_tree

SAMPLE_YAML = """
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: regular
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    pad_size: [1.6, 1.6]
  children:
    DIP-SKINNY:
      params:
        pitch: 1.778
"""


def test_load_family_tree_builds_node_and_child(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(SAMPLE_YAML)

    tree = load_family_tree(str(path))

    assert set(tree.keys()) == {"DIP"}
    dip = tree["DIP"]
    assert isinstance(dip, FamilyNode)
    assert dip.generator == "dual_row_grid"
    assert dip.variant_param == "pin_count"
    assert dip.variants == {"n": "narrow", "r": "regular", "w": "wide"}
    assert dip.default_width == "regular"
    assert dip.params["pitch"] == 2.54
    assert dip.params["row_spacing"] == {"narrow": 7.62, "regular": 10.16, "wide": 15.24}

    child = dip.children["DIP-SKINNY"]
    assert child.name == "DIP-SKINNY"
    assert child.params == {"pitch": 1.778}
    assert child.generator is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_family_tree.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.family_tree'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/family_tree.py
from dataclasses import dataclass, field

import yaml


@dataclass
class FamilyNode:
    name: str
    generator: str | None = None
    params: dict = field(default_factory=dict)
    variants: dict = field(default_factory=dict)
    default_width: str | None = None
    variant_param: str = "pin_count"
    children: dict = field(default_factory=dict)


def _build_node(name: str, data: dict) -> FamilyNode:
    node = FamilyNode(
        name=name,
        generator=data.get("generator"),
        params=data.get("params", {}),
        variants=data.get("variants", {}),
        default_width=data.get("default_width"),
        variant_param=data.get("variant_param", "pin_count"),
    )
    for child_name, child_data in data.get("children", {}).items():
        node.children[child_name] = _build_node(child_name, child_data)
    return node


def load_family_tree(path: str) -> dict:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return {name: _build_node(name, data) for name, data in raw.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_family_tree.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/family_tree.py tests/test_family_tree.py
git commit -m "feat: add family tree YAML loader"
```

---

### Task 6: Family tree resolver

**Files:**
- Modify: `kicad_fpdb/family_tree.py`
- Modify: `tests/test_family_tree.py`

**Interfaces:**
- Consumes: `FamilyNode` (Task 5), `ParsedDescriptor` (Task 4).
- Produces: `ResolvedFootprint` (fields: `generator: str`, `params: dict`), `resolve_descriptor(roots: dict, parsed: ParsedDescriptor) -> ResolvedFootprint`.

This handles two kinds of families:
- **Formula families** (e.g. DIP, SOIC, QFP): the descriptor's variant token (e.g. `16`) is injected live into `params[variant_param]` (e.g. `pin_count`). Width-code modifiers (e.g. `r`) select a value out of any dict-valued param (e.g. `row_spacing`).
- **Enumerated families** (e.g. R, C chip sizes): the tree has a leaf node literally named `f"{family}-{variant}"` (e.g. `R-0603`) with its geometry fully specified in that node's own `params` — no live variant injection.

`resolve_descriptor` tries the enumerated (full-name) lookup first; if no such node exists, it falls back to the formula (family-name) lookup.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_family_tree.py`:

```python
from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import ResolvedFootprint, resolve_descriptor

FORMULA_YAML = """
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: regular
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    pad_size: [1.6, 1.6]
    pad_shape: dip_pin1_marker
    pad_type: thru_hole
    drill: 0.8
    centered: false
"""

ENUMERATED_YAML = """
R:
  children:
    R-0603:
      generator: two_pad_chip
      params:
        pad_pitch: 1.65
        pad_size: [0.8, 0.95]
"""


def test_resolve_formula_family_with_width_and_pitch_override(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(FORMULA_YAML)
    tree = load_family_tree(str(path))

    resolved = resolve_descriptor(tree, parse_descriptor("DIP-16 r 0.1"))

    assert resolved == ResolvedFootprint(
        generator="dual_row_grid",
        params={
            "pin_count": 16,
            "pitch": 0.1,
            "row_spacing": 10.16,
            "pad_size": [1.6, 1.6],
            "pad_shape": "dip_pin1_marker",
            "pad_type": "thru_hole",
            "drill": 0.8,
            "centered": False,
        },
    )


def test_resolve_formula_family_default_width(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(FORMULA_YAML)
    tree = load_family_tree(str(path))

    resolved = resolve_descriptor(tree, parse_descriptor("DIP-16"))

    assert resolved.params["row_spacing"] == 10.16
    assert resolved.params["pitch"] == 2.54
    assert resolved.params["pin_count"] == 16


def test_resolve_enumerated_family(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(ENUMERATED_YAML)
    tree = load_family_tree(str(path))

    resolved = resolve_descriptor(tree, parse_descriptor("R-0603"))

    assert resolved == ResolvedFootprint(
        generator="two_pad_chip",
        params={"pad_pitch": 1.65, "pad_size": [0.8, 0.95]},
    )


def test_resolve_unknown_family_raises(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(FORMULA_YAML)
    tree = load_family_tree(str(path))

    import pytest
    with pytest.raises(KeyError):
        resolve_descriptor(tree, parse_descriptor("QFP-32"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_family_tree.py -v`
Expected: FAIL — `resolve_descriptor` / `ResolvedFootprint` not defined.

- [ ] **Step 3: Add the resolver implementation**

Append to `kicad_fpdb/family_tree.py`:

```python
@dataclass
class ResolvedFootprint:
    generator: str
    params: dict


def _find_chain(roots: dict, target_name: str):
    def search(node: FamilyNode, chain: list):
        chain = chain + [node]
        if node.name == target_name:
            return chain
        for child in node.children.values():
            found = search(child, chain)
            if found:
                return found
        return None

    for root in roots.values():
        found = search(root, [])
        if found:
            return found
    return None


def _merge_params(chain: list) -> dict:
    merged: dict = {}
    for node in chain:
        for key, value in node.params.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def _resolve_meta(chain: list, attr: str, default):
    value = default
    for node in chain:
        candidate = getattr(node, attr)
        if candidate:
            value = candidate
    return value


def resolve_descriptor(roots: dict, parsed) -> ResolvedFootprint:
    full_name = f"{parsed.family}-{parsed.variant}"
    chain = _find_chain(roots, full_name)
    inject_variant = chain is None
    if chain is None:
        chain = _find_chain(roots, parsed.family)
    if chain is None:
        raise KeyError(f"unknown family {parsed.family!r}")

    params = _merge_params(chain)
    variants = _resolve_meta(chain, "variants", {})
    default_width = _resolve_meta(chain, "default_width", None)
    variant_param = _resolve_meta(chain, "variant_param", "pin_count")
    generator = _resolve_meta(chain, "generator", None)
    if generator is None:
        raise ValueError(f"no generator defined for family {parsed.family!r}")

    width_name = default_width
    for token in parsed.modifier_tokens:
        if token in variants:
            width_name = variants[token]
        else:
            try:
                params["pitch"] = float(token)
            except ValueError:
                raise ValueError(f"unknown modifier {token!r} for family {parsed.family!r}")

    resolved_params = {}
    for key, value in params.items():
        if isinstance(value, dict):
            if width_name is None:
                raise ValueError(f"family {parsed.family!r} requires a width modifier for {key!r}")
            resolved_params[key] = value[width_name]
        else:
            resolved_params[key] = value

    if inject_variant and variant_param:
        variant_token = parsed.variant
        resolved_params[variant_param] = int(variant_token) if variant_token.isdigit() else variant_token

    return ResolvedFootprint(generator=generator, params=resolved_params)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_family_tree.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/family_tree.py tests/test_family_tree.py
git commit -m "feat: add family tree inheritance resolver"
```

---

### Task 7: `dual_row_grid` generator — DIP (corner-origin, thru-hole)

**Files:**
- Create: `kicad_fpdb/generators/__init__.py` (empty)
- Create: `kicad_fpdb/generators/dual_row.py`
- Test: `tests/test_generators_dual_row.py`

**Interfaces:**
- Consumes: `Pad`, `FootprintGeometry` from `kicad_fpdb.geometry`.
- Produces: `dual_row_grid(pin_count: int, pitch: float, row_spacing: float, pad_size: tuple[float, float], pad_shape: str, pad_type: str, drill: float | None = None, centered: bool = False) -> FootprintGeometry`.

Reference data below is taken directly from `/usr/share/kicad/footprints/Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod` (pins 1, 2, 8, 9, 16).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generators_dual_row.py
from kicad_fpdb.generators.dual_row import dual_row_grid


def test_dip16_matches_real_kicad_footprint():
    geom = dual_row_grid(
        pin_count=16, pitch=2.54, row_spacing=7.62,
        pad_size=(1.6, 1.6), pad_shape="dip_pin1_marker",
        pad_type="thru_hole", drill=0.8, centered=False,
    )
    assert len(geom.pads) == 16

    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert pad1.at == (0.0, 0.0)
    assert pad1.shape == "roundrect"
    assert pad1.pad_type == "thru_hole"
    assert pad1.drill == 0.8
    assert abs(pad1.roundrect_rratio - 0.15625) < 1e-4

    pad2 = by_number["2"]
    assert pad2.at == (0.0, 2.54)
    assert pad2.shape == "circle"
    assert pad2.roundrect_rratio is None

    pad8 = by_number["8"]
    assert pad8.at == (0.0, 17.78)

    pad9 = by_number["9"]
    assert pad9.at == (7.62, 17.78)
    assert pad9.shape == "circle"

    pad16 = by_number["16"]
    assert pad16.at == (7.62, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generators_dual_row.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.generators'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/generators/dual_row.py
from kicad_fpdb.geometry import FootprintGeometry, Pad


def dual_row_grid(pin_count: int, pitch: float, row_spacing: float,
                   pad_size: tuple[float, float], pad_shape: str,
                   pad_type: str, drill: float | None = None,
                   centered: bool = False) -> FootprintGeometry:
    if pin_count % 2 != 0:
        raise ValueError("dual_row_grid requires an even pin_count")
    pins_per_row = pin_count // 2

    if centered:
        y0 = -pitch * (pins_per_row - 1) / 2
        x_left, x_right = -row_spacing / 2, row_spacing / 2
    else:
        y0 = 0.0
        x_left, x_right = 0.0, row_spacing

    pads = []
    for i in range(pins_per_row):
        pin1 = i == 0
        shape = "roundrect" if (pad_shape == "dip_pin1_marker" and pin1) else (
            "circle" if pad_shape == "dip_pin1_marker" else "roundrect"
        )
        pads.append(Pad(
            number=str(i + 1), pad_type=pad_type, shape=shape,
            at=(x_left, y0 + i * pitch), size=pad_size, drill=drill,
            roundrect_rratio=_round_ratio(pad_shape, shape, pad_size),
        ))

    top_y = y0 + (pins_per_row - 1) * pitch
    for i in range(pins_per_row):
        shape = "circle" if pad_shape == "dip_pin1_marker" else "roundrect"
        pads.append(Pad(
            number=str(pins_per_row + i + 1), pad_type=pad_type, shape=shape,
            at=(x_right, top_y - i * pitch), size=pad_size, drill=drill,
            roundrect_rratio=_round_ratio(pad_shape, shape, pad_size),
        ))

    return FootprintGeometry(name="", pads=pads)


def _round_ratio(pad_shape: str, shape: str, pad_size: tuple[float, float]) -> float | None:
    if shape != "roundrect":
        return None
    if pad_shape == "dip_pin1_marker":
        return round(0.25 / min(pad_size), 5)
    return 0.25
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generators_dual_row.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/generators/__init__.py kicad_fpdb/generators/dual_row.py tests/test_generators_dual_row.py
git commit -m "feat: add dual_row_grid generator, verified against DIP-16"
```

---

### Task 8: `dual_row_grid` — SOIC (centered-origin, SMD)

**Files:**
- Modify: `tests/test_generators_dual_row.py`

**Interfaces:**
- Consumes: `dual_row_grid` (Task 7) — no code change needed, only new test coverage of the `centered=True` / SMD path.

Reference data taken from `/usr/share/kicad/footprints/Package_SO.pretty/SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod` (pins 1, 4, 5, 8).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_generators_dual_row.py`:

```python
def test_soic8_matches_real_kicad_footprint():
    geom = dual_row_grid(
        pin_count=8, pitch=1.27, row_spacing=4.95,
        pad_size=(1.95, 0.6), pad_shape="roundrect",
        pad_type="smd", drill=None, centered=True,
    )
    assert len(geom.pads) == 8
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-2.475)) < 1e-6
    assert abs(pad1.at[1] - (-1.905)) < 1e-6
    assert pad1.pad_type == "smd"
    assert pad1.roundrect_rratio == 0.25

    pad4 = by_number["4"]
    assert abs(pad4.at[0] - (-2.475)) < 1e-6
    assert abs(pad4.at[1] - 1.905) < 1e-6

    pad5 = by_number["5"]
    assert abs(pad5.at[0] - 2.475) < 1e-6
    assert abs(pad5.at[1] - 1.905) < 1e-6

    pad8 = by_number["8"]
    assert abs(pad8.at[0] - 2.475) < 1e-6
    assert abs(pad8.at[1] - (-1.905)) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generators_dual_row.py::test_soic8_matches_real_kicad_footprint -v`
Expected: FAIL (assertions don't match yet — actually this should already pass since `dual_row_grid` from Task 7 already supports `centered`; if it fails, the `centered` branch has a bug — fix it, don't skip this step).

- [ ] **Step 3: Confirm/fix implementation**

No new code expected — `dual_row_grid`'s `centered` branch (written in Task 7) should already satisfy this. If the test fails, fix `kicad_fpdb/generators/dual_row.py` until it passes.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generators_dual_row.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_generators_dual_row.py
git commit -m "test: verify dual_row_grid centered/SMD mode against SOIC-8"
```

---

### Task 9: `two_pad_chip` generator (chip resistors/capacitors)

**Files:**
- Create: `kicad_fpdb/generators/two_pad.py`
- Test: `tests/test_generators_two_pad.py`

**Interfaces:**
- Produces: `two_pad_chip(pad_pitch: float, pad_size: tuple[float, float], pad_shape: str = "roundrect", roundrect_rratio: float = 0.25) -> FootprintGeometry`.

Reference data from `/usr/share/kicad/footprints/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generators_two_pad.py
from kicad_fpdb.generators.two_pad import two_pad_chip


def test_r0603_matches_real_kicad_footprint():
    geom = two_pad_chip(pad_pitch=1.65, pad_size=(0.8, 0.95))
    assert len(geom.pads) == 2
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-0.825)) < 1e-6
    assert pad1.at[1] == 0.0
    assert pad1.size == (0.8, 0.95)
    assert pad1.pad_type == "smd"
    assert pad1.roundrect_rratio == 0.25

    pad2 = by_number["2"]
    assert abs(pad2.at[0] - 0.825) < 1e-6
    assert pad2.at[1] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generators_two_pad.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.generators.two_pad'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/generators/two_pad.py
from kicad_fpdb.geometry import FootprintGeometry, Pad


def two_pad_chip(pad_pitch: float, pad_size: tuple[float, float],
                  pad_shape: str = "roundrect", roundrect_rratio: float = 0.25) -> FootprintGeometry:
    half = pad_pitch / 2
    rratio = roundrect_rratio if pad_shape == "roundrect" else None
    pads = [
        Pad(number="1", pad_type="smd", shape=pad_shape, at=(-half, 0.0),
            size=pad_size, roundrect_rratio=rratio),
        Pad(number="2", pad_type="smd", shape=pad_shape, at=(half, 0.0),
            size=pad_size, roundrect_rratio=rratio),
    ]
    return FootprintGeometry(name="", pads=pads)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generators_two_pad.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/generators/two_pad.py tests/test_generators_two_pad.py
git commit -m "feat: add two_pad_chip generator, verified against R_0603"
```

---

### Task 10: `quad_perimeter` generator (QFP)

**Files:**
- Create: `kicad_fpdb/generators/quad_perimeter.py`
- Test: `tests/test_generators_quad_perimeter.py`

**Interfaces:**
- Produces: `quad_perimeter(pin_count: int, pitch: float, pad_offset: float, pad_size: tuple[float, float]) -> FootprintGeometry`.

Reference data from `/usr/share/kicad/footprints/Package_QFP.pretty/LQFP-32_7x7mm_P0.8mm.kicad_mod` (pins 1, 8, 9, 17).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generators_quad_perimeter.py
from kicad_fpdb.generators.quad_perimeter import quad_perimeter


def test_lqfp32_matches_real_kicad_footprint():
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_offset=4.175, pad_size=(1.5, 0.5))
    assert len(geom.pads) == 32
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-4.175)) < 1e-6
    assert abs(pad1.at[1] - (-2.8)) < 1e-6
    assert pad1.size == (1.5, 0.5)

    pad8 = by_number["8"]
    assert abs(pad8.at[0] - (-4.175)) < 1e-6
    assert abs(pad8.at[1] - 2.8) < 1e-6

    pad9 = by_number["9"]
    assert abs(pad9.at[0] - (-2.8)) < 1e-6
    assert abs(pad9.at[1] - 4.175) < 1e-6
    assert pad9.size == (0.5, 1.5)

    pad17 = by_number["17"]
    assert abs(pad17.at[0] - 4.175) < 1e-6
    assert abs(pad17.at[1] - 2.8) < 1e-6
    assert pad17.size == (1.5, 0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generators_quad_perimeter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.generators.quad_perimeter'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/generators/quad_perimeter.py
from kicad_fpdb.geometry import FootprintGeometry, Pad


def quad_perimeter(pin_count: int, pitch: float, pad_offset: float,
                    pad_size: tuple[float, float]) -> FootprintGeometry:
    if pin_count % 4 != 0:
        raise ValueError("quad_perimeter requires pin_count divisible by 4")
    pins_per_side = pin_count // 4
    half_span = (pins_per_side - 1) * pitch / 2
    long, short = pad_size

    pads = []
    n = 1
    for i in range(pins_per_side):  # left side
        y = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(-pad_offset, y), size=(long, short), roundrect_rratio=0.25))
        n += 1
    for i in range(pins_per_side):  # bottom side
        x = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, pad_offset), size=(short, long), roundrect_rratio=0.25))
        n += 1
    for i in range(pins_per_side):  # right side
        y = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(pad_offset, y), size=(long, short), roundrect_rratio=0.25))
        n += 1
    for i in range(pins_per_side):  # top side
        x = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, -pad_offset), size=(short, long), roundrect_rratio=0.25))
        n += 1

    return FootprintGeometry(name="", pads=pads)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generators_quad_perimeter.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/generators/quad_perimeter.py tests/test_generators_quad_perimeter.py
git commit -m "feat: add quad_perimeter generator, verified against LQFP-32"
```

---

### Task 11: Family tree data file

**Files:**
- Create: `data/kicad-fpdb.yaml`

**Interfaces:**
- Consumes: nothing (pure data). Loaded by `load_family_tree` (Task 5) in Task 12.

- [ ] **Step 1: Write `data/kicad-fpdb.yaml`**

```yaml
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: regular
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    pad_size: [1.6, 1.6]
    pad_shape: dip_pin1_marker
    pad_type: thru_hole
    drill: 0.8
    centered: false

SOIC:
  generator: dual_row_grid
  variant_param: pin_count
  params:
    pitch: 1.27
    row_spacing: 4.95
    pad_size: [1.95, 0.6]
    pad_shape: roundrect
    pad_type: smd
    centered: true

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

C:
  children:
    C-0603:
      generator: two_pad_chip
      params: {pad_pitch: 1.55, pad_size: [0.9, 0.95]}

QFP:
  children:
    QFP-32:
      generator: quad_perimeter
      params: {pin_count: 32, pitch: 0.8, pad_offset: 4.175, pad_size: [1.5, 0.5]}
    QFP-48:
      generator: quad_perimeter
      params: {pin_count: 48, pitch: 0.5, pad_offset: 4.1625, pad_size: [1.475, 0.3]}
```

- [ ] **Step 2: Sanity-check it loads without error**

Run: `python -c "from kicad_fpdb.family_tree import load_family_tree; t = load_family_tree('data/kicad-fpdb.yaml'); print(sorted(t.keys()))"`
Expected: prints `['C', 'DIP', 'QFP', 'R', 'SOIC']` with no traceback.

- [ ] **Step 3: Commit**

```bash
git add data/kicad-fpdb.yaml
git commit -m "data: add initial family tree covering DIP, SOIC, R, C, QFP"
```

---

### Task 12: Pipeline orchestration + first full-pipeline regression test

**Files:**
- Create: `kicad_fpdb/pipeline.py`
- Test: `tests/test_pipeline_regression.py`

**Interfaces:**
- Consumes: `parse_descriptor` (Task 4), `load_family_tree`/`resolve_descriptor` (Tasks 5-6), `dual_row_grid`/`two_pad_chip`/`quad_perimeter` (Tasks 7-10), `write_kicad_mod` (Task 3).
- Produces: `generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str` (returns the `.kicad_mod` file text).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_regression.py
import re

import pytest

from kicad_fpdb.pipeline import generate_footprint

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"
KICAD_FOOTPRINTS = "/usr/share/kicad/footprints"


def _parse_real_pads(path: str) -> dict[str, tuple[float, float]]:
    """Extracts {pad_number: (x, y)} from a real .kicad_mod file."""
    text = open(path).read()
    pads = {}
    for match in re.finditer(r'\(pad "(\d+)" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)', text):
        number, x, y = match.groups()
        pads[number] = (float(x), float(y))
    return pads


def test_dip16_pipeline_matches_real_footprint():
    generated = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP-16_TEST")
    real_pads = _parse_real_pads(f"{KICAD_FOOTPRINTS}/Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod")

    generated_pads = {}
    for match in re.finditer(r'\(pad "(\d+)" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)', generated):
        number, x, y = match.groups()
        generated_pads[number] = (float(x), float(y))

    assert set(generated_pads.keys()) == set(real_pads.keys())
    for number, (rx, ry) in real_pads.items():
        gx, gy = generated_pads[number]
        assert abs(gx - rx) < 1e-4
        assert abs(gy - ry) < 1e-4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_regression.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_fpdb.pipeline'`

- [ ] **Step 3: Write the implementation**

```python
# kicad_fpdb/pipeline.py
from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.dual_row import dual_row_grid
from kicad_fpdb.generators.quad_perimeter import quad_perimeter
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.writer import write_kicad_mod

GENERATORS = {
    "dual_row_grid": dual_row_grid,
    "two_pad_chip": two_pad_chip,
    "quad_perimeter": quad_perimeter,
}


def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**resolved.params)
    geometry.name = name

    return write_kicad_mod(name, geometry)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_regression.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_regression.py
git commit -m "feat: wire descriptor->geometry->file pipeline, verified against DIP-16"
```

---

### Task 13: Expand regression suite across families and variants

**Files:**
- Modify: `tests/test_pipeline_regression.py`

**Interfaces:**
- Consumes: `generate_footprint` (Task 12) — no production code changes, only broader test coverage per the spec's requirement to cover multiple variants per family.

- [ ] **Step 1: Refactor the existing test into a parametrized helper**

Replace the body of `tests/test_pipeline_regression.py` with:

```python
# tests/test_pipeline_regression.py
import re

import pytest

from kicad_fpdb.pipeline import generate_footprint

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"
KICAD_FOOTPRINTS = "/usr/share/kicad/footprints"

PAD_PATTERN = re.compile(r'\(pad "(\d+)" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)')


def _parse_pads(text: str) -> dict[str, tuple[float, float]]:
    return {m.group(1): (float(m.group(2)), float(m.group(3))) for m in PAD_PATTERN.finditer(text)}


CASES = [
    # (descriptor, real reference file, args passed at resolve time)
    ("DIP-16", "Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod"),
    ("DIP-14", "Package_DIP.pretty/DIP-14_W7.62mm.kicad_mod"),
    ("DIP-18", "Package_DIP.pretty/DIP-18_W7.62mm.kicad_mod"),
    ("DIP-16 r", "Package_DIP.pretty/DIP-16_W10.16mm.kicad_mod"),
    ("SOIC-8", "Package_SO.pretty/SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod"),
    ("SOIC-14", "Package_SO.pretty/SOIC-14_3.9x8.7mm_P1.27mm.kicad_mod"),
    ("R-0402", "Resistor_SMD.pretty/R_0402_1005Metric.kicad_mod"),
    ("R-0603", "Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod"),
    ("R-0805", "Resistor_SMD.pretty/R_0805_2012Metric.kicad_mod"),
    ("C-0603", "Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod"),
    ("QFP-32", "Package_QFP.pretty/LQFP-32_7x7mm_P0.8mm.kicad_mod"),
    ("QFP-48", "Package_QFP.pretty/LQFP-48_7x7mm_P0.5mm.kicad_mod"),
]


@pytest.mark.parametrize("descriptor,reference_relpath", CASES)
def test_pipeline_matches_real_footprint(descriptor, reference_relpath):
    generated = generate_footprint(descriptor, FAMILY_TREE_PATH, name="TEST")
    real_text = open(f"{KICAD_FOOTPRINTS}/{reference_relpath}").read()

    generated_pads = _parse_pads(generated)
    real_pads = _parse_pads(real_text)

    assert set(generated_pads.keys()) == set(real_pads.keys()), descriptor
    for number, (rx, ry) in real_pads.items():
        gx, gy = generated_pads[number]
        assert abs(gx - rx) < 1e-4, f"{descriptor} pad {number} x"
        assert abs(gy - ry) < 1e-4, f"{descriptor} pad {number} y"
```

- [ ] **Step 2: Run the full regression suite**

Run: `pytest tests/test_pipeline_regression.py -v`
Expected: PASS (12 cases). If any case fails, it means either the family tree data (Task 11) or a generator (Tasks 7-10) has a bug for that specific variant — fix the root cause, don't adjust the expected reference data.

- [ ] **Step 3: Run the entire test suite to confirm nothing regressed**

Run: `pytest -v`
Expected: PASS (all tests across all previous tasks, plus these 12).

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline_regression.py
git commit -m "test: expand pipeline regression suite to 12 variants across 5 families"
```

---

### Task 14: Manual visual spot-check

**Files:** none (manual verification task, no code changes)

**Interfaces:** none — this task validates Task 13's output visually, per the spec's "manual spot-check" requirement.

- [ ] **Step 1: Generate a handful of footprints into a scratch library**

```bash
mkdir -p /tmp/kicad-fpdb-spotcheck
python - <<'EOF'
from kicad_fpdb.pipeline import generate_footprint

cases = [
    ("DIP-16 r 0.1", "DIP16_check"),
    ("SOIC-8", "SOIC8_check"),
    ("R-0603", "R0603_check"),
    ("QFP-32", "QFP32_check"),
]
for descriptor, name in cases:
    text = generate_footprint(descriptor, "data/kicad-fpdb.yaml", name=name)
    with open(f"/tmp/kicad-fpdb-spotcheck/{name}.kicad_mod", "w") as f:
        f.write(text)
EOF
```

- [ ] **Step 2: Open the scratch library in KiCad's footprint editor**

Run: `kicad-cli fp export svg /tmp/kicad-fpdb-spotcheck -o /tmp/kicad-fpdb-spotcheck/svg`, then view the SVGs (or open `/tmp/kicad-fpdb-spotcheck` directly as a footprint library in the KiCad footprint editor GUI).

- [ ] **Step 3: Confirm each footprint looks reasonable**

Check: pad shapes/sizes look sane, pin 1 is distinguishable (roundrect vs. circle for DIP), no overlapping pads. There is no silkscreen/courtyard yet (out of scope per this plan) — the check is limited to pad layout.

- [ ] **Step 4: Note findings**

If anything looks wrong, file it as a follow-up — do not silently patch generator math to "look better" without a corresponding failing automated test first (see Task 13).

---

## Out of Scope (future plans, per the design spec)

- Silkscreen/courtyard/fab outline geometry generation.
- 3D model references and footprint metadata.
- Full-library conversion pipeline.
- KiCad plugin/UI integration.
- Community contribution/moderation server.
- Descriptor grammar extensions beyond `FAMILY-VARIANT [MODIFIER...]` (e.g. pitch-code modifiers for QFP families, needed once more QFP pitch variants are added).
