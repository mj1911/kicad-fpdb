import pytest

from jedec_fpdb import ipc7251

LEAD = 0.559  # MS-001's lead width max, mm


def test_drill_diameter_by_density():
    # Table 3-5 "Hole Diameter Factor": Max 0.25, Nominal 0.20, Least 0.15
    assert ipc7251.drill_diameter_mm(LEAD, "M") == pytest.approx(0.809)
    assert ipc7251.drill_diameter_mm(LEAD, "N") == pytest.approx(0.759)
    assert ipc7251.drill_diameter_mm(LEAD, "L") == pytest.approx(0.709)


def test_pad_diameter_by_density():
    # Table 3-5 "Int. & Ext. Annular ring Excess (added to hole dia.)":
    # Max 0.50, Nominal 0.35, Least 0.30 -- added directly to the drill
    # diameter, not doubled.
    assert ipc7251.pad_diameter_mm(LEAD, "M") == pytest.approx(1.309)
    assert ipc7251.pad_diameter_mm(LEAD, "N") == pytest.approx(1.109)
    assert ipc7251.pad_diameter_mm(LEAD, "L") == pytest.approx(1.009)


def test_courtyard_excess_by_density():
    # Table 3-5 "Courtyard Excess from Component body and/or lands":
    # Max 0.5, Nominal 0.25, Least 0.1
    assert ipc7251.courtyard_excess_mm("M") == pytest.approx(0.5)
    assert ipc7251.courtyard_excess_mm("N") == pytest.approx(0.25)
    assert ipc7251.courtyard_excess_mm("L") == pytest.approx(0.1)


def test_most_is_more_generous_than_nominal_than_least():
    # "Most material condition" (M) is Table 3-5's most generous/
    # conservative density level, "Least" (L) the tightest -- every
    # quantity should reflect that ordering.
    assert ipc7251.pad_diameter_mm(LEAD, "M") > ipc7251.pad_diameter_mm(LEAD, "N") > ipc7251.pad_diameter_mm(LEAD, "L")
    assert ipc7251.courtyard_excess_mm("M") > ipc7251.courtyard_excess_mm("N") > ipc7251.courtyard_excess_mm("L")


def test_unknown_density_raises():
    with pytest.raises(ValueError):
        ipc7251.drill_diameter_mm(LEAD, "X")
    with pytest.raises(ValueError):
        ipc7251.pad_diameter_mm(LEAD, "X")
    with pytest.raises(ValueError):
        ipc7251.courtyard_excess_mm("X")


@pytest.mark.parametrize("raw_mm,expected_mm", [
    (9.079, 9.1),
    (9.10, 9.1),   # already exact -- must not round up further
    (11.2286, 11.3),
    (0.01, 0.1),
])
def test_round_up_to_0_1mm(raw_mm, expected_mm):
    assert ipc7251.round_up_to_0_1mm(raw_mm) == pytest.approx(expected_mm)
