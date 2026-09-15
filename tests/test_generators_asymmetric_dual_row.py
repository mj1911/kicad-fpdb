from kicad_fpdb.generators.asymmetric_dual_row import asymmetric_dual_row


def test_sot23_matches_real_kicad_footprint():
    geom = asymmetric_dual_row(
        left_offsets=[-0.95, 0.95], right_offsets=[0], row_spacing=1.875,
        pad_size=(1.475, 0.6), pad_shape="roundrect", pad_type="smd",
    )
    assert len(geom.pads) == 3
    by_number = {pad.number: pad for pad in geom.pads}

    pad1 = by_number["1"]
    assert abs(pad1.at[0] - (-0.9375)) < 1e-6
    assert abs(pad1.at[1] - (-0.95)) < 1e-6
    assert pad1.pad_type == "smd"
    assert pad1.shape == "roundrect"
    assert pad1.size == (1.475, 0.6)

    pad2 = by_number["2"]
    assert abs(pad2.at[0] - (-0.9375)) < 1e-6
    assert abs(pad2.at[1] - 0.95) < 1e-6

    pad3 = by_number["3"]
    assert abs(pad3.at[0] - 0.9375) < 1e-6
    assert abs(pad3.at[1] - 0.0) < 1e-6


def test_sot23_5_matches_real_kicad_footprint():
    # 3 pins left, 2 on right -- right column uses only the outer two of
    # the shared 3-position lead-frame grid, not independently centered.
    geom = asymmetric_dual_row(
        left_offsets=[-0.95, 0, 0.95], right_offsets=[0.95, -0.95], row_spacing=2.275,
        pad_size=(1.325, 0.6), pad_shape="roundrect", pad_type="smd",
    )
    assert len(geom.pads) == 5
    by_number = {pad.number: pad for pad in geom.pads}

    for number, expected_y in [("1", -0.95), ("2", 0.0), ("3", 0.95)]:
        pad = by_number[number]
        assert abs(pad.at[0] - (-1.1375)) < 1e-6
        assert abs(pad.at[1] - expected_y) < 1e-6

    for number, expected_y in [("4", 0.95), ("5", -0.95)]:
        pad = by_number[number]
        assert abs(pad.at[0] - 1.1375) < 1e-6
        assert abs(pad.at[1] - expected_y) < 1e-6


def test_roundrect_rratio_uses_clamped_formula():
    geom = asymmetric_dual_row(
        left_offsets=[-0.95, 0.95], right_offsets=[0], row_spacing=1.875,
        pad_size=(1.475, 0.6), pad_shape="roundrect", pad_type="smd",
    )
    # min pad dimension 0.6mm stays under the 1mm clamp threshold.
    assert geom.pads[0].roundrect_rratio == 0.25


def test_non_roundrect_pads_have_no_rratio():
    geom = asymmetric_dual_row(
        left_offsets=[-0.95, 0.95], right_offsets=[0], row_spacing=1.875,
        pad_size=(1.475, 0.6), pad_shape="circle", pad_type="smd",
    )
    assert all(pad.roundrect_rratio is None for pad in geom.pads)
