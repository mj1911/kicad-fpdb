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
