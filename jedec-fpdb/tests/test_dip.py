import pytest

from jedec_fpdb import dip


def test_generate_produces_correct_pad_count():
    fp = dip.generate("narrow", 16, "N")
    assert len(fp.pads) == 16
    assert {p.number for p in fp.pads} == set(range(1, 17))


def test_pin1_is_rect_others_are_circle():
    fp = dip.generate("narrow", 16, "N")
    pad1 = next(p for p in fp.pads if p.number == 1)
    others = [p for p in fp.pads if p.number != 1]
    assert pad1.shape == "rect"
    assert all(p.shape == "circle" for p in others)


@pytest.mark.parametrize("width_class", ["narrow", "regular", "wide"])
def test_row_spacing_and_pitch_match_ms001(width_class):
    from data import ms001_dip
    fp = dip.generate(width_class, 24, "N")
    pad1 = next(p for p in fp.pads if p.number == 1)
    pad2 = next(p for p in fp.pads if p.number == 2)
    pad13 = next(p for p in fp.pads if p.number == 13)  # first right-column pin (24/2 + 1)
    assert abs(pad2.y_mm - pad1.y_mm) == pytest.approx(ms001_dip.PITCH_MM)
    assert abs(pad13.x_mm - pad1.x_mm) == pytest.approx(ms001_dip.row_spacing_mm(width_class))


def test_no_two_pads_share_a_position():
    fp = dip.generate("narrow", 24, "N")
    positions = [(round(p.x_mm, 6), round(p.y_mm, 6)) for p in fp.pads]
    assert len(positions) == len(set(positions))


def test_courtyard_encloses_all_pads():
    fp = dip.generate("narrow", 8, "N")
    for p in fp.pads:
        r = p.diameter_mm / 2
        assert fp.courtyard.x1_mm <= p.x_mm - r
        assert fp.courtyard.x2_mm >= p.x_mm + r
        assert fp.courtyard.y1_mm <= p.y_mm - r
        assert fp.courtyard.y2_mm >= p.y_mm + r


def test_unsupported_width_class_raises():
    with pytest.raises(ValueError):
        dip.generate("extra_wide", 16, "N")


def test_invalid_pin_count_raises():
    with pytest.raises(ValueError):
        dip.generate("narrow", 15, "N")
