from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import (
    FamilyNode,
    ResolvedFootprint,
    load_family_tree,
    resolve_descriptor,
)

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
        resolve_descriptor(tree, parse_descriptor("LQFP-32"))


NO_DEFAULT_WIDTH_YAML = """
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, wide: 15.24}
    pad_size: [1.6, 1.6]
"""


def test_resolve_dict_param_without_width_raises(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(NO_DEFAULT_WIDTH_YAML)
    tree = load_family_tree(str(path))

    import pytest
    # No default_width is set on the node and the descriptor supplies no
    # width modifier token, so row_spacing (a dict-valued param) can never
    # be resolved to a concrete value.
    with pytest.raises(ValueError):
        resolve_descriptor(tree, parse_descriptor("DIP-16"))


def test_resolve_garbage_modifier_token_raises(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(FORMULA_YAML)
    tree = load_family_tree(str(path))

    import pytest
    # "xyz" is neither a known width code (per `variants`) nor parseable
    # as a float pitch override.
    with pytest.raises(ValueError):
        resolve_descriptor(tree, parse_descriptor("DIP-16 xyz"))


UNKNOWN_GENERATOR_YAML = """
WIDGET:
  generator: totally_bogus_generator
  params:
    pitch: 2.54
"""


def test_load_family_tree_rejects_unknown_generator(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(UNKNOWN_GENERATOR_YAML)

    import pytest
    with pytest.raises(ValueError) as excinfo:
        load_family_tree(str(path))

    message = str(excinfo.value)
    assert "WIDGET" in message
    assert "totally_bogus_generator" in message
