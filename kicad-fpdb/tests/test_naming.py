from kicad_fpdb.geometry import FootprintGeometry, Poly, Rect
from kicad_fpdb.naming import descriptive_suffix, fab_outline_bounding_box


def _rect_geometry(start, end, layer="F.Fab"):
    return FootprintGeometry(name="TEST", rects=[Rect(start=start, end=end, layer=layer)])


def _poly_geometry(points, layer="F.Fab"):
    return FootprintGeometry(name="TEST", polys=[Poly(points=points, layer=layer)])


def test_fab_outline_bounding_box_from_rect():
    geom = _rect_geometry((-0.8, -0.4125), (0.8, 0.4125))
    assert fab_outline_bounding_box(geom) == (-0.8, -0.4125, 0.8, 0.4125)


def test_fab_outline_bounding_box_from_poly():
    geom = _poly_geometry([(-1.95, -1.475), (1.95, -2.45), (1.95, 2.45), (-1.95, 2.45)])
    assert fab_outline_bounding_box(geom) == (-1.95, -2.45, 1.95, 2.45)


def test_fab_outline_bounding_box_ignores_other_layers():
    geom = _rect_geometry((-5, -5), (5, 5), layer="F.CrtYd")
    assert fab_outline_bounding_box(geom) is None


def test_dip_suffix_uses_row_spacing():
    geom = FootprintGeometry(name="TEST")
    suffix = descriptive_suffix("DIP", "16", {"row_spacing": 7.62}, geom)
    assert suffix == "_W7.62mm"


def test_dip_suffix_empty_without_row_spacing():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("DIP", "16", {}, geom) == ""


def test_soic_suffix_uses_fab_bbox_and_pitch():
    geom = _poly_geometry([(-1.95, -1.475), (1.95, -2.45), (1.95, 2.45), (-1.95, 2.45)])
    suffix = descriptive_suffix("SOIC", "8", {"pitch": 1.27}, geom)
    assert suffix == "_3.9x4.9mm_P1.27mm"


def test_qfp_suffix_uses_fab_bbox_and_pitch():
    geom = _poly_geometry([(-3.5, -2.5), (3.5, -3.5), (3.5, 3.5), (-3.5, 3.5)])
    suffix = descriptive_suffix("LQFP", "32", {"pitch": 0.8}, geom)
    assert suffix == "_7x7mm_P0.8mm"


def test_soic_suffix_empty_without_fab_outline():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("SOIC", "8", {"pitch": 1.27}, geom) == ""


def test_qfn_suffix_uses_fab_bbox_pitch_and_ep_size():
    geom = _poly_geometry([(-0.75, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (-1.5, -0.75)])
    suffix = descriptive_suffix("QFN", "16", {"pitch": 0.5, "ep_size": [1.45, 1.45]}, geom)
    assert suffix == "-1EP_3x3mm_P0.5mm_EP1.45x1.45mm"


def test_qfn_suffix_empty_without_ep_size():
    geom = _poly_geometry([(-0.75, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5), (-1.5, -0.75)])
    assert descriptive_suffix("QFN", "16", {"pitch": 0.5}, geom) == "_3x3mm_P0.5mm"


def test_chip_resistor_suffix_uses_metric_lookup():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("R", "0603", {"pad_pitch": 1.65}, geom) == "_1608Metric"


def test_chip_capacitor_suffix_uses_metric_lookup():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("C", "0805", {"pad_pitch": 1.825}, geom) == "_2012Metric"


def test_chip_suffix_empty_for_unknown_variant():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("R", "9999", {"pad_pitch": 1.0}, geom) == ""


def test_axial_suffix_uses_fab_bbox_and_pad_pitch():
    geom = _rect_geometry((2.01, -0.8), (5.61, 0.8))
    suffix = descriptive_suffix("R", "AXIAL0204", {"pad_pitch": 7.62}, geom)
    assert suffix == "_L3.6_D1.6_P7.62mm"


def test_axial_suffix_takes_precedence_over_chip_lookup():
    # "AXIAL0204" must not be treated as a chip metric-code variant.
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("R", "AXIAL0204", {}, geom) == ""


def test_sot_family_gets_no_suffix():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("SOT", "23-5", {"row_spacing": 2.275}, geom) == ""


def test_unknown_family_gets_no_suffix():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("FOO", "1", {"pitch": 1.0}, geom) == ""


def test_cerdip_suffix_uses_row_spacing_and_side_brazed():
    # Real KiCad's own CERDIP names always carry "_SideBrazed" right
    # after the dimension part, unlike plain DIP.
    geom = FootprintGeometry(name="TEST")
    suffix = descriptive_suffix("CERDIP", "14", {"row_spacing": 7.62}, geom)
    assert suffix == "_W7.62mm_SideBrazed"


def test_dip_suffix_with_socket_modifier_appends_after_dimension():
    # Real KiCad names the _Socket variant "DIP-14_W7.62mm_Socket" --
    # the modifier suffix comes after the dimension, not before it.
    geom = FootprintGeometry(name="TEST")
    suffix = descriptive_suffix("DIP", "14", {"row_spacing": 7.62}, geom, applied_modifiers=["socket"])
    assert suffix == "_W7.62mm_Socket"


def test_cerdip_suffix_with_socket_modifier_appends_last():
    geom = FootprintGeometry(name="TEST")
    suffix = descriptive_suffix("CERDIP", "16", {"row_spacing": 7.62}, geom, applied_modifiers=["socket"])
    assert suffix == "_W7.62mm_SideBrazed_Socket"


def test_dip_suffix_with_longpads_modifier_uses_internal_capital():
    # Plain str.capitalize() would give "Longpads" -- real KiCad's own
    # name has an internal capital ("LongPads").
    geom = FootprintGeometry(name="TEST")
    suffix = descriptive_suffix("DIP", "14", {"row_spacing": 7.62}, geom, applied_modifiers=["longpads"])
    assert suffix == "_W7.62mm_LongPads"


def test_unknown_family_with_modifier_still_gets_modifier_suffix():
    geom = FootprintGeometry(name="TEST")
    assert descriptive_suffix("FOO", "1", {}, geom, applied_modifiers=["socket"]) == "_Socket"
