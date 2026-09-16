from kicad_fpdb.pipeline import generate_footprint


def test_dip_value_text_includes_row_spacing_suffix():
    text = generate_footprint("DIP-16", "data/kicad-fpdb.yaml", name="DIP-16")
    assert '(footprint "DIP-16_W7.62mm"' in text
    assert '(property "Value" "DIP-16_W7.62mm"' in text


def test_dip_wide_value_text_uses_its_own_row_spacing():
    text = generate_footprint("DIP-24 w", "data/kicad-fpdb.yaml", name="DIP-24 w")
    assert '(property "Value" "DIP-24 w_W15.24mm"' in text


def test_soic_value_text_includes_body_and_pitch_suffix():
    text = generate_footprint("SOIC-8", "data/kicad-fpdb.yaml", name="SOIC-8")
    assert '(property "Value" "SOIC-8_3.9x4.9mm_P1.27mm"' in text


def test_qfp_value_text_includes_body_and_pitch_suffix():
    text = generate_footprint("LQFP-32", "data/kicad-fpdb.yaml", name="LQFP-32")
    assert '(property "Value" "LQFP-32_7x7mm_P0.8mm"' in text


def test_chip_resistor_value_text_includes_metric_suffix():
    text = generate_footprint("R-0603", "data/kicad-fpdb.yaml", name="R-0603")
    assert '(property "Value" "R-0603_1608Metric"' in text


def test_chip_capacitor_value_text_includes_metric_suffix():
    text = generate_footprint("C-0805", "data/kicad-fpdb.yaml", name="C-0805")
    assert '(property "Value" "C-0805_2012Metric"' in text


def test_axial_resistor_value_text_includes_lead_and_pitch_suffix():
    text = generate_footprint("R-AXIAL0204", "data/kicad-fpdb.yaml", name="R-AXIAL0204")
    assert '(property "Value" "R-AXIAL0204_L3.6_D1.6_P7.62mm"' in text


def test_sot_value_text_has_no_suffix():
    text = generate_footprint("SOT-23-5", "data/kicad-fpdb.yaml", name="SOT-23-5")
    assert '(property "Value" "SOT-23-5"' in text
