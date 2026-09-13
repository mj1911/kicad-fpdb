import pytest

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.pipeline import GENERATORS, _add_outline, generate_footprint

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"


def _dip16_geometry():
    tree = load_family_tree(FAMILY_TREE_PATH)
    resolved = resolve_descriptor(tree, parse_descriptor("DIP-16"))
    geometry = GENERATORS[resolved.generator](**resolved.params)
    geometry.name = "DIP16_TEST"
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


def test_add_outline_produces_silkscreen_body_and_pin1_marker():
    geometry = _dip16_geometry()
    _add_outline(geometry)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    # 4 body sides + 1 pin-1 corner marker.
    assert len(silk_lines) == 5

    # Pad bbox is (-0.8, -0.8) to (8.42, 18.58); silkscreen adds 0.2mm margin,
    # giving a body rect of (-1.0, -1.0) to (8.62, 18.78). Pad "1" sits at
    # (0, 0), nearest to the (-1.0, -1.0) corner.
    marker = silk_lines[-1]
    assert marker.start == pytest.approx((-0.5, -1.0))
    assert marker.end == pytest.approx((-1.0, -0.5))


def test_generate_footprint_includes_outline_geometry():
    text = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP16_TEST")
    assert "(fp_rect" in text
    assert '(layer "F.CrtYd")' in text
    assert "(fp_line" in text
    assert '(layer "F.SilkS")' in text
