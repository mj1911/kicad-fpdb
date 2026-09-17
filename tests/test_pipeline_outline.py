import math
import re

import pytest

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.asymmetric_dual_row import asymmetric_dual_row
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.pipeline import GENERATORS, _add_corner_marks, _add_outline, generate_footprint

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
    resolved = resolve_descriptor(tree, parse_descriptor("LQFP-32"))
    params = dict(resolved.params)
    params.pop("body_size", None)
    params.pop("courtyard_margin_x", None)
    params.pop("courtyard_margin_y", None)
    params.pop("fab_outline", None)
    params.pop("fab_chamfer", None)
    params.pop("pin1_marker_style", None)
    params.pop("pin1_triangle_axis", None)
    params.pop("pin1_triangle_size", None)
    params.pop("pin1_triangle_anchor_mm", None)
    geometry = GENERATORS[resolved.generator](**params)
    geometry.name = "LQFP32_TEST"
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
    params.pop("pin1_marker_style", None)
    params.pop("pin1_triangle_axis", None)
    params.pop("pin1_triangle_size", None)
    params.pop("pin1_triangle_anchor_mm", None)
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

    # Real LQFP-32_7x7mm_P0.8mm.kicad_mod body corners are at (±3.61, ±3.61).
    # Legs now extend inward exactly to the adjacent side's own courtyard
    # jog (this test's fixture pads give a "top"/"left" arm edge at
    # ±3.05, minus the 0.5mm default courtyard margin -- since this test
    # doesn't pass courtyard_margin_x/_y -- landing at ±3.55) instead of
    # the old fixed ±0.3mm offset (±3.31).
    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in silk_lines for pt in (line.start, line.end)}
    assert (-3.61, -3.61) in endpoints
    assert (-3.55, -3.61) in endpoints
    assert (-3.61, -3.55) in endpoints
    assert (3.61, -3.61) in endpoints
    assert (3.55, -3.61) in endpoints
    assert (3.61, -3.55) in endpoints
    assert (3.61, 3.61) in endpoints
    assert (3.55, 3.61) in endpoints
    assert (3.61, 3.55) in endpoints
    assert (-3.61, 3.61) in endpoints
    assert (-3.55, 3.61) in endpoints
    assert (-3.61, 3.55) in endpoints


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


def test_add_outline_with_triangle_style_draws_pin1_triangle():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22, pin1_marker_style="triangle")

    assert len(geometry.circles) == 0
    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"
    assert marker.fill == "yes"

    # Pad "1" sits at (-4.175, -2.8), size (1.5, 0.5) -- a left-side pad
    # (width > height), same orientation convention real QFN's pin 1
    # uses. No courtyard_margin_x/_y passed, so _add_outline falls back
    # to COURTYARD_MARGIN_MM (0.5).
    # Apex: pad's own left edge (-4.175 - 0.75 = -4.925), minus the
    # courtyard margin (0.5), minus the fixed 0.01mm silk offset.
    # Base: apex_x - 0.33 (fixed depth), spread pad-y +/- 0.24 (fixed).
    apex = (-5.435, -2.8)
    base_top = (-5.765, -3.04)
    base_bottom = (-5.765, -2.56)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert points == {apex, base_top, base_bottom}


def test_add_outline_pin1_marker_false_suppresses_triangle_too():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22, pin1_marker=False, pin1_marker_style="triangle")

    assert len(geometry.circles) == 0
    assert len(geometry.polys) == 0


def test_add_outline_with_y_axis_triangle_uses_body_anchor():
    geometry = _qfp32_geometry()
    _add_outline(
        geometry, body_size=7.22, pin1_marker_style="triangle",
        pin1_triangle_axis="y", pin1_triangle_size="large", pin1_triangle_anchor_mm=0.75,
        courtyard_margin_x=0.25, courtyard_margin_y=0.25, courtyard_body_size=7.0,
    )

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    assert marker.layer == "F.SilkS"

    # Extension axis (Y): apex = pad1's own top edge (-2.8 - 0.25 = -3.05)
    # minus courtyard_margin_y (0.25) minus the fixed 0.01mm silk offset
    # = -3.31; base = apex - 0.47 (the "large" depth) = -3.78.
    # Perpendicular axis (X): body-anchored, NOT pad1-relative -- apex.x
    # = -(courtyard_body_size/2 + anchor) = -(3.5 + 0.75) = -4.25,
    # independent of pad1.x entirely. Base spread +/-0.34 (the "large"
    # half-width) around that.
    apex = (-4.25, -3.31)
    base_a = (-4.59, -3.78)
    base_b = (-3.91, -3.78)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert points == {apex, base_a, base_b}


def test_add_outline_with_y_axis_triangle_falls_back_to_pad_relative_without_anchor():
    geometry = _qfp32_geometry()
    _add_outline(
        geometry, body_size=7.22, pin1_marker_style="triangle",
        pin1_triangle_axis="y", pin1_triangle_size="large",
        courtyard_margin_x=0.25, courtyard_margin_y=0.25,
    )

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]
    # No pin1_triangle_anchor_mm -- perpendicular axis (X) falls back to
    # pad1's own x (-4.175) directly, not body-anchored.
    apex = (-4.175, -3.31)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert apex in points


def test_add_outline_triangle_axis_none_still_infers_from_pad_shape():
    # Regression guard: pin1_triangle_axis's default (None) must keep
    # reproducing today's QFN behavior exactly -- shape-inferred axis
    # ("x", since this fixture's pad 1 is wider than tall), "small" size,
    # pad-relative perpendicular position. Byte-identical to the
    # existing test_add_outline_with_triangle_style_draws_pin1_triangle.
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22, pin1_marker_style="triangle")

    marker = geometry.polys[0]
    apex = (-5.435, -2.8)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert apex in points


def test_add_outline_with_y_axis_triangle_handles_tuple_courtyard_body_size():
    from kicad_fpdb.geometry import FootprintGeometry, Pad
    geometry = FootprintGeometry(name="TEST")
    geometry.pads = [
        Pad(number="1", pad_type="smd", shape="roundrect", at=(-1.0, -1.0), size=(1.0, 0.6)),
        Pad(number="2", pad_type="smd", shape="roundrect", at=(1.0, -1.0), size=(1.0, 0.6)),
    ]
    _add_outline(
        geometry, pin1_marker_style="triangle", pin1_triangle_axis="y",
        pin1_triangle_anchor_mm=0.75, courtyard_margin_y=0.25,
        courtyard_body_size=(3.0, 5.0),
    )

    assert len(geometry.polys) == 1
    marker = geometry.polys[0]

    # Extension axis (Y): apex = pad1's own top edge (-1.0 - 0.3 = -1.3)
    # minus courtyard_margin_y (0.25) minus the fixed 0.01mm silk offset
    # = -1.56; base = apex - 0.33 (the default "small" depth) = -1.89.
    # Perpendicular axis (X): body-anchored using the tuple's WIDTH
    # (index 0, 3.0), not the full tuple -- apex.x = -(3.0/2 + 0.75) =
    # -2.25, independent of pad1.x. Base spread +/-0.24 (the default
    # "small" half-width).
    apex = (-2.25, -1.56)
    base_a = (-2.49, -1.89)
    base_b = (-2.01, -1.89)
    points = {(round(x, 5), round(y, 5)) for x, y in marker.points}
    assert points == {apex, base_a, base_b}


def test_add_corner_marks_extends_legs_to_side_group_jog():
    from kicad_fpdb.geometry import FootprintGeometry
    geometry = FootprintGeometry(name="TEST")
    side_groups = {
        "top": (-1.0, -3.0, 1.0, -2.2),
        "bottom": (-1.0, 2.2, 1.0, 3.0),
        "left": (-3.0, -1.0, -2.2, 1.0),
        "right": (2.2, -1.0, 3.0, 1.0),
    }
    _add_corner_marks(geometry, -2.0, -2.0, 2.0, 2.0, side_groups=side_groups, mx=0.25, my=0.25)

    assert len(geometry.lines) == 8
    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in geometry.lines for pt in (line.start, line.end)}
    # Each leg now reaches the adjacent side's own margin-expanded edge
    # (e.g. top-left corner's horizontal leg is bounded by "top"'s own
    # left edge minus mx: -1.0 - 0.25 = -1.25) instead of a fixed 0.3mm
    # offset -- see docs/superpowers/specs/2026-09-17-corner-mark-
    # extends-to-courtyard-jog-design.md.
    assert (-2.0, -2.0) in endpoints
    assert (-1.25, -2.0) in endpoints
    assert (-2.0, -1.25) in endpoints
    assert (2.0, -2.0) in endpoints
    assert (1.25, -2.0) in endpoints
    assert (2.0, -1.25) in endpoints
    assert (2.0, 2.0) in endpoints
    assert (1.25, 2.0) in endpoints
    assert (2.0, 1.25) in endpoints
    assert (-2.0, 2.0) in endpoints
    assert (-1.25, 2.0) in endpoints
    assert (-2.0, 1.25) in endpoints
    for line in geometry.lines:
        assert line.layer == "F.SilkS"


def test_add_corner_marks_falls_back_to_fixed_length_without_side_groups():
    from kicad_fpdb.geometry import FootprintGeometry
    geometry = FootprintGeometry(name="TEST")
    _add_corner_marks(geometry, -2.0, -2.0, 2.0, 2.0)

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in geometry.lines for pt in (line.start, line.end)}
    # No side_groups at all -- every leg keeps the old fixed 0.3mm length.
    assert (-1.7, -2.0) in endpoints
    assert (-2.0, -1.7) in endpoints
    assert (1.7, -2.0) in endpoints
    assert (2.0, -1.7) in endpoints
    assert (1.7, 2.0) in endpoints
    assert (2.0, 1.7) in endpoints
    assert (-1.7, 2.0) in endpoints
    assert (-2.0, 1.7) in endpoints


def test_add_corner_marks_falls_back_per_leg_when_one_side_is_missing():
    from kicad_fpdb.geometry import FootprintGeometry
    geometry = FootprintGeometry(name="TEST")
    # No "top" entry -- both top corners' horizontal legs must fall back
    # to the fixed length, while every other leg (bounded by a side that
    # IS present) still computes from side_groups.
    side_groups = {
        "bottom": (-1.0, 2.2, 1.0, 3.0),
        "left": (-3.0, -1.0, -2.2, 1.0),
        "right": (2.2, -1.0, 3.0, 1.0),
    }
    _add_corner_marks(geometry, -2.0, -2.0, 2.0, 2.0, side_groups=side_groups, mx=0.25, my=0.25)

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in geometry.lines for pt in (line.start, line.end)}
    # Top corners' horizontal legs: fixed-length fallback (no "top").
    assert (-1.7, -2.0) in endpoints
    assert (1.7, -2.0) in endpoints
    # Top corners' vertical legs: computed from "left"/"right" (present).
    assert (-2.0, -1.25) in endpoints
    assert (2.0, -1.25) in endpoints
    # Bottom corners: fully computed (both "bottom" and "left"/"right" present).
    assert (1.25, 2.0) in endpoints
    assert (2.0, 1.25) in endpoints
    assert (-1.25, 2.0) in endpoints
    assert (-2.0, 1.25) in endpoints


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
    # has one (DIP itself doesn't -- see test_generate_footprint_dip16_has_no_pin1_marker;
    # SOIC switched to the triangle marker -- see
    # test_generate_footprint_soic8_has_triangle_pin1_marker -- so this
    # uses SOT-23-6 instead, whose symmetric layout still keeps the
    # plain circle marker, unlike SOT-23/-5's pin1_marker: false).
    sot_text = generate_footprint("SOT-23-6", FAMILY_TREE_PATH, name="SOT236_TEST")
    assert "(fp_circle" in sot_text
    assert "(fill yes)" in sot_text


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
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
    assert "(start -3.61 -3.61)" in text
    # Leg now reaches the courtyard jog (-3.3) instead of the old fixed
    # -3.31 -- a 0.01mm difference for this specific variant, since its
    # jog happens to sit almost exactly where the old fixed length did.
    assert "(end -3.3 -3.61)" in text
    assert "(end -3.61 -3.3)" in text


def test_generate_footprint_qfp48_silk_matches_real_corner_position():
    text = generate_footprint("LQFP-48", FAMILY_TREE_PATH, name="LQFP48_TEST")
    # Same 7x7mm body as LQFP-32, but LQFP-48's own pad layout gives a
    # different jog position -- -3.15, close to real KiCad's own 0.45mm
    # leg for this package (real: -3.16), unlike the old fixed -3.31
    # this project previously used for every LQFP variant alike.
    assert "(start -3.61 -3.61)" in text
    assert "(end -3.15 -3.61)" in text


def test_generate_footprint_qfp100_silk_matches_real_corner_position():
    # Real LQFP-100_14x14mm_P0.5mm.kicad_mod corner marks are at
    # (+-7.11, +-7.11) -- proves body_size derivation
    # (courtyard_body_size + 0.22) generalizes beyond the 7x7mm bodies
    # LQFP-32/LQFP-48 share, to a 14x14mm body.
    text = generate_footprint("LQFP-100", FAMILY_TREE_PATH, name="LQFP100_TEST")
    assert "(start -7.11 -7.11)" in text
    assert "(end -6.4 -7.11)" in text


def test_generate_footprint_qfp32_pad_offset_derived_from_courtyard_body_size():
    # LQFP-32's yaml no longer declares pad_offset directly -- this proves
    # generate_footprint() forwards courtyard_body_size through to
    # quad_perimeter so it can derive pad_offset itself.
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
    assert "(at -4.175 -2.8)" in text


def test_generate_footprint_qfp48_pad_offset_uses_override_extension():
    # LQFP-48 overrides pad_lead_extension to 0.6625 at the yaml level.
    text = generate_footprint("LQFP-48", FAMILY_TREE_PATH, name="LQFP48_TEST")
    assert "(at -4.1625" in text


def test_generate_footprint_does_not_leak_body_size_to_generator():
    # If pipeline.py forgot to pop body_size before calling the generator,
    # this raises TypeError("unexpected keyword argument").
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
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


def test_generate_footprint_sot236_still_has_circle_pin1_marker():
    # Regression guard: DIP opted out (pin1_marker: false) and SOIC/LQFP/
    # QFN opted into the triangle style -- SOT-23-6's symmetric layout
    # still gets the plain circle marker (pin1_marker_style defaults to
    # "circle"), unaffected by any of that.
    text = generate_footprint("SOT-23-6", FAMILY_TREE_PATH, name="SOT236_TEST")
    assert "fp_circle" in text


def test_generate_footprint_does_not_leak_pin1_marker_to_generator():
    # If pipeline.py forgot to pop pin1_marker before calling the
    # generator, this raises TypeError("unexpected keyword argument").
    text = generate_footprint("R-0603", FAMILY_TREE_PATH, name="R0603_TEST")
    assert text  # got here without raising


def test_generate_footprint_qfn12_has_triangle_pin1_marker():
    fp = generate_footprint("QFN-12", FAMILY_TREE_PATH, name="TEST")
    # Exactly one fp_poly on F.SilkS with 3 points -- the pin-1
    # triangle. (The F.Fab chamfer outline is also a Poly, but on
    # F.Fab with 5 points, so this regex -- scoped to F.SilkS -- won't
    # match it.)
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        fp, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_does_not_leak_pin1_marker_style_to_generator():
    # If pipeline.py forgot to pop pin1_marker_style before calling the
    # generator, quad_perimeter would raise TypeError for an unexpected
    # kwarg -- this just has to not raise.
    generate_footprint("QFN-12", FAMILY_TREE_PATH, name="TEST")


def test_generate_footprint_soic8_has_triangle_pin1_marker():
    fp = generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="TEST")
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        fp, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_lqfp32_has_triangle_pin1_marker():
    fp = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="TEST")
    silk_triangles = re.findall(
        r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
        r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
        r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)',
        fp, re.S,
    )
    assert len(silk_triangles) == 1
    points = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", silk_triangles[0])
    assert len(points) == 3


def test_generate_footprint_does_not_leak_pin1_triangle_params_to_generator():
    # If pipeline.py forgot to pop pin1_triangle_axis/_size/_anchor_mm
    # before calling the generator, this raises TypeError for an
    # unexpected kwarg -- this just has to not raise.
    generate_footprint("SOIC-8", FAMILY_TREE_PATH, name="TEST")
    generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="TEST")


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
    # SOIC/LQFP/SOT use. Matches real R_Axial_DIN0204 exactly.
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
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
    assert text.count("(fp_rect") == 0
    assert "(start -3.75 -3.75)" in text
    assert "(start -5.175 -3.3)" in text
    assert "(end 5.175 3.3)" in text


def test_generate_footprint_qfp48_courtyard_matches_stepped_shape():
    text = generate_footprint("LQFP-48", FAMILY_TREE_PATH, name="LQFP48_TEST")
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
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
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
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
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
    for descriptor in ("DIP-16", "SOIC-8", "LQFP-32", "R-0603", "SOT-23"):
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


def test_dip_regular_width_uses_larger_body_at_pin_count_22_and_24():
    # Real KiCad's DIP-22/DIP-24_W10.16mm.kicad_mod have a genuinely
    # larger real body (silk 7.84mm/fab 9.14mm) than every other
    # regular-width pin count checked (4-16: 6.47mm/6.35mm) -- confirmed
    # by byte-level bounding-box comparison. DIP-22/DIP-24's own
    # children in data/kicad-fpdb.yaml override this via a dict-merge
    # (see test_family_tree.py's equivalent synthetic-yaml test); this
    # locks in the exact real-data values.
    for descriptor in ("DIP-22 r", "DIP-24 r"):
        resolved = resolve_descriptor(load_family_tree(FAMILY_TREE_PATH), parse_descriptor(descriptor))
        assert resolved.params["body_width"] == 7.84, descriptor
        assert resolved.params["fab_body_width"] == 9.14, descriptor


def test_dip_24_narrow_and_wide_are_unaffected_by_regular_override():
    # DIP-24's narrow/wide widths must keep the root's own (unchanged)
    # body_width -- the "regular" override on DIP-24's child node must
    # not leak onto its sibling width classes.
    narrow = resolve_descriptor(load_family_tree(FAMILY_TREE_PATH), parse_descriptor("DIP-24"))
    assert narrow.params["body_width"] == 5.3
    wide = resolve_descriptor(load_family_tree(FAMILY_TREE_PATH), parse_descriptor("DIP-24 w"))
    assert wide.params["body_width"] == 12.92


def test_socket_courtyard_sits_outside_the_socket_silk_rectangle():
    # A real _Socket footprint's courtyard is measured from each pin's
    # own center by a flat 1.52mm (x) / 1.58mm (y) -- *larger* than the
    # socket silk rectangle's own 1.33mm/1.39mm center-based margin, so
    # the courtyard properly sits outside the silk describing the
    # socket's own typical size/shape. Confirmed by byte-level
    # comparison against DIP-8/14/16 and CERDIP-16/24's own Socket
    # reference files -- this locks in the exact real-data values.
    for descriptor in ("DIP-14 socket", "CERDIP-16 socket"):
        resolved = resolve_descriptor(load_family_tree(FAMILY_TREE_PATH), parse_descriptor(descriptor))
        assert resolved.params["courtyard_margin_x"] == 1.52, descriptor
        assert resolved.params["courtyard_margin_y"] == 1.58, descriptor
        assert resolved.params["courtyard_margin_x"] > resolved.params["socket_margin_x"], descriptor
        assert resolved.params["courtyard_margin_y"] > resolved.params["socket_margin_y"], descriptor


def test_longpads_shrinks_body_width_for_narrow_and_wide_but_not_regular():
    # Real KiCad's LongPads variant shrinks the oversized F.SilkS body by
    # a flat 0.8mm for narrow/wide, but leaves "regular" completely
    # unchanged at small pin counts (6.47mm either way) -- confirmed by
    # byte-level comparison against DIP-8_W10.16mm(_LongPads).
    tree = load_family_tree(FAMILY_TREE_PATH)
    narrow = resolve_descriptor(tree, parse_descriptor("DIP-14 longpads"))
    assert narrow.params["body_width"] == 4.5
    wide = resolve_descriptor(tree, parse_descriptor("DIP-24 w longpads"))
    assert wide.params["body_width"] == 12.12
    regular_small = resolve_descriptor(tree, parse_descriptor("DIP-8 r longpads"))
    assert regular_small.params["body_width"] == 6.47


def test_longpads_shrinks_the_already_oversized_regular_body_at_22_and_24():
    # DIP-22/DIP-24's regular body is already overridden to 7.84mm (see
    # test_dip_regular_width_uses_larger_body_at_pin_count_22_and_24);
    # LongPads applies the same -0.8mm shrink to *that* value (7.04mm),
    # not the small-pin-count default -- these two variants declare
    # their own "longpads" modifier for exactly this reason.
    tree = load_family_tree(FAMILY_TREE_PATH)
    for descriptor in ("DIP-22 r longpads", "DIP-24 r longpads"):
        resolved = resolve_descriptor(tree, parse_descriptor(descriptor))
        assert resolved.params["body_width"] == 7.04, descriptor


def test_longpads_pad_size_is_elongated():
    resolved = resolve_descriptor(
        load_family_tree(FAMILY_TREE_PATH), parse_descriptor("DIP-14 longpads")
    )
    assert resolved.params["pad_size"] == [2.4, 1.6]


def test_longpads_generates_oval_shape_for_non_pin1_pads():
    text = generate_footprint("DIP-14 longpads", FAMILY_TREE_PATH, name="X")
    assert '(pad "1" thru_hole roundrect' in text
    assert '(pad "2" thru_hole oval' in text


def test_socket_margin_is_measured_from_pad_center_not_edge():
    # Real KiCad's Socket silk margin is fixed relative to each pin's
    # own center (1.33mm), not the pad bbox edge -- this only coincided
    # with an edge-based 0.53mm margin as long as every pad was the same
    # 1.6mm size. Confirmed exact against DIP-8/14/16_Socket.
    resolved = resolve_descriptor(load_family_tree(FAMILY_TREE_PATH), parse_descriptor("DIP-14 socket"))
    assert resolved.params["socket_margin_x"] == 1.33
    assert resolved.params["courtyard_from_pad_center"] is True


def test_socket_longpads_combo_uses_a_distinct_socket_margin():
    # Real KiCad's Socket+LongPads combo has its own socket_margin_x
    # (1.44mm), different from Socket alone (1.33mm) -- confirmed exact
    # against DIP-14/DIP-24_Socket_LongPads. Order of the two modifier
    # tokens in the descriptor must not matter (the "_with" override is
    # checked against the full active-token set, not applied
    # sequentially).
    tree = load_family_tree(FAMILY_TREE_PATH)
    for descriptor in ("DIP-14 socket longpads", "DIP-14 longpads socket"):
        resolved = resolve_descriptor(tree, parse_descriptor(descriptor))
        assert resolved.params["socket_margin_x"] == 1.44, descriptor


def test_socket_longpads_combo_courtyard_is_unchanged_from_socket_alone():
    # Unlike the silk margin, the real Socket courtyard is byte-identical
    # whether or not LongPads is also active (confirmed against
    # DIP-14_Socket vs. DIP-14_Socket_LongPads) -- it's already
    # center-based and LongPads doesn't move the pin centers.
    tree = load_family_tree(FAMILY_TREE_PATH)
    socket_only = resolve_descriptor(tree, parse_descriptor("DIP-14 socket"))
    socket_longpads = resolve_descriptor(tree, parse_descriptor("DIP-14 socket longpads"))
    assert socket_only.params["courtyard_margin_x"] == socket_longpads.params["courtyard_margin_x"]
    assert socket_only.params["courtyard_margin_y"] == socket_longpads.params["courtyard_margin_y"]


def test_cerdip_8_socket_longpads_combo_uses_its_own_oversized_y_margin_but_shared_x():
    # CERDIP-8's own "socket" override replaces the root's entirely (see
    # its yaml comment), so it must redeclare its own "_with: longpads"
    # too, or the combo's socket_margin_x correction would silently be
    # lost for this specific variant.
    resolved = resolve_descriptor(
        load_family_tree(FAMILY_TREE_PATH), parse_descriptor("CERDIP-8 socket longpads")
    )
    assert resolved.params["socket_margin_x"] == 1.44
    assert resolved.params["socket_margin_y"] == 2.915


def test_smdip_reuses_dip_constants_but_has_its_own_body_width_tiers():
    # SMDIP reuses DIP's own body_margin/fab_body_margin/fab_chamfer/
    # notch_radius/courtyard_margin_x exactly (confirmed via
    # _pad_center_extent-based margins against real SMDIP files), but
    # its silk/fab body_width is keyed by its own width tiers, not
    # DIP's narrow/regular/wide -- "medium" (9.53mm) and "broad"
    # (11.48mm) share the same body_width/fab_body_width pair despite
    # different row spacing, confirmed exact against SMDIP-*_W9.53mm
    # and SMDIP-*_W11.48mm.
    tree = load_family_tree(FAMILY_TREE_PATH)
    narrow = resolve_descriptor(tree, parse_descriptor("SMDIP-14"))
    assert narrow.params["body_margin"] == 1.33
    assert narrow.params["fab_body_margin"] == 1.27
    assert narrow.params["courtyard_margin_x"] == 0.25
    assert narrow.params["body_width"] == 4.9

    medium = resolve_descriptor(tree, parse_descriptor("SMDIP-14 m"))
    broad = resolve_descriptor(tree, parse_descriptor("SMDIP-14 b"))
    assert medium.params["body_width"] == broad.params["body_width"] == 6.47
    assert medium.params["fab_body_width"] == broad.params["fab_body_width"] == 6.35


def test_smdip_pads_are_smd_centered_and_uniformly_roundrect():
    text = generate_footprint("SMDIP-14", FAMILY_TREE_PATH, name="X")
    assert '(pad "1" smd roundrect' in text
    assert '(pad "2" smd roundrect' in text
    assert "(drill" not in text
