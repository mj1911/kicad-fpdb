import pytest
from kicad_fpdb.generators.dual_row import dual_row_grid


def test_odd_pin_count_raises_value_error():
    """Verify that dual_row_grid raises ValueError for odd pin_count."""
    with pytest.raises(ValueError, match="dual_row_grid requires an even pin_count"):
        dual_row_grid(
            pin_count=15, pitch=2.54, row_spacing=7.62,
            pad_size=(1.6, 1.6), pad_shape="dip_pin1_marker",
            pad_type="thru_hole", drill=0.8, centered=False,
        )


def test_dip16_matches_real_kicad_footprint():
    geom = dual_row_grid(
        pin_count=16, pitch=2.54, row_spacing=7.62,
        pad_size=(1.6, 1.6), pad_shape="dip_pin1_marker",
        pad_type="thru_hole", drill=0.8, centered=False,
    )
    assert len(geom.pads) == 16

    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert pad1.at == (0.0, 0.0)
    assert pad1.shape == "roundrect"
    assert pad1.pad_type == "thru_hole"
    assert pad1.drill == 0.8
    assert abs(pad1.roundrect_rratio - 0.15625) < 1e-4

    pad2 = by_number["2"]
    assert pad2.at == (0.0, 2.54)
    assert pad2.shape == "circle"
    assert pad2.roundrect_rratio is None

    pad8 = by_number["8"]
    assert pad8.at == (0.0, 17.78)

    pad9 = by_number["9"]
    assert pad9.at == (7.62, 17.78)
    assert pad9.shape == "circle"

    pad16 = by_number["16"]
    assert pad16.at == (7.62, 0.0)


def test_soic8_matches_real_kicad_footprint():
    geom = dual_row_grid(
        pin_count=8, pitch=1.27, row_spacing=4.95,
        pad_size=(1.95, 0.6), pad_shape="roundrect",
        pad_type="smd", drill=None, centered=True,
    )
    assert len(geom.pads) == 8
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-2.475)) < 1e-6
    assert abs(pad1.at[1] - (-1.905)) < 1e-6
    assert pad1.pad_type == "smd"
    assert pad1.roundrect_rratio == 0.25

    pad4 = by_number["4"]
    assert abs(pad4.at[0] - (-2.475)) < 1e-6
    assert abs(pad4.at[1] - 1.905) < 1e-6

    pad5 = by_number["5"]
    assert abs(pad5.at[0] - 2.475) < 1e-6
    assert abs(pad5.at[1] - 1.905) < 1e-6

    pad8 = by_number["8"]
    assert abs(pad8.at[0] - 2.475) < 1e-6
    assert abs(pad8.at[1] - (-1.905)) < 1e-6


def test_generic_roundrect_pad_uses_clamped_rratio_above_1mm():
    geom = dual_row_grid(
        pin_count=4, pitch=1.27, row_spacing=4.95,
        pad_size=(1.2, 1.5), pad_shape="roundrect",
        pad_type="smd", drill=None, centered=True,
    )
    pad1 = geom.pads[0]
    assert abs(pad1.roundrect_rratio - (0.25 / 1.2)) < 1e-5
