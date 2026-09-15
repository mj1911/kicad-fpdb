import pytest

from kicad_fpdb.generators.quad_perimeter import quad_perimeter


def test_lqfp32_matches_real_kicad_footprint():
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_offset=4.175, pad_size=(1.5, 0.5))
    assert len(geom.pads) == 32
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-4.175)) < 1e-6
    assert abs(pad1.at[1] - (-2.8)) < 1e-6
    assert pad1.size == (1.5, 0.5)

    pad8 = by_number["8"]
    assert abs(pad8.at[0] - (-4.175)) < 1e-6
    assert abs(pad8.at[1] - 2.8) < 1e-6

    pad9 = by_number["9"]
    assert abs(pad9.at[0] - (-2.8)) < 1e-6
    assert abs(pad9.at[1] - 4.175) < 1e-6
    assert pad9.size == (0.5, 1.5)

    pad17 = by_number["17"]
    assert abs(pad17.at[0] - 4.175) < 1e-6
    assert abs(pad17.at[1] - 2.8) < 1e-6
    assert pad17.size == (1.5, 0.5)


def test_quad_perimeter_pad_stays_nominal_under_1mm():
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_offset=4.175, pad_size=(1.2, 0.5))
    pad1 = geom.pads[0]
    assert pad1.roundrect_rratio == 0.25  # min dimension 0.5mm stays unclamped


def test_quad_perimeter_pad_clamps_above_1mm():
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_offset=4.175, pad_size=(1.2, 1.5))
    pad1 = geom.pads[0]
    assert abs(pad1.roundrect_rratio - (0.25 / 1.2)) < 1e-5


def test_quad_perimeter_derives_pad_offset_from_body_size_default_extension():
    # Real LQFP-32_7x7mm_P0.8mm.kicad_mod: body 7x7mm, pad "1" at x=-4.175.
    # 7.0/2 + 0.675 (the default lead extension) == 4.175 exactly.
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_size=(1.5, 0.5), courtyard_body_size=7.0)
    pad1 = geom.pads[0]
    assert abs(pad1.at[0] - (-4.175)) < 1e-9


def test_quad_perimeter_derives_pad_offset_with_custom_extension():
    # Real LQFP-48_7x7mm_P0.5mm.kicad_mod: body 7x7mm, pad "1" at x=-4.1625.
    # 7.0/2 + 0.6625 (this package's own lead extension) == 4.1625 exactly.
    geom = quad_perimeter(pin_count=48, pitch=0.5, pad_size=(1.475, 0.3),
                           courtyard_body_size=7.0, pad_lead_extension=0.6625)
    pad1 = geom.pads[0]
    assert abs(pad1.at[0] - (-4.1625)) < 1e-9


def test_quad_perimeter_explicit_pad_offset_overrides_derivation():
    # An escape hatch: an explicit pad_offset must win even when a
    # (deliberately wrong) courtyard_body_size is also given.
    geom = quad_perimeter(pin_count=32, pitch=0.8, pad_size=(1.5, 0.5),
                           courtyard_body_size=999.0, pad_offset=4.175)
    pad1 = geom.pads[0]
    assert abs(pad1.at[0] - (-4.175)) < 1e-9


def test_quad_perimeter_raises_without_pad_offset_or_body_size():
    with pytest.raises(ValueError, match="pad_offset or courtyard_body_size"):
        quad_perimeter(pin_count=32, pitch=0.8, pad_size=(1.5, 0.5))
