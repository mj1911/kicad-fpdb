import os

import pytest

from jedec_fpdb import compare, dip

KICAD_DIP_DIR = "/usr/share/kicad/footprints/Package_DIP.pretty"

pytestmark = pytest.mark.skipif(
    not os.path.isdir(KICAD_DIP_DIR),
    reason=f"{KICAD_DIP_DIR} not present on this machine",
)

# (width_class, pin_count, real filename). Drill/pad diameter tolerance
# is looser than pitch/row_spacing since real KiCad uses generous,
# round-number pad sizing -- 0.8mm drill / 1.6mm pad regardless of pin
# count or width class -- that noticeably exceeds even IPC-7251's own
# "Maximum" (Level A) density level; see the design spec.
CASES = [
    ("narrow", 4, "DIP-4_W7.62mm.kicad_mod"),
    ("narrow", 6, "DIP-6_W7.62mm.kicad_mod"),
    ("narrow", 8, "DIP-8_W7.62mm.kicad_mod"),
    ("narrow", 14, "DIP-14_W7.62mm.kicad_mod"),
    ("narrow", 16, "DIP-16_W7.62mm.kicad_mod"),
    ("narrow", 24, "DIP-24_W7.62mm.kicad_mod"),
    # regular (.400in / 10.16mm row spacing) -- N=22/24 come directly from
    # MS-010's own table, the rest are regression extrapolation (see
    # test_ms001_dip.py).
    ("regular", 4, "DIP-4_W10.16mm.kicad_mod"),
    ("regular", 6, "DIP-6_W10.16mm.kicad_mod"),
    ("regular", 8, "DIP-8_W10.16mm.kicad_mod"),
    ("regular", 10, "DIP-10_W10.16mm.kicad_mod"),
    ("regular", 12, "DIP-12_W10.16mm.kicad_mod"),
    ("regular", 14, "DIP-14_W10.16mm.kicad_mod"),
    ("regular", 16, "DIP-16_W10.16mm.kicad_mod"),
    ("regular", 22, "DIP-22_W10.16mm.kicad_mod"),
    ("regular", 24, "DIP-24_W10.16mm.kicad_mod"),
    # wide (.600in / 15.24mm row spacing) -- N=24/28/40/48 come directly
    # from MS-011's own table, the rest are regression extrapolation.
    ("wide", 24, "DIP-24_W15.24mm.kicad_mod"),
    ("wide", 26, "DIP-26_W15.24mm.kicad_mod"),
    ("wide", 28, "DIP-28_W15.24mm.kicad_mod"),
    ("wide", 32, "DIP-32_W15.24mm.kicad_mod"),
    ("wide", 40, "DIP-40_W15.24mm.kicad_mod"),
    ("wide", 42, "DIP-42_W15.24mm.kicad_mod"),
    ("wide", 48, "DIP-48_W15.24mm.kicad_mod"),
    ("wide", 64, "DIP-64_W15.24mm.kicad_mod"),
]


@pytest.mark.parametrize("width_class,pin_count,filename", CASES)
def test_compare_against_real_dip_file(width_class, pin_count, filename):
    fp = dip.generate(width_class, pin_count, "N")
    real_text = open(f"{KICAD_DIP_DIR}/{filename}").read()

    deltas = compare.diff(fp, real_text)

    # Pitch and row spacing are both exact JEDEC Basic dimensions and
    # should match the real file exactly.
    assert abs(deltas["pitch_mm"]) < 0.01
    assert abs(deltas["row_spacing_mm"]) < 0.01
    # Drill/pad diameter and courtyard size are expected to deviate --
    # these bounds catch an implementation bug (wrong units, a
    # gross/order-of-magnitude mistake) without requiring an exact match
    # to KiCad's own conventions.
    assert abs(deltas["drill_mm"]) < 0.3
    assert abs(deltas["pad_diameter_mm"]) < 1.0
    assert abs(deltas["courtyard_width_mm"]) < 2.0
    assert abs(deltas["courtyard_height_mm"]) < 2.0
