from kicad_fpdb.geometry import Pad, FootprintGeometry


def test_pad_defaults():
    pad = Pad(number="1", pad_type="smd", shape="roundrect", at=(0.0, 0.0), size=(0.8, 0.95))
    assert pad.drill is None
    assert pad.roundrect_rratio is None


def test_footprint_geometry_holds_pads():
    pad = Pad(number="1", pad_type="smd", shape="roundrect", at=(0.0, 0.0), size=(0.8, 0.95))
    geom = FootprintGeometry(name="TEST", pads=[pad])
    assert geom.name == "TEST"
    assert geom.pads == [pad]


def test_pad_normalizes_list_size_and_at_to_tuples():
    # YAML-derived pad_size/at arrive as lists in some generator call
    # sites; Pad should normalize both to tuples regardless of input type
    # so `pad.size`/`pad.at` are consistently `tuple[float, float]`.
    pad = Pad(number="1", pad_type="smd", shape="roundrect", at=[0.0, 0.0], size=[0.8, 0.95])
    assert pad.at == (0.0, 0.0)
    assert pad.size == (0.8, 0.95)
    assert isinstance(pad.at, tuple)
    assert isinstance(pad.size, tuple)
