from kicad_fpdb.pipeline import generate_footprint

MINIMAL_TREE = """
TESTPAD:
  generator: two_pad_chip
  params:
    pin1_marker: false
    pad_pitch: 1.0
    pad_size: [0.5, 0.5]
  children:
    TESTPAD-MARGIN:
      params:
        solder_mask_margin: 0.05
        solder_paste_margin: -0.05
    TESTPAD-NOMARGIN:
      params: {}
"""


def test_generate_footprint_applies_solder_margins_to_every_pad(tmp_path):
    tree_path = tmp_path / "tree.yaml"
    tree_path.write_text(MINIMAL_TREE)
    text = generate_footprint("TESTPAD-MARGIN", str(tree_path), "TESTPAD_MARGIN")
    assert text.count("(solder_mask_margin 0.05)") == 2
    assert text.count("(solder_paste_margin -0.05)") == 2


def test_generate_footprint_omits_solder_margins_when_undeclared(tmp_path):
    tree_path = tmp_path / "tree.yaml"
    tree_path.write_text(MINIMAL_TREE)
    text = generate_footprint("TESTPAD-NOMARGIN", str(tree_path), "TESTPAD_NO_MARGIN")
    assert "solder_mask_margin" not in text
    assert "solder_paste_margin" not in text
