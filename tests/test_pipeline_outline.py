import math

import pytest

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.pipeline import GENERATORS, _add_outline, generate_footprint

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"


def _dip16_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("DIP-16"))
    params = dict(resolved.params)
    params.pop("body_width", None)
    params.pop("body_margin", None)
    params.pop("courtyard_margin_x", None)
    params.pop("courtyard_margin_y", None)
    params.pop("notch_radius", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "DIP16_TEST"
    return geometry


def _qfp32_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("QFP-32"))
    params = dict(resolved.params)
    params.pop("body_size", None)
    params.pop("courtyard_margin_x", None)
    params.pop("courtyard_margin_y", None)
    params.pop("courtyard_body_size", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "QFP32_TEST"
    return geometry


def _soic8_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("SOIC-8"))
    params = dict(resolved.params)
    params.pop("body_width", None)
    params.pop("body_margin", None)
    params.pop("courtyard_margin_x", None)
    params.pop("courtyard_margin_y", None)
    params.pop("courtyard_body_width", None)
    params.pop("courtyard_body_margin", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "SOIC8_TEST"
    return geometry


def _r0603_geometry():
    geometry = two_pad_chip(pad_pitch=1.65, pad_size=(0.8, 0.95))
    geometry.name = "R0603_TEST"
    return geometry


def _r0201_geometry():
    geometry = two_pad_chip(pad_pitch=0.64, pad_size=(0.46, 0.4))
    geometry.name = "R0201_TEST"
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


def test_add_outline_with_courtyard_margins_uses_asymmetric_values():
    geometry = _dip16_geometry()
    _add_outline(geometry, courtyard_margin_x=0.25, courtyard_margin_y=0.72)

    assert len(geometry.rects) == 1
    rect = geometry.rects[0]
    assert rect.layer == "F.CrtYd"
    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); 0.25mm margin in X,
    # 0.72mm in Y.
    assert rect.start == pytest.approx((-1.05, -1.52))
    assert rect.end == pytest.approx((8.67, 19.3))


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


def test_add_outline_with_notch_radius_splits_top_edge():
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33, notch_radius=1.0)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    # 5 lines now (top edge split into 2) instead of 4, plus 1 arc.
    assert len(silk_lines) == 5
    assert len(geometry.arcs) == 1

    arc = geometry.arcs[0]
    assert arc.layer == "F.SilkS"
    # Real DIP-16_W7.62mm.kicad_mod notch is exactly this arc.
    assert arc.start == pytest.approx((4.81, -1.33))
    assert arc.mid == pytest.approx((3.81, -0.33))
    assert arc.end == pytest.approx((2.81, -1.33))

    top_segment_endpoints = {
        (round(pt[0], 5), round(pt[1], 5))
        for line in silk_lines if line.start[1] == pytest.approx(-1.33) and line.end[1] == pytest.approx(-1.33)
        for pt in (line.start, line.end)
    }
    assert (1.16, -1.33) in top_segment_endpoints
    assert (2.81, -1.33) in top_segment_endpoints
    assert (4.81, -1.33) in top_segment_endpoints
    assert (6.46, -1.33) in top_segment_endpoints


def test_add_outline_without_notch_radius_keeps_plain_top_edge():
    # SOIC shares this same body_width/body_margin branch but never
    # declares notch_radius — must keep today's plain 4-line rectangle.
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4
    assert len(geometry.arcs) == 0


def test_add_outline_without_body_params_keeps_generic_margin_behavior():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    xs = sorted({round(x, 5) for line in silk_lines for x in (line.start[0], line.end[0])})
    ys = sorted({round(y, 5) for line in silk_lines for y in (line.start[1], line.end[1])})
    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); generic silk margin is 0.2mm.
    assert xs == pytest.approx([-1.0, 8.62])
    assert ys == pytest.approx([-1.0, 18.78])


def test_add_outline_produces_pin1_marker_circle():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    assert len(geometry.circles) == 1
    assert len(geometry.polys) == 0
    marker = geometry.circles[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" sits at (0, 0), size (1.6, 1.6). The marker sits directly
    # above it: same X; its *near* edge (center + radius) clears the
    # pad's own top edge (half its Y size) by a fixed 0.3mm clearance —
    # center is offset by half-Y-size + clearance + radius.
    assert marker.center == pytest.approx((0.0, -1.4))
    assert marker.radius == pytest.approx(0.3)


def test_add_outline_pin1_marker_false_suppresses_marker():
    geometry = _dip16_geometry()
    _add_outline(geometry, pin1_marker=False)

    assert len(geometry.circles) == 0


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

    assert len(geometry.circles) == 1
    marker = geometry.circles[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" (quad_perimeter's left side, first pin) sits at
    # (-4.175, -2.8), size (1.5, 0.5) — the marker is independent of
    # the corner-marks outline entirely now, anchored only to pad 1.
    assert marker.center == pytest.approx((-4.175, -3.65))
    assert marker.radius == pytest.approx(0.3)


def test_add_outline_with_courtyard_body_width_draws_stepped_courtyard():
    geometry = _soic8_geometry()
    _add_outline(
        geometry, body_width=4.12, body_margin=0.64,
        courtyard_margin_x=0.25, courtyard_margin_y=0.25,
        courtyard_body_width=3.9, courtyard_body_margin=0.545,
    )

    assert len(geometry.rects) == 0
    crtyd_lines = [line for line in geometry.lines if line.layer == "F.CrtYd"]
    assert len(crtyd_lines) == 12

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in crtyd_lines for pt in (line.start, line.end)}
    # Real SOIC-8 courtyard shape (see design spec): true body 3.9x4.9mm,
    # full pad bbox, both expanded 0.25mm.
    assert (-2.2, -2.7) in endpoints
    assert (2.2, 2.7) in endpoints
    assert (-3.7, -2.455) in endpoints
    assert (3.7, 2.455) in endpoints


def test_add_outline_with_courtyard_body_size_draws_stepped_courtyard():
    geometry = _qfp32_geometry()
    _add_outline(
        geometry, body_size=7.22,
        courtyard_margin_x=0.25, courtyard_margin_y=0.25,
        courtyard_body_size=7.0,
    )

    assert len(geometry.rects) == 0
    crtyd_lines = [line for line in geometry.lines if line.layer == "F.CrtYd"]
    assert len(crtyd_lines) == 20

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in crtyd_lines for pt in (line.start, line.end)}
    # Real LQFP-32 courtyard shape (see design spec): true 7x7mm body
    # square, one pad-group rect per side, all expanded 0.25mm.
    assert (-3.75, -3.75) in endpoints
    assert (3.75, 3.75) in endpoints
    assert (-5.175, -3.3) in endpoints
    assert (5.175, 3.3) in endpoints


def test_add_outline_without_courtyard_body_params_keeps_plain_rect():
    # Regression guard: DIP (and any family that doesn't declare the new
    # courtyard_body_* params) must be completely unaffected.
    geometry = _dip16_geometry()
    _add_outline(geometry, courtyard_margin_x=0.25, courtyard_margin_y=0.72)

    assert len(geometry.rects) == 1
    assert not any(line.layer == "F.CrtYd" for line in geometry.lines)


def test_generate_footprint_includes_outline_geometry():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(fp_rect" in text
    assert '(layer "F.CrtYd")' in text
    assert "(fp_line" in text
    assert "(fp_circle" in text
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
    assert "fp_circle" not in text


def test_generate_footprint_c0603_has_no_pin1_marker():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "fp_circle" not in text


def test_generate_footprint_dip16_still_has_pin1_marker():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "fp_circle" in text


def test_generate_footprint_does_not_leak_pin1_marker_to_generator():
    # If pipeline.py forgot to pop pin1_marker before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text  # got here without raising


def test_add_outline_with_silk_line_params_draws_two_lines():
    geometry = _r0603_geometry()
    _add_outline(geometry, silk_y=0.5225, silk_half_length=0.237258, pin1_marker=False)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 2

    ys = sorted({round(line.start[1], 6) for line in silk_lines})
    assert ys == pytest.approx([-0.5225, 0.5225])
    for line in silk_lines:
        assert line.start[1] == line.end[1]
        xs = sorted([round(line.start[0], 6), round(line.end[0], 6)])
        assert xs == pytest.approx([-0.237258, 0.237258])

    # No pin-1 marker (pin1_marker=False, matching how R/C actually
    # declare it), and only the courtyard rect — no F.SilkS rectangle.
    assert len(geometry.circles) == 0
    assert len(geometry.rects) == 1
    assert geometry.rects[0].layer == "F.CrtYd"


def test_add_outline_with_no_silk_draws_courtyard_but_no_silk_geometry():
    # R-0201 is too small for real KiCad to draw any silk outline at all
    # -- no_silk suppresses the whole F.SilkS branch while leaving the
    # courtyard untouched.
    geometry = _r0201_geometry()
    _add_outline(geometry, no_silk=True, courtyard_margin_x=0.15, courtyard_margin_y=0.15, pin1_marker=False)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 0
    assert len(geometry.arcs) == 0
    assert len(geometry.circles) == 0

    assert len(geometry.rects) == 1
    assert geometry.rects[0].layer == "F.CrtYd"
    assert geometry.rects[0].start == pytest.approx((-0.7, -0.35))
    assert geometry.rects[0].end == pytest.approx((0.7, 0.35))


def test_generate_footprint_r0402_silk_matches_real_lines():
    text = generate_footprint("R-0402", FAMILY_TREE_PATH, name="R0402_TEST")
    assert "(start -0.153641 -0.38)" in text
    assert "(end 0.153641 -0.38)" in text
    assert "(start -0.153641 0.38)" in text
    assert "(end 0.153641 0.38)" in text


def test_generate_footprint_r0603_silk_matches_real_lines():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "(start -0.237258 -0.5225)" in text
    assert "(end 0.237258 -0.5225)" in text


def test_generate_footprint_r0805_silk_matches_real_lines():
    text = generate_footprint("R-0805", FAMILY_TREE_PATH, name="R0805_TEST")
    assert "(start -0.227064 -0.735)" in text
    assert "(end 0.227064 -0.735)" in text


def test_generate_footprint_c0603_silk_matches_real_lines():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "(start -0.14058 -0.51)" in text
    assert "(end 0.14058 -0.51)" in text


def test_generate_footprint_r0402_courtyard_matches_real_margin():
    text = generate_footprint("R-0402", FAMILY_TREE_PATH, name="R0402_TEST")
    assert "(start -0.93 -0.47)" in text
    assert "(end 0.93 0.47)" in text


def test_generate_footprint_r0603_courtyard_matches_real_margin():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "(start -1.475 -0.725)" in text
    assert "(end 1.475 0.725)" in text


def test_generate_footprint_r0805_courtyard_matches_real_margin():
    text = generate_footprint("R-0805", FAMILY_TREE_PATH, name="R0805_TEST")
    assert "(start -1.675 -0.95)" in text
    assert "(end 1.675 0.95)" in text


def test_generate_footprint_c0603_courtyard_matches_real_margin():
    text = generate_footprint("C-0603", FAMILY_TREE_PATH, name="C0603_TEST")
    assert "(start -1.475 -0.725)" in text
    assert "(end 1.475 0.725)" in text


def test_generate_footprint_r0603_has_only_courtyard_rect():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text.count("(fp_rect") == 1


def test_generate_footprint_does_not_leak_silk_line_params_to_generator():
    # If pipeline.py forgot to pop silk_y/silk_half_length before calling
    # the generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text  # got here without raising


def test_generate_footprint_dip16_courtyard_matches_real_kicad():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(start -1.05 -1.52)" in text
    assert "(end 8.67 19.3)" in text


def test_generate_footprint_does_not_leak_courtyard_margins_to_generator():
    # If pipeline.py forgot to pop courtyard_margin_x/y before calling
    # the generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert text  # got here without raising


def test_generate_footprint_soic8_courtyard_matches_stepped_shape():
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert text.count("(fp_rect") == 0
    assert '(layer "F.CrtYd")' in text
    assert "(start -2.2 -2.7)" in text
    assert "(start -3.7 -2.455)" in text
    assert "(end 3.7 2.455)" in text


def test_generate_footprint_soic14_courtyard_matches_stepped_shape():
    text = generate_footprint("SOIC-14", FAMILY_TREE_PATH, name="SOIC14_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -2.2 -4.605)" in text
    assert "(start -3.7 -4.36)" in text
    assert "(end 3.7 4.36)" in text


def test_generate_footprint_qfp32_courtyard_matches_stepped_shape():
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -3.75 -3.75)" in text
    assert "(start -5.175 -3.3)" in text
    assert "(end 5.175 3.3)" in text


def test_generate_footprint_qfp48_courtyard_matches_stepped_shape():
    text = generate_footprint("QFP-48", FAMILY_TREE_PATH, name="QFP48_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -3.75 -3.75)" in text
    assert "(start -5.15 -3.15)" in text
    assert "(end 5.15 3.15)" in text


def test_generate_footprint_does_not_leak_courtyard_body_params_to_generator():
    # If pipeline.py forgot to pop courtyard_body_width/_margin/_size
    # before calling the generator, this raises
    # TypeError("unexpected keyword argument").
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert text
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert text


def test_generate_footprint_dip16_has_top_notch():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(fp_arc" in text
    assert "(start 4.81 -1.33)" in text
    assert "(mid 3.81 -0.33)" in text
    assert "(end 2.81 -1.33)" in text


def test_generate_footprint_soic8_has_no_notch():
    # SOIC shares the body_width/body_margin branch but must not get one.
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert "(fp_arc" not in text


def test_generate_footprint_does_not_leak_notch_radius_to_generator():
    # If pipeline.py forgot to pop notch_radius before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert text  # got here without raising


def test_generate_footprint_dip24_wide_matches_real_body_courtyard_and_notch():
    # DIP's wide width class (row_spacing 15.24) had no verified regression
    # case before this — confirms the shared body_margin/courtyard_margin/
    # notch_radius constants (calibrated on narrow/regular) hold exactly
    # for wide too.
    text = generate_footprint("DIP-24 w", FAMILY_TREE_PATH, name="DIP24W_TEST")
    assert "(start 1.16 -1.33)" in text
    assert "(end 14.08 29.27)" in text
    assert "(start -1.05 -1.52)" in text
    assert "(end 16.29 29.46)" in text
    assert "(start 8.62 -1.33)" in text
    assert "(mid 7.62 -0.33)" in text
    assert "(end 6.62 -1.33)" in text


def test_generate_footprint_soic16_courtyard_and_silk_match_formula():
    # Third SOIC pin count validated (after SOIC-8/14) -- confirms the
    # shared body_margin/courtyard_body_margin formula keeps working as
    # pin count (and therefore body length) grows, with the larger but
    # still small approximation already accepted for this family.
    text = generate_footprint("SOIC-16", FAMILY_TREE_PATH, name="SOIC16_TEST")
    assert "(start -2.06 -5.085)" in text
    assert "(end 2.06 5.085)" in text
    assert "(start -2.2 -5.24)" in text
    assert "(start -3.7 -4.995)" in text
    assert "(end 3.7 4.995)" in text


def test_generate_footprint_r0201_has_no_silk_and_real_courtyard():
    text = generate_footprint("R-0201", FAMILY_TREE_PATH, name="R0201_TEST")
    # No silk outline geometry at all -- only the Reference text property
    # (itself on F.SilkS) remains, matching real KiCad's R-0201.
    assert "(fp_arc" not in text
    assert "(fp_line" not in text
    assert "(fp_circle" not in text
    assert "(start -0.7 -0.35)" in text
    assert "(end 0.7 0.35)" in text


def test_generate_footprint_r1206_silk_and_courtyard_match_real_values():
    text = generate_footprint("R-1206", FAMILY_TREE_PATH, name="R1206_TEST")
    assert "(start -0.727064 -0.91)" in text
    assert "(end 0.727064 -0.91)" in text
    assert "(start -2.275 -1.125)" in text
    assert "(end 2.275 1.125)" in text


def test_generate_footprint_c0402_silk_and_courtyard_match_real_values():
    text = generate_footprint("C-0402", FAMILY_TREE_PATH, name="C0402_TEST")
    assert "(start -0.107836 -0.36)" in text
    assert "(end 0.107836 -0.36)" in text
    assert "(start -0.91 -0.46)" in text
    assert "(end 0.91 0.46)" in text


def test_generate_footprint_c0805_silk_and_courtyard_match_real_values():
    text = generate_footprint("C-0805", FAMILY_TREE_PATH, name="C0805_TEST")
    assert "(start -0.261252 -0.735)" in text
    assert "(end 0.261252 -0.735)" in text
    assert "(start -1.7 -0.975)" in text
    assert "(end 1.7 0.975)" in text
