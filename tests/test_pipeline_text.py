import re

from kicad_fpdb.pipeline import generate_footprint

AT_3 = re.compile(r"\(at ([-\d.]+) ([-\d.]+) 0\)")


def _require_match(match: re.Match[str] | None) -> re.Match[str]:
    assert match is not None
    return match


def test_generated_footprint_includes_reference_and_value():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    assert '(property "Reference" "REF**"' in text
    # Value gets a descriptive suffix matching real KiCad's own naming
    # convention -- see tests/test_pipeline_naming.py and kicad_fpdb.naming.
    assert '(property "Value" "R_TEST_1608Metric"' in text


def test_reference_is_above_pads_and_value_is_below():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]

    ref_y = float(_require_match(AT_3.search(ref_block)).group(2))
    value_y = float(_require_match(AT_3.search(value_block)).group(2))

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
    ref_x = float(_require_match(AT_3.search(ref_block)).group(1))

    # R-0603 pads are symmetric about x=0.
    assert abs(ref_x - 0.0) < 1e-6


def test_reference_and_value_sit_outside_courtyard_not_just_pads():
    # R-0603's courtyard (0.25mm margin) extends further than a plain
    # pad-bbox margin would -- text must clear the courtyard, not the pads.
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_y = float(_require_match(AT_3.search(ref_block)).group(2))
    value_y = float(_require_match(AT_3.search(value_block)).group(2))

    # R-0603 courtyard is (-1.475, -0.725) to (1.475, 0.725).
    assert ref_y < -0.725
    assert value_y > 0.725


def test_reference_and_value_are_not_grid_snapped():
    # Real KiCad never grid-aligns Reference/Value text -- the previous
    # 1.27mm (0.05in) grid-snap was a deliberate stylistic choice this
    # project made, not something real footprints do. R-0603's
    # courtyard is (-1.475, -0.725) to (1.475, 0.725); the plain 0.7mm
    # margin lands at -1.425/1.425, neither a multiple of 1.27.
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_x, ref_y = (float(v) for v in _require_match(AT_3.search(ref_block)).groups())
    value_x, value_y = (float(v) for v in _require_match(AT_3.search(value_block)).groups())

    assert (ref_x, ref_y) == (0.0, -1.425)
    assert (value_x, value_y) == (0.0, 1.425)


def test_reference_and_value_use_real_dip16_positions():
    # DIP-16's courtyard (-1.05, -1.52) to (8.67, 19.3) is the outermost
    # outline -- 0.7mm clearance from it, snapped to the nearest 1.27mm,
    # gives exactly these positions.
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")

    ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
    value_block = text[text.index('(property "Value"'):]
    ref_x, ref_y = (float(v) for v in _require_match(AT_3.search(ref_block)).groups())
    value_x, value_y = (float(v) for v in _require_match(AT_3.search(value_block)).groups())

    assert (ref_x, ref_y) == (3.81, -2.54)
    assert (value_x, value_y) == (3.81, 20.32)


def test_generated_footprint_includes_fab_reference_text():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R_TEST")
    assert '(fp_text user "${REFERENCE}"' in text
    assert '(layer "F.Fab")' in text


def test_fab_reference_text_uses_default_font_size_when_not_overridden():
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    assert "(size 1 1)" in fab_ref_block
    assert "(thickness 0.15)" in fab_ref_block


def test_fab_reference_text_uses_smaller_font_on_tiny_chip_passives():
    # The default 1mm font badly overflows a chip passive's tiny
    # courtyard -- real KiCad scales it down per package size.
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R0603_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    assert "(size 0.4 0.4)" in fab_ref_block
    assert "(thickness 0.06)" in fab_ref_block


def test_fab_reference_text_is_rotated_90_for_dip():
    # Real KiCad rotates this 90 degrees for DIP/SOIC's tall/narrow
    # bodies so it reads along the long axis; QFP/chip passives don't.
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    assert "(at 3.81 8.89 90)" in fab_ref_block


def test_fab_reference_text_is_rotated_90_for_soic():
    text = generate_footprint("SOIC-8", "data/kicad-fpdb.yaml", name="SOIC8_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    assert " 90)" in fab_ref_block.splitlines()[1]


def test_fab_reference_text_is_not_rotated_for_qfp():
    text = generate_footprint("LQFP-32", "data/kicad-fpdb.yaml", name="LQFP32_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    assert " 0)" in fab_ref_block.splitlines()[1]


def test_fab_reference_text_is_centered_on_the_footprint():
    # Matches real KiCad exactly: centered at the midpoint of the pad
    # grid, e.g. DIP-16's real fp_text user "${REFERENCE}" sits at
    # (3.81, 8.89) -- half the 7.62mm row spacing, half the 17.78mm pad
    # span.
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    at_x, at_y, _rotation = (
        float(v)
        for v in _require_match(
            re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", fab_ref_block)
        ).groups()
    )
    assert (at_x, at_y) == (3.81, 8.89)


def test_reference_and_value_never_land_closer_than_the_intended_gap():
    # Rounding to the *nearest* grid point can round inward, landing
    # closer to the part than TEXT_MARGIN_MM and visually overlapping
    # the courtyard -- confirmed on R-1206 (courtyard edge 1.125mm,
    # nearest-grid text landed at 1.27mm, only 0.145mm clear). Every
    # chip-passive size must keep at least the intended clearance.
    for descriptor in ("R-0201", "R-0402", "R-0603", "R-0805", "R-1206", "C-0402", "C-0603", "C-0805"):
        text = generate_footprint(descriptor, "data/kicad-fpdb.yaml", name="T")
        courtyard_match = _require_match(re.search(
            r"\(fp_rect\n\s*\(start [\-\d.]+ ([\-\d.]+)\)\n\s*\(end [\-\d.]+ ([\-\d.]+)\)", text,
        ))
        courtyard_min_y, courtyard_max_y = (float(v) for v in courtyard_match.groups())

        ref_block = text[text.index('(property "Reference"'):text.index('(property "Value"')]
        value_block = text[text.index('(property "Value"'):]
        ref_y = float(_require_match(AT_3.search(ref_block)).group(2))
        value_y = float(_require_match(AT_3.search(value_block)).group(2))

        assert courtyard_min_y - ref_y >= 0.7 - 1e-6, descriptor
        assert value_y - courtyard_max_y >= 0.7 - 1e-6, descriptor


def test_generate_footprint_does_not_leak_text_margin_mm_to_generator():
    # If pipeline.py forgot to pop text_margin_mm before calling the
    # generator, this raises TypeError for an unexpected kwarg.
    generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP16_TEST")
