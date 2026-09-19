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


WIDTH_OVERRIDE_YAML = """
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: narrow
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    body_width: {narrow: 5.3, regular: 6.47, wide: 12.92}
    pad_size: [1.6, 1.6]
  children:
    DIP-22:
      params: {pin_count: 22, body_width: {regular: 7.84}}
"""


def test_full_name_child_dict_param_overrides_only_its_own_width_key(tmp_path):
    # A formula-driven family's full-name child (e.g. real KiCad's
    # DIP-22/DIP-24, whose "regular"-width body is genuinely larger than
    # every other regular-width pin count) must override just its own
    # width-class key in a dict-valued param, not replace the whole dict
    # -- _merge_params deep-merges dicts, so "narrow"/"wide" must survive
    # untouched for the same descriptor.
    path = tmp_path / "families.yaml"
    path.write_text(WIDTH_OVERRIDE_YAML)
    tree = load_family_tree(str(path))

    regular = resolve_descriptor(tree, parse_descriptor("DIP-22 r"))
    assert regular.params["body_width"] == 7.84

    narrow = resolve_descriptor(tree, parse_descriptor("DIP-22 n"))
    assert narrow.params["body_width"] == 5.3


MODIFIER_PARTIAL_OVERRIDE_YAML = """
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  variants: {n: narrow, r: regular, w: wide}
  default_width: narrow
  params:
    pitch: 2.54
    row_spacing: {narrow: 7.62, regular: 10.16, wide: 15.24}
    body_width: {narrow: 5.3, regular: 6.47, wide: 12.92}
    pad_size: [1.6, 1.6]
  modifiers:
    longpads:
      pad_size: [2.4, 1.6]
      body_width: {narrow: 4.5, wide: 12.12}
"""


def test_modifier_dict_override_merges_not_replaces(tmp_path):
    # A modifier's dict-valued override (e.g. "longpads" shrinking
    # body_width for narrow/wide only) must deep-merge into the
    # existing dict, not replace it wholesale -- otherwise "regular"
    # would vanish from body_width entirely once the modifier applied,
    # raising a KeyError for any "... r longpads" descriptor.
    path = tmp_path / "families.yaml"
    path.write_text(MODIFIER_PARTIAL_OVERRIDE_YAML)
    tree = load_family_tree(str(path))

    narrow = resolve_descriptor(tree, parse_descriptor("DIP-14 longpads"))
    assert narrow.params["body_width"] == 4.5
    assert narrow.params["pad_size"] == [2.4, 1.6]

    regular = resolve_descriptor(tree, parse_descriptor("DIP-14 r longpads"))
    assert regular.params["body_width"] == 6.47


MODIFIER_COMBO_YAML = """
DIP:
  generator: dual_row_grid
  variant_param: pin_count
  params:
    pitch: 2.54
    row_spacing: 7.62
    pad_size: [1.6, 1.6]
  modifiers:
    socket:
      socket_margin_x: 1.33
      _with:
        longpads: {socket_margin_x: 1.44}
    longpads:
      pad_size: [2.4, 1.6]
"""


def test_modifier_combo_override_applies_regardless_of_token_order(tmp_path):
    # A "_with" combo override is checked against the full set of active
    # modifier tokens, not applied sequentially -- so "socket longpads"
    # and "longpads socket" must resolve identically.
    path = tmp_path / "families.yaml"
    path.write_text(MODIFIER_COMBO_YAML)
    tree = load_family_tree(str(path))

    for descriptor in ("DIP-14 socket longpads", "DIP-14 longpads socket"):
        resolved = resolve_descriptor(tree, parse_descriptor(descriptor))
        assert resolved.params["socket_margin_x"] == 1.44, descriptor
        assert resolved.params["pad_size"] == [2.4, 1.6], descriptor


def test_modifier_combo_override_not_applied_without_the_other_token(tmp_path):
    path = tmp_path / "families.yaml"
    path.write_text(MODIFIER_COMBO_YAML)
    tree = load_family_tree(str(path))

    resolved = resolve_descriptor(tree, parse_descriptor("DIP-14 socket"))
    assert resolved.params["socket_margin_x"] == 1.33


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
