from kicad_fpdb.geometry import FootprintGeometry, Line, Pad, Poly, Rect, Text, pad_bounding_box


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


def test_footprint_geometry_texts_default_empty():
    geom = FootprintGeometry(name="TEST")
    assert geom.texts == []


def test_text_holds_fields():
    text = Text(kind="reference", text="REF**", at=(1.0, -2.0), layer="F.Fab")
    assert text.kind == "reference"
    assert text.text == "REF**"
    assert text.at == (1.0, -2.0)
    assert text.layer == "F.Fab"


def test_footprint_geometry_lines_and_rects_default_empty():
    geom = FootprintGeometry(name="TEST")
    assert geom.lines == []
    assert geom.rects == []
    assert geom.polys == []


def test_poly_holds_fields():
    poly = Poly(points=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], layer="F.SilkS")
    assert poly.points == [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    assert poly.layer == "F.SilkS"
    assert poly.width == 0.12
    assert poly.fill == "yes"


def test_line_holds_fields():
    line = Line(start=(0.0, 0.0), end=(1.0, 2.0), layer="F.SilkS")
    assert line.start == (0.0, 0.0)
    assert line.end == (1.0, 2.0)
    assert line.layer == "F.SilkS"
    assert line.width == 0.12


def test_rect_holds_fields():
    rect = Rect(start=(0.0, 0.0), end=(1.0, 2.0), layer="F.CrtYd")
    assert rect.start == (0.0, 0.0)
    assert rect.end == (1.0, 2.0)
    assert rect.layer == "F.CrtYd"
    assert rect.width == 0.05
    assert rect.fill == "no"


def test_pad_bounding_box_accounts_for_pad_size():
    pads = [
        Pad(number="1", pad_type="smd", shape="roundrect", at=(0.0, 0.0), size=(1.0, 2.0)),
        Pad(number="2", pad_type="smd", shape="roundrect", at=(10.0, 5.0), size=(1.0, 2.0)),
    ]
    min_x, min_y, max_x, max_y = pad_bounding_box(pads)
    assert min_x == -0.5
    assert max_x == 10.5
    assert min_y == -1.0
    assert max_y == 6.0
