import pytest

from data import ms001_dip


def test_basic_dimensions():
    assert ms001_dip.PITCH_MM == pytest.approx(2.54)
    assert ms001_dip.ROW_SPACING_MM == pytest.approx(7.62)
    assert ms001_dip.BODY_WIDTH_MM == pytest.approx(6.35)
    assert ms001_dip.LEAD_WIDTH_MAX_MM == pytest.approx(0.559)


@pytest.mark.parametrize("pin_count,expected_mm", [
    (14, 19.05),
    (16, 20.066),
    (18, 22.86),
    (20, 26.162),
    (22, 29.337),
    (24, 31.75),
    (28, 35.687),
])
def test_body_length_table_lookup(pin_count, expected_mm):
    assert ms001_dip.body_length_mm(pin_count) == pytest.approx(expected_mm)


def test_body_length_8_pin_is_regression_extrapolation():
    # N=8 has no full-lead entry in MS-001's own table (see design spec) --
    # this only bounds the extrapolation to a sane range, since we can't
    # independently verify a precise "official" value for it.
    result = ms001_dip.body_length_mm(8)
    assert 8.0 < result < 14.0


def test_body_length_rejects_odd_pin_count():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm(15)


def test_body_length_rejects_too_few_pins():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm(2)


def test_extrapolate_body_length_on_synthetic_linear_data():
    # Verifies the regression math itself against a table with a known
    # exact linear relationship (D = N), independent of MS-001's real,
    # non-linear numbers.
    table = {10: 10.0, 20: 20.0, 30: 30.0}
    result = ms001_dip._extrapolate_body_length_mm(table, 40)
    assert result == pytest.approx(40.0)
