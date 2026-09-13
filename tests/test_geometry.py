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
