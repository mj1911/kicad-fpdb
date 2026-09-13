import re

from kicad_fpdb.pipeline import generate_footprint

AT_3 = re.compile(r"\(at ([-\d.]+) ([-\d.]+) 0\)")


def test_generated_footprint_includes_reference_and_value():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    assert '(property "Reference" "REF**"' in text
    assert '(property "Value" "R_TEST"' in text


def test_reference_is_above_pads_and_value_is_below():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]

    ref_y = float(AT_3.search(ref_block).group(2))
    value_y = float(AT_3.search(value_block).group(2))

    # Pads for R-0603 sit at y=0 with half-height 0.475mm (size 0.8x0.95).
    assert ref_y < -0.475
    assert value_y > 0.475


def test_reference_and_value_are_horizontally_centered_on_pads():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    ref_x = float(AT_3.search(ref_block).group(1))

    # R-0603 pads are symmetric about x=0.
    assert abs(ref_x - 0.0) < 1e-6
