import math

import pytest

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.pipeline import GENERATORS, _add_outline, generate_footprint

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"


def _dip16_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("DIP-16"))
    params = dict(resolved.params)
    params.pop("body_width", None)
    params.pop("body_margin", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "DIP16_TEST"
    return geometry


def _qfp32_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("QFP-32"))
    params = dict(resolved.params)
    params.pop("body_size", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "QFP32_TEST"
    return geometry


def test_add_outline_produces_courtyard_rect():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    assert len(geometry.rects) == 1
    rect = geometry.rects[0]
    assert rect.layer == "F.CrtYd"
    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); courtyard adds 0.5mm margin.
    assert rect.start == pytest.approx((-1.3, -1.3))
    assert rect.end == pytest.approx((8.92, 19.08))


def test_add_outline_produces_silkscreen_body_rect():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4


def test_add_outline_with_body_params_matches_real_dip16_narrow():
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4
    xs = sorted({round(x, 5) for line in silk_lines for x in (line.start[0], line.end[0])})
    ys = sorted({round(y, 5) for line in silk_lines for y in (line.start[1], line.end[1])})
    # Real DIP-16_W7.62mm.kicad_mod silk rect is exactly (1.16, -1.33) to
    # (6.46, 19.11) — pad centers span x=0..7.62, y=0..17.78.
    assert xs == pytest.approx([1.16, 6.46])
    assert ys == pytest.approx([-1.33, 19.11])


def test_add_outline_without_body_params_keeps_generic_margin_behavior():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    xs = sorted({round(x, 5) for line in silk_lines for x in (line.start[0], line.end[0])})
    ys = sorted({round(y, 5) for line in silk_lines for y in (line.start[1], line.end[1])})
    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); generic silk margin is 0.2mm.
    assert xs == pytest.approx([-1.0, 8.62])
    assert ys == pytest.approx([-1.0, 18.78])


def test_add_outline_produces_pin1_marker_triangle():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); silkscreen adds 0.2mm margin,
    # giving a body rect of (-1.0, -1.0) to (8.62, 18.78). Pad "1" sits at
    # (0, 0), nearest to the (-1.0, -1.0) corner. The tip sits at that
    # corner (closest point to pad 1); the base is offset outward, away
    # from pad 1, along the diagonal.
    tip, base1, base2 = marker.points
    assert tip == pytest.approx((-1.0, -1.0))
    assert base1 == pytest.approx((-1.6363961, -1.2121320))
    assert base2 == pytest.approx((-1.2121320, -1.6363961))

    pad1_at = (0.0, 0.0)
    dist_tip = math.hypot(tip[0] - pad1_at[0], tip[1] - pad1_at[1])
    dist_base1 = math.hypot(base1[0] - pad1_at[0], base1[1] - pad1_at[1])
    dist_base2 = math.hypot(base2[0] - pad1_at[0], base2[1] - pad1_at[1])
    assert dist_tip < dist_base1
    assert dist_tip < dist_base2


def test_add_outline_pin1_marker_false_suppresses_marker():
    geometry = _dip16_geometry()
    _add_outline(geometry, pin1_marker=False)

    assert len(geometry.polys) == 0


def test_add_outline_with_body_size_draws_corner_marks():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    # 4 corners x 2 legs each = 8 short lines, no full-perimeter rectangle.
    assert len(silk_lines) == 8

    # Real LQFP-32_7x7mm_P0.8mm.kicad_mod corner marks are at (±3.61, ±3.61)
    # with 0.3mm legs — this project uses a fixed 0.3mm leg for all QFP.
    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in silk_lines for pt in (line.start, line.end)}
    assert (-3.61, -3.61) in endpoints
    assert (-3.31, -3.61) in endpoints
    assert (-3.61, -3.31) in endpoints
    assert (3.61, -3.61) in endpoints
    assert (3.31, -3.61) in endpoints
    assert (3.61, -3.31) in endpoints
    assert (3.61, 3.61) in endpoints
    assert (3.31, 3.61) in endpoints
    assert (3.61, 3.31) in endpoints
    assert (-3.61, 3.61) in endpoints
    assert (-3.31, 3.61) in endpoints
    assert (-3.61, 3.31) in endpoints


def test_add_outline_with_body_size_keeps_pin1_marker():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22)

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" (quad_perimeter's left side, first pin) sits at
    # (-4.175, -2.8), nearest to the (-3.61, -3.61) corner.
    tip, base1, base2 = marker.points
    assert tip == pytest.approx((-3.61, -3.61))


def test_generate_footprint_includes_outline_geometry():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(fp_rect" in text
    assert '(layer "F.CrtYd")' in text
    assert "(fp_line" in text
    assert "(fp_poly" in text
    assert "(fill yes)" in text
    assert '(layer "F.SilkS")' in text


def test_generate_footprint_dip16_narrow_silk_matches_real_body():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(start 1.16 -1.33)" in text
    assert "(end 6.46 -1.33)" in text
    assert "(end 6.46 19.11)" in text
    assert "(end 1.16 19.11)" in text


def test_generate_footprint_dip16_regular_silk_matches_real_body():
    text = generate_footprint("DIP-16 r", FAMILY_TREE_PATH, name="DIP16R_TEST")
    assert "(start 1.845 -1.33)" in text
    assert "(end 8.315 -1.33)" in text


def test_generate_footprint_soic8_silk_matches_body_formula():
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert "(start -2.06 -2.545)" in text
    assert "(end 2.06 -2.545)" in text
    assert "(end 2.06 2.545)" in text


def test_generate_footprint_does_not_leak_body_params_to_generator():
    # If pipeline.py forgot to pop body_width/body_margin before calling
    # the generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert text  # got here without raising


def test_generate_footprint_qfp32_silk_matches_real_corner_marks():
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert "(start -3.61 -3.61)" in text
    assert "(end -3.31 -3.61)" in text
    assert "(end -3.61 -3.31)" in text


def test_generate_footprint_qfp48_silk_matches_real_corner_position():
    text = generate_footprint("QFP-48", FAMILY_TREE_PATH, name="QFP48_TEST")
    # Same 7x7mm body as QFP-32 (per the spec, both real footprints share
    # this corner position); leg length is this project's fixed 0.3mm,
    # not real KiCad's 0.45mm for this specific package.
    assert "(start -3.61 -3.61)" in text
    assert "(end -3.31 -3.61)" in text


def test_generate_footprint_does_not_leak_body_size_to_generator():
    # If pipeline.py forgot to pop body_size before calling the generator,
    # this raises TypeError("unexpected keyword argument").
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert text  # got here without raising


def test_generate_footprint_r0603_has_no_pin1_marker():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "fp_poly" not in text


def test_generate_footprint_c0603_has_no_pin1_marker():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "fp_poly" not in text


def test_generate_footprint_dip16_still_has_pin1_marker():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "fp_poly" in text


def test_generate_footprint_does_not_leak_pin1_marker_to_generator():
    # If pipeline.py forgot to pop pin1_marker before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text  # got here without raising
