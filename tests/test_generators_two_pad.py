from kicad_fpdb.generators.two_pad import two_pad_chip


def test_r0603_matches_real_kicad_footprint():
    geom = two_pad_chip(pad_pitch=1.65, pad_size=(0.8, 0.95))
    assert len(geom.pads) == 2
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-0.825)) < 1e-6
    assert pad1.at[1] == 0.0
    assert pad1.size == (0.8, 0.95)
    assert pad1.pad_type == "smd"
    assert pad1.roundrect_rratio == 0.25

    pad2 = by_number["2"]
    assert abs(pad2.at[0] - 0.825) < 1e-6
    assert pad2.at[1] == 0.0
