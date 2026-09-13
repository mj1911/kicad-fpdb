from kicad_fpdb.generators.dual_row import dual_row_grid


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
