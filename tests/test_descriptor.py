import pytest

from kicad_fpdb.descriptor import ParsedDescriptor, parse_descriptor


def test_parse_family_variant_and_modifiers():
    result = parse_descriptor("DIP-16 r 0.1")
    assert result == ParsedDescriptor(family="DIP", variant="16", modifier_tokens=["r", "0.1"])


def test_parse_no_modifiers():
    result = parse_descriptor("SOIC-8")
    assert result == ParsedDescriptor(family="SOIC", variant="8", modifier_tokens=[])


def test_parse_non_numeric_variant():
    result = parse_descriptor("R-0603")
    assert result == ParsedDescriptor(family="R", variant="0603", modifier_tokens=[])


def test_parse_empty_string_raises():
    with pytest.raises(ValueError):
        parse_descriptor("")


def test_parse_missing_dash_raises():
    with pytest.raises(ValueError):
        parse_descriptor("DIP16")
