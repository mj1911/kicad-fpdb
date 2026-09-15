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


def test_reference_is_on_silkscreen_and_value_is_on_fab():
    # Matches real KiCad convention: Reference on F.SilkS, Value on F.Fab.
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]

    assert '(layer "F.SilkS")' in ref_block
    assert '(layer "F.Fab")' in value_block


def test_reference_and_value_are_horizontally_centered_on_pads():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    ref_x = float(AT_3.search(ref_block).group(1))

    # R-0603 pads are symmetric about x=0.
    assert abs(ref_x - 0.0) < 1e-6


def test_reference_and_value_sit_outside_courtyard_not_just_pads():
    # R-0603's courtyard (0.25mm margin) extends further than a plain
    # pad-bbox margin would -- text must clear the courtyard, not the pads.
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_y = float(AT_3.search(ref_block).group(2))
    value_y = float(AT_3.search(value_block).group(2))

    # R-0603 courtyard is (-1.475, -0.725) to (1.475, 0.725).
    assert ref_y < -0.725
    assert value_y > 0.725


def test_reference_and_value_are_snapped_to_005in_grid():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_x, ref_y = (float(v) for v in AT_3.search(ref_block).groups())
    value_x, value_y = (float(v) for v in AT_3.search(value_block).groups())

    grid = 1.27  # 0.05in
    for coord in (ref_x, ref_y, value_x, value_y):
        assert abs(round(coord / grid) * grid - coord) < 1e-6


def test_reference_and_value_use_real_dip16_positions():
    # DIP-16's courtyard (-1.05, -1.52) to (8.67, 19.3) is the outermost
    # outline -- 0.7mm clearance from it, snapped to the nearest 1.27mm,
    # gives exactly these positions.
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_x, ref_y = (float(v) for v in AT_3.search(ref_block).groups())
    value_x, value_y = (float(v) for v in AT_3.search(value_block).groups())

    assert (ref_x, ref_y) == (3.81, -2.54)
    assert (value_x, value_y) == (3.81, 20.32)
