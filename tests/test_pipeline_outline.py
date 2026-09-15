import math

import pytest

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.asymmetric_dual_row import asymmetric_dual_row
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
    params.pop("pin1_marker", None)
    params.pop("fab_body_width", None)
    params.pop("fab_body_margin", None)
    params.pop("fab_chamfer", None)
    params.pop("fab_reference_rotation", None)
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
    params.pop("fab_outline", None)
    params.pop("fab_chamfer", None)
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
    params.pop("silk_two_lines", None)
    params.pop("fab_outline", None)
    params.pop("fab_chamfer", None)
    params.pop("fab_reference_rotation", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "SOIC8_TEST"
    return geometry


def _r0603_geometry():
    geometry = two_pad_chip(pad_pitch=1.65, pad_size=(0.8, 0.95))
    geometry.name = "R0603_TEST"
    return geometry


def _r_axial0204_geometry():
    geometry = two_pad_chip(
        pad_pitch=7.62, pad_size=(1.4, 1.4), pad_shape="circle",
        pad_type="thru_hole", drill=0.7, centered=False,
    )
    geometry.name = "R_AXIAL0204_TEST"
    return geometry


def _sot23_geometry():
    geometry = asymmetric_dual_row(
        left_offsets=[-0.95, 0.95], right_offsets=[0], row_spacing=1.875,
        pad_size=(1.475, 0.6), pad_shape="roundrect", pad_type="smd",
    )
    geometry.name = "SOT23_TEST"
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
    # Regression guard for the plain rectangle fallback (neither
    # notch_radius nor silk_two_lines declared) -- must keep today's
    # 4-line rectangle.
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4
    assert len(geometry.arcs) == 0


def test_add_outline_with_silk_two_lines_draws_only_top_and_bottom():
    # SOIC's real silk is just the top/bottom body edges, not a closed
    # rectangle -- no vertical sides.
    geometry = _soic8_geometry()
    _add_outline(geometry, body_width=4.12, body_margin=0.64, silk_two_lines=True)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 2
    assert len(geometry.arcs) == 0

    ys = sorted({round(line.start[1], 5) for line in silk_lines} | {round(line.end[1], 5) for line in silk_lines})
    assert ys == pytest.approx([-2.545, 2.545])
    for line in silk_lines:
        assert line.start[1] == line.end[1]
        xs = sorted([round(line.start[0], 5), round(line.end[0], 5)])
        assert xs == pytest.approx([-2.06, 2.06])


def test_add_outline_without_silk_two_lines_keeps_plain_rectangle():
    # Regression guard: DIP (and anything else that doesn't opt in) is
    # unaffected -- still the full 4-line rectangle (or notch variant).
    geometry = _dip16_geometry()
    _add_outline(geometry, body_width=5.3, body_margin=1.33)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 4


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
    assert '(layer "F.SilkS")' in text

    # Pin-1 marker circle geometry is exercised via a family that still
    # has one (DIP itself doesn't -- see test_generate_footprint_dip16_has_no_pin1_marker).
    soic_text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    assert "(fp_circle" in soic_text
    assert "(fill yes)" in soic_text


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


def test_generate_footprint_soic8_silk_has_no_vertical_sides():
    # Real SOIC silk is just the top/bottom body edges -- no closed
    # rectangle. Only 2 F.SilkS fp_line entries (silk_two_lines: true).
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    silk_line_blocks = [
        block for block in text.split("(fp_line")[1:] if '(layer "F.SilkS")' in block
    ]
    assert len(silk_line_blocks) == 2


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


def test_generate_footprint_qfp32_pad_offset_derived_from_courtyard_body_size():
    # QFP-32's yaml no longer declares pad_offset directly -- this proves
    # generate_footprint() forwards courtyard_body_size through to
    # quad_perimeter so it can derive pad_offset itself.
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    assert "(at -4.175 -2.8)" in text


def test_generate_footprint_qfp48_pad_offset_uses_override_extension():
    # QFP-48 overrides pad_lead_extension to 0.6625 at the yaml level.
    text = generate_footprint("QFP-48", FAMILY_TREE_PATH, name="QFP48_TEST")
    assert "(at -4.1625" in text


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


def test_generate_footprint_dip16_has_no_pin1_marker():
    # DIP already has a square pin-1 pad and a silk notch -- a separate
    # circle marker is redundant.
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "fp_circle" not in text


def test_generate_footprint_soic8_still_has_pin1_marker():
    # Regression guard: only DIP opted out -- other families with no
    # square pin-1 pad shape of their own still get the circle marker.
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
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


def test_add_outline_with_tuple_courtyard_body_size_unions_per_pad_rects():
    # SOT-style stepped courtyard: union of the true (non-square) body
    # rect and each individual pad's own bbox (not grouped per side --
    # a family with a gap between two same-side pads, like SOT-23-5,
    # needs the gap to stay open).
    geometry = _sot23_geometry()
    _add_outline(geometry, courtyard_body_size=(1.3, 2.9),
                  courtyard_margin_x=0.25, courtyard_margin_y=0.25, pin1_marker=False)

    assert len(geometry.rects) == 0
    crtyd_lines = [line for line in geometry.lines if line.layer == "F.CrtYd"]
    assert len(crtyd_lines) == 16

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in crtyd_lines for pt in (line.start, line.end)}
    # Matches real SOT-23 courtyard corners within the same ~0.005mm
    # rounding already documented elsewhere (our flat 0.25 margin vs
    # real's ~0.255): real (-1.93, -1.5) etc.
    assert (-1.925, -1.5) in endpoints
    assert (-0.9, -1.7) in endpoints
    assert (0.9, -1.7) in endpoints
    assert (1.925, -0.55) in endpoints
    assert (1.925, 0.55) in endpoints


def test_add_outline_with_silk_segments_draws_verbatim_lines():
    geometry = _sot23_geometry()
    segments = [
        ((-0.76, -1.56), (0.76, -1.56)),
        ((-0.76, -1.51), (-0.76, -1.56)),
        ((-0.76, 0.39), (-0.76, -0.39)),
    ]
    _add_outline(geometry, silk_segments=segments, pin1_marker=False)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    assert len(silk_lines) == 3
    assert len(geometry.arcs) == 0
    for (start, end), line in zip(segments, silk_lines):
        assert line.start == pytest.approx(start)
        assert line.end == pytest.approx(end)

    # Courtyard is unaffected -- still the generic flat-margin fallback.
    assert len(geometry.rects) == 1
    assert geometry.rects[0].layer == "F.CrtYd"


def test_add_outline_with_fab_body_width_draws_chamfered_poly():
    # DIP-style: own fab_body_width/_margin pair (distinct from the
    # oversized silk body_width/body_margin), chamfered at pin 1's
    # corner. Matches real DIP-16 exactly.
    geometry = _dip16_geometry()
    _add_outline(geometry, fab_body_width=6.35, fab_body_margin=1.27, fab_chamfer=1.0, pin1_marker=False)

    fab_polys = [poly for poly in geometry.polys if poly.layer == "F.Fab"]
    assert len(fab_polys) == 1
    poly = fab_polys[0]
    assert poly.fill == "no"
    rounded_points = [(round(x, 6), round(y, 6)) for x, y in poly.points]
    assert rounded_points == [
        (1.635, -1.27), (6.985, -1.27), (6.985, 19.05), (0.635, 19.05), (0.635, -0.27),
    ]
    assert not any(rect.layer == "F.Fab" for rect in geometry.rects)  # no plain fab rect when chamfered


def test_add_outline_with_fab_outline_reuses_courtyard_body_width():
    # SOIC-style: no separate fab_body_width declared -- fab_outline
    # reuses the existing courtyard_body_width/_margin (already the
    # true physical body), matching real KiCad exactly.
    geometry = _soic8_geometry()
    _add_outline(geometry, fab_outline=True, fab_chamfer=0.975,
                  courtyard_body_width=3.9, courtyard_body_margin=0.545, pin1_marker=False)

    fab_polys = [poly for poly in geometry.polys if poly.layer == "F.Fab"]
    assert len(fab_polys) == 1
    rounded_points = [(round(x, 6), round(y, 6)) for x, y in fab_polys[0].points]
    assert rounded_points == [
        (-0.975, -2.45), (1.95, -2.45), (1.95, 2.45), (-1.95, 2.45), (-1.95, -1.475),
    ]


def test_add_outline_with_fab_outline_reuses_tuple_courtyard_body_size():
    # SOT-style: fab_outline reuses the existing tuple courtyard_body_size.
    geometry = _sot23_geometry()
    _add_outline(geometry, fab_outline=True, fab_chamfer=0.325,
                  courtyard_body_size=(1.3, 2.9), pin1_marker=False)

    fab_polys = [poly for poly in geometry.polys if poly.layer == "F.Fab"]
    assert len(fab_polys) == 1
    rounded_points = [(round(x, 6), round(y, 6)) for x, y in fab_polys[0].points]
    assert rounded_points == [
        (-0.325, -1.45), (0.65, -1.45), (0.65, 1.45), (-0.65, 1.45), (-0.65, -1.125),
    ]


def test_add_outline_with_fab_body_size_draws_plain_rect_no_chamfer():
    # R/C-style: chip passives get their own new fab_body_size (no
    # existing courtyard "true body" to reuse, since their courtyard is
    # just a margin-expanded pad bbox) and no chamfer (no polarity).
    geometry = _r0603_geometry()
    _add_outline(geometry, fab_body_size=(1.6, 0.825), pin1_marker=False)

    assert len([p for p in geometry.polys if p.layer == "F.Fab"]) == 0
    fab_rects = [r for r in geometry.rects if r.layer == "F.Fab"]
    assert len(fab_rects) == 1
    assert fab_rects[0].start == pytest.approx((-0.8, -0.4125))
    assert fab_rects[0].end == pytest.approx((0.8, 0.4125))
    assert fab_rects[0].fill == "no"


def test_add_outline_without_fab_params_draws_no_fab_geometry():
    # Regression guard: a family that declares none of the new fab_*
    # params gets no F.Fab body geometry at all (only the pre-existing
    # Value property, added later by _add_reference_and_value_text, not
    # _add_outline).
    geometry = _dip16_geometry()
    _add_outline(geometry)

    assert not any(poly.layer == "F.Fab" for poly in geometry.polys)
    assert not any(rect.layer == "F.Fab" for rect in geometry.rects)


def test_add_outline_with_silk_leads_draws_leads_and_body_rect():
    # Real THT axial resistors draw two short lead lines from each pad's
    # edge (plus a fixed clearance) to the oversized silk body's own
    # edge, in addition to the body rectangle -- matches real
    # R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_Horizontal exactly.
    geometry = _r_axial0204_geometry()
    _add_outline(geometry, body_width=3.84, body_margin=0.92, silk_leads=True, pin1_marker=False)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    lead_lines = [line for line in silk_lines if line.start[1] == line.end[1] == 0]
    assert len(lead_lines) == 2
    rounded = {(round(l.start[0], 5), round(l.end[0], 5)) for l in lead_lines}
    assert (0.94, 1.89) in rounded
    assert (6.68, 5.73) in rounded
    # Body rectangle is still drawn (4 more lines, since no notch_radius).
    assert len(silk_lines) == 6


def test_add_outline_with_fab_leads_draws_leads_from_pad_center():
    # F.Fab leads start exactly at the pad center (no clearance), unlike
    # the silk leads above.
    geometry = _r_axial0204_geometry()
    _add_outline(geometry, fab_body_size=(3.6, 1.6), fab_leads=True, pin1_marker=False)

    fab_lines = [line for line in geometry.lines if line.layer == "F.Fab"]
    assert len(fab_lines) == 2
    rounded = {(round(l.start[0], 5), round(l.end[0], 5)) for l in fab_lines}
    assert (0.0, 2.01) in rounded
    assert (7.62, 5.61) in rounded
    # Body rectangle is still drawn alongside the leads (no chamfer here).
    fab_rects = [r for r in geometry.rects if r.layer == "F.Fab"]
    assert len(fab_rects) == 1


def test_add_outline_with_courtyard_includes_body_combines_bboxes():
    # New flat-rectangle courtyard mode: combined bbox of (pad bbox, true
    # F.Fab body), then one flat margin -- not the stepped union model
    # SOIC/QFP/SOT use. Matches real R_Axial_DIN0204 exactly.
    geometry = _r_axial0204_geometry()
    _add_outline(geometry, fab_body_size=(3.6, 1.6), courtyard_includes_body=True,
                  courtyard_margin_x=0.25, courtyard_margin_y=0.25, pin1_marker=False)

    crtyd_rects = [r for r in geometry.rects if r.layer == "F.CrtYd"]
    assert len(crtyd_rects) == 1
    assert crtyd_rects[0].start == pytest.approx((-0.95, -1.05))
    assert crtyd_rects[0].end == pytest.approx((8.57, 1.05))


def test_add_outline_without_courtyard_includes_body_ignores_fab_body():
    # Regression guard: fab_body_size alone (courtyard_includes_body not
    # set) must not change the plain flat-margin-on-pad-bbox courtyard
    # every chip passive already relies on.
    geometry = _r0603_geometry()
    _add_outline(geometry, fab_body_size=(1.6, 0.825), courtyard_margin_x=0.25, courtyard_margin_y=0.25,
                  pin1_marker=False)

    crtyd_rects = [r for r in geometry.rects if r.layer == "F.CrtYd"]
    assert len(crtyd_rects) == 1
    assert crtyd_rects[0].start == pytest.approx((-1.475, -0.725))
    assert crtyd_rects[0].end == pytest.approx((1.475, 0.725))


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


def test_generate_footprint_r0603_has_courtyard_and_fab_rects_only():
    # Two plain fp_rect entries now: the F.CrtYd courtyard (unchanged)
    # and the new F.Fab body outline (chip passives get no chamfer).
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text.count("(fp_rect") == 2
    assert text.count('(layer "F.CrtYd")') == 1
    assert '(layer "F.Fab")' in text


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


def test_generate_footprint_sot23_matches_real_silk_and_courtyard():
    text = generate_footprint("SOT-23", FAMILY_TREE_PATH, name="SOT23_TEST")
    assert text.count("(fp_rect") == 0
    # Silk: verbatim segments copied from the real reference footprint.
    assert "(start -0.76 -1.56)" in text
    assert "(end 0.76 -1.56)" in text
    # Courtyard: union-of-rects model, matches real within the same
    # ~0.005mm rounding already documented elsewhere.
    assert "(start -1.925 -1.5)" in text
    assert "(start -0.9 -1.7)" in text


def test_generate_footprint_sot23_5_matches_real_silk_and_courtyard():
    text = generate_footprint("SOT-23-5", FAMILY_TREE_PATH, name="SOT235_TEST")
    assert "(start -0.91 -1.56)" in text
    assert "(start -2.05 -1.5)" in text
    assert "(start -1.05 -1.7)" in text


def test_generate_footprint_sot23_6_matches_real_silk_and_courtyard():
    text = generate_footprint("SOT-23-6", FAMILY_TREE_PATH, name="SOT236_TEST")
    assert "(start -0.91 -1.56)" in text
    assert "(start -2.05 -1.5)" in text
    # SOT-23-6's 3+3 columns are fully populated (no gap) -- no middle
    # silk segment, unlike SOT-23-5's 3+2.
    assert "(start 0.91 -0.39)" not in text


def test_generate_footprint_sot23_8_matches_real_silk_and_courtyard():
    text = generate_footprint("SOT-23-8", FAMILY_TREE_PATH, name="SOT238_TEST")
    assert "(start -0.91 -1.56)" in text
    assert "(start -2.05 -1.475)" in text


def test_generate_footprint_sot23_has_no_pin1_marker():
    # SOT-23's asymmetric 2+1 pin layout is only physically placeable one
    # way -- a separate pin-1 indicator is redundant.
    text = generate_footprint("SOT-23", FAMILY_TREE_PATH, name="SOT23_TEST")
    assert "fp_circle" not in text


def test_generate_footprint_sot23_5_has_no_pin1_marker():
    # Same reasoning: SOT-23-5's asymmetric 3+2 layout is unambiguous.
    text = generate_footprint("SOT-23-5", FAMILY_TREE_PATH, name="SOT235_TEST")
    assert "fp_circle" not in text


def test_generate_footprint_sot23_6_still_has_pin1_marker():
    # SOT-23-6 (3+3) and SOT-23-8 (4+4) are symmetric -- rotating the
    # part 180 degrees still fits, so they keep the marker.
    text = generate_footprint("SOT-23-6", FAMILY_TREE_PATH, name="SOT236_TEST")
    assert "fp_circle" in text


def test_generate_footprint_sot23_8_still_has_pin1_marker():
    text = generate_footprint("SOT-23-8", FAMILY_TREE_PATH, name="SOT238_TEST")
    assert "fp_circle" in text


def test_generate_footprint_sot23_fab_reference_is_rotated_and_small():
    text = generate_footprint("SOT-23", FAMILY_TREE_PATH, name="SOT23_TEST")
    fab_ref_block = text[text.index('(fp_text user "${REFERENCE}"'):]
    assert "(at 0 0 90)" in fab_ref_block
    assert "(size 0.72 0.72)" in fab_ref_block
    assert "(thickness 0.11)" in fab_ref_block


def test_generate_footprint_does_not_leak_silk_segments_to_generator():
    # If pipeline.py forgot to pop silk_segments before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("SOT-23", FAMILY_TREE_PATH, name="SOT23_TEST")
    assert text  # got here without raising


def test_generate_footprint_dip16_fab_body_matches_real_chamfer():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    fab_poly = text[text.index("(fp_poly"):text.index('(layer "F.Fab")', text.index("(fp_poly"))]
    assert "(xy 1.635 -1.27)" in fab_poly
    assert "(xy 6.985 -1.27)" in fab_poly
    assert "(xy 6.985 19.05)" in fab_poly
    assert "(xy 0.635 19.05)" in fab_poly
    assert "(xy 0.635 -0.27)" in fab_poly


def test_generate_footprint_soic8_fab_body_reuses_courtyard_true_body():
    text = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="SOIC8_TEST")
    fab_poly = text[text.index("(fp_poly"):text.index('(layer "F.Fab")', text.index("(fp_poly"))]
    assert "(xy -0.975 -2.45)" in fab_poly
    assert "(xy 1.95 -2.45)" in fab_poly
    assert "(xy -1.95 -1.475)" in fab_poly


def test_generate_footprint_qfp32_fab_body_reuses_courtyard_true_body():
    text = generate_footprint("QFP-32", FAMILY_TREE_PATH, name="QFP32_TEST")
    fab_poly = text[text.index("(fp_poly"):text.index('(layer "F.Fab")', text.index("(fp_poly"))]
    assert "(xy -2.5 -3.5)" in fab_poly
    assert "(xy 3.5 3.5)" in fab_poly


def test_generate_footprint_sot23_fab_body_reuses_tuple_courtyard_true_body():
    text = generate_footprint("SOT-23", FAMILY_TREE_PATH, name="SOT23_TEST")
    fab_poly = text[text.index("(fp_poly"):text.index('(layer "F.Fab")', text.index("(fp_poly"))]
    assert "(xy -0.325 -1.45)" in fab_poly
    assert "(xy -0.65 -1.125)" in fab_poly


def test_generate_footprint_r0603_fab_body_is_plain_rect_no_chamfer():
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert "(fp_poly" not in text
    fab_block = text[text.rindex("(fp_rect"):]
    assert "(start -0.8 -0.4125)" in fab_block
    assert "(end 0.8 0.4125)" in fab_block
    assert '(layer "F.Fab")' in fab_block


def test_generate_footprint_does_not_leak_fab_body_params_to_generator():
    # If pipeline.py forgot to pop any fab_body_*/fab_outline/fab_chamfer
    # param before calling the generator, this raises
    # TypeError("unexpected keyword argument").
    for descriptor in ("DIP-16", "SOIC-8", "QFP-32", "R-0603", "SOT-23"):
        text = generate_footprint(descriptor, FAMILY_TREE_PATH, name="X")
        assert text


def test_generate_footprint_raxial0204_matches_real_values():
    text = generate_footprint("R-AXIAL0204", FAMILY_TREE_PATH, name="X")
    assert "(start -0.95 -1.05)" in text
    assert "(end 8.57 1.05)" in text
    assert "(start 2.01 -0.8)" in text
    assert "(end 5.61 0.8)" in text
    assert "(start 1.89 -0.92)" in text
    assert "(start 0.94 0)" in text
    assert "(end 1.89 0)" in text
    assert "(start 0 0)" in text
    assert "(end 2.01 0)" in text


def test_generate_footprint_raxial0207_matches_real_values():
    text = generate_footprint("R-AXIAL0207", FAMILY_TREE_PATH, name="X")
    assert "(start -1.05 -1.5)" in text
    assert "(end 11.21 1.5)" in text
    assert "(start 1.93 -1.25)" in text
    assert "(end 8.23 1.25)" in text
    assert "(start 1.81 -1.37)" in text
    assert "(start 1.04 0)" in text
    assert "(end 1.81 0)" in text


def test_generate_footprint_raxial0309_matches_real_values():
    text = generate_footprint("R-AXIAL0309", FAMILY_TREE_PATH, name="X")
    assert "(start -1.05 -1.85)" in text
    assert "(end 13.75 1.85)" in text
    assert "(start 1.85 -1.6)" in text
    assert "(end 10.85 1.6)" in text


def test_generate_footprint_raxial0414_matches_real_values():
    text = generate_footprint("R-AXIAL0414", FAMILY_TREE_PATH, name="X")
    assert "(start -1.45 -2.5)" in text
    assert "(end 16.69 2.5)" in text
    assert "(start 1.67 -2.25)" in text
    assert "(end 13.57 2.25)" in text


def test_generate_footprint_raxial_pads_are_thru_hole():
    text = generate_footprint("R-AXIAL0207", FAMILY_TREE_PATH, name="X")
    assert '(pad "1" thru_hole circle' in text
    assert '(pad "2" thru_hole circle' in text
    assert "(drill 0.8)" in text
    assert "(at 0 0)" in text
    assert "(at 10.16 0)" in text


def test_generate_footprint_raxial_has_no_pin1_marker():
    # Axial resistors have no polarity, matching the R family's existing
    # pin1_marker: false.
    text = generate_footprint("R-AXIAL0207", FAMILY_TREE_PATH, name="X")
    assert "fp_circle" not in text


def test_generate_footprint_does_not_leak_lead_and_courtyard_body_params_to_generator():
    # If pipeline.py forgot to pop silk_leads/fab_leads/
    # courtyard_includes_body before calling the generator, this raises
    # TypeError("unexpected keyword argument").
    text = generate_footprint("R-AXIAL0204", FAMILY_TREE_PATH, name="X")
    assert text
