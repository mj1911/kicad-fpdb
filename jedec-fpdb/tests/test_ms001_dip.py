import pytest

from data import ms001_dip


def test_shared_dimensions():
    assert ms001_dip.PITCH_MM == pytest.approx(2.54)
    assert ms001_dip.LEAD_WIDTH_MAX_MM == pytest.approx(0.5588)


@pytest.mark.parametrize("width_class,expected_row_spacing_mm,expected_body_width_mm", [
    ("narrow", 7.62, 6.35),
    ("regular", 10.16, 9.144),
    ("wide", 15.24, 13.5255),
])
def test_row_spacing_and_body_width(width_class, expected_row_spacing_mm, expected_body_width_mm):
    assert ms001_dip.row_spacing_mm(width_class) == pytest.approx(expected_row_spacing_mm)
    assert ms001_dip.body_width_mm(width_class) == pytest.approx(expected_body_width_mm)


@pytest.mark.parametrize("width_class,pin_count,expected_mm", [
    ("narrow", 14, 19.05),
    ("narrow", 16, 20.066),
    ("narrow", 18, 22.86),
    ("narrow", 20, 26.162),
    ("narrow", 22, 29.337),
    ("narrow", 24, 31.75),
    ("narrow", 28, 35.687),
    ("regular", 22, 27.559),
    ("regular", 24, 30.099),
    ("regular", 28, 35.179),
    ("regular", 32, 40.259),
    ("wide", 24, 31.0),
    ("wide", 28, 37.4),
    ("wide", 40, 51.75),
    ("wide", 48, 61.9),
])
def test_body_length_table_lookup(width_class, pin_count, expected_mm):
    assert ms001_dip.body_length_mm(width_class, pin_count) == pytest.approx(expected_mm)


@pytest.mark.parametrize("pin_count,lower_mm,upper_mm", [
    (4, 4.0, 8.0),
    (6, 6.0, 10.0),
    (8, 8.0, 14.0),
])
def test_narrow_body_length_below_table_is_regression_extrapolation(pin_count, lower_mm, upper_mm):
    # N=4/6/8 have no full-lead entry in MS-001's own table (see design
    # spec) -- this only bounds the extrapolation to a sane range, since
    # we can't independently verify a precise "official" value for any
    # of them. (Cross-checked against real KiCad DIP-4/6/8 files in
    # test_compare.py, where all three land comfortably inside the
    # existing comparison tolerances.)
    result = ms001_dip.body_length_mm("narrow", pin_count)
    assert lower_mm < result < upper_mm


@pytest.mark.parametrize("pin_count,lower_mm,upper_mm", [
    (4, 3.0, 7.0),
    (6, 4.0, 9.0),
    (8, 6.0, 11.0),
    (10, 8.0, 14.0),
    (12, 10.0, 16.0),
    (14, 12.0, 19.0),
    (16, 14.0, 21.0),
])
def test_regular_body_length_below_table_is_regression_extrapolation(pin_count, lower_mm, upper_mm):
    # MS-010's own documented range starts at N=22 -- lower pin counts
    # are pure regression extrapolation. This is lower-risk than it
    # sounds: the table's 4 documented points (N=22/24/28/32) fall on a
    # perfectly linear D-vs-N line (slope exactly half the lead pitch),
    # so the fit isn't guessing at curvature the way narrow's noisier
    # table would be. Cross-checked against real KiCad
    # DIP-{4,6,8,10,12,14,16}_W10.16mm files in test_compare.py.
    result = ms001_dip.body_length_mm("regular", pin_count)
    assert lower_mm < result < upper_mm


@pytest.mark.parametrize("pin_count,lower_mm,upper_mm", [
    (26, 32.0, 37.0),
    (32, 38.0, 46.0),
    (42, 52.0, 58.0),
    (64, 68.0, 90.0),
])
def test_wide_body_length_outside_table_is_regression_extrapolation(pin_count, lower_mm, upper_mm):
    # MS-011's own documented points (N=24/28/40/48) don't cover every
    # real wide DIP pin count -- N=26/32/42 fall inside/near that range,
    # N=64 is an extension beyond the table's own max. Cross-checked
    # against real KiCad DIP-{26,32,42,64}_W15.24mm files in
    # test_compare.py.
    result = ms001_dip.body_length_mm("wide", pin_count)
    assert lower_mm < result < upper_mm


def test_body_length_rejects_odd_pin_count():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm("narrow", 15)


def test_body_length_rejects_too_few_pins():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm("narrow", 2)


def test_body_length_rejects_unsupported_width_class():
    with pytest.raises(ValueError):
        ms001_dip.body_length_mm("extra_wide", 16)


def test_row_spacing_rejects_unsupported_width_class():
    with pytest.raises(ValueError):
        ms001_dip.row_spacing_mm("extra_wide")


def test_extrapolate_body_length_on_synthetic_linear_data():
    # Verifies the regression math itself against a table with a known
    # exact linear relationship (D = N), independent of any real
    # document's own non-linear numbers.
    table = {10: 10.0, 20: 20.0, 30: 30.0}
    result = ms001_dip._extrapolate_body_length_mm(table, 40)
    assert result == pytest.approx(40.0)
