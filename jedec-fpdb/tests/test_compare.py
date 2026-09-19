import os

import pytest

from jedec_fpdb import compare, dip
from jedec_fpdb.reference_cases import CASES, KICAD_DIP_DIR

pytestmark = pytest.mark.skipif(
    not os.path.isdir(KICAD_DIP_DIR),
    reason=f"{KICAD_DIP_DIR} not present on this machine",
)

# Drill/pad diameter tolerance is looser than pitch/row_spacing since real
# KiCad uses generous, round-number pad sizing -- 0.8mm drill / 1.6mm pad
# regardless of pin count or width class -- that noticeably exceeds even
# IPC-7251's own "Maximum" (Level A) density level; see the design spec.


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
