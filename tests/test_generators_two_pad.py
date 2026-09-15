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


def test_r1206_pad_uses_clamped_roundrect_rratio():
    # R-1206's real pad (1.125mm min dimension) clamps to an absolute
    # 0.25mm max corner radius, not the flat nominal 0.25 ratio.
    geom = two_pad_chip(pad_pitch=2.925, pad_size=(1.125, 1.75))
    pad1 = geom.pads[0]
    assert abs(pad1.roundrect_rratio - 0.222222) < 1e-5


def test_uncentered_thru_hole_matches_real_axial_resistor():
    # Real THT axial resistors place pad 1 at the origin and pad 2 at
    # (pitch, 0) -- not symmetric about x=0 like SMD chip passives.
    geom = two_pad_chip(
        pad_pitch=7.62, pad_size=(1.4, 1.4), pad_shape="circle",
        pad_type="thru_hole", drill=0.7, centered=False,
    )
    assert len(geom.pads) == 2
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert pad1.at == (0.0, 0.0)
    assert pad1.pad_type == "thru_hole"
    assert pad1.shape == "circle"
    assert pad1.drill == 0.7
    assert pad1.roundrect_rratio is None

    pad2 = by_number["2"]
    assert pad2.at == (7.62, 0.0)
    assert pad2.drill == 0.7


def test_centered_default_is_unaffected_by_new_params():
    # Regression guard: SMD chip passives (centered=True default, no
    # drill) are unaffected by the new thru-hole support.
    geom = two_pad_chip(pad_pitch=1.65, pad_size=(0.8, 0.95))
    assert geom.pads[0].pad_type == "smd"
    assert geom.pads[0].drill is None
