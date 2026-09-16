# tests/test_pipeline_regression.py
import os
import re

import pytest

from kicad_fpdb.pipeline import generate_footprint
from kicad_fpdb.reference_cases import CASES, FAMILY_TREE_PATH, KICAD_FOOTPRINTS

pytestmark = pytest.mark.skipif(
    not os.path.isdir(KICAD_FOOTPRINTS),
    reason=f"{KICAD_FOOTPRINTS} not present on this machine",
)

PAD_START = re.compile(r'\(pad "(\d+)" (\w+) (\w+)')
AT_PATTERN = re.compile(r"\(at ([-\d.]+) ([-\d.]+)\)")
SIZE_PATTERN = re.compile(r"\(size ([-\d.]+) ([-\d.]+)\)")
RRATIO_PATTERN = re.compile(r"\(roundrect_rratio ([-\d.]+)\)")


def _parse_pads(text: str) -> dict[str, dict]:
    starts = list(PAD_START.finditer(text))
    pads = {}
    for i, m in enumerate(starts):
        block_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[m.end():block_end]
        number, pad_type, shape = m.group(1), m.group(2), m.group(3)
        at_match = AT_PATTERN.search(block)
        size_match = SIZE_PATTERN.search(block)
        rratio_match = RRATIO_PATTERN.search(block)
        assert at_match is not None, number
        assert size_match is not None, number
        pads[number] = {
            "pad_type": pad_type,
            "shape": shape,
            "at": (float(at_match.group(1)), float(at_match.group(2))),
            "size": (float(size_match.group(1)), float(size_match.group(2))),
            "roundrect_rratio": float(rratio_match.group(1)) if rratio_match else None,
        }
    return pads


@pytest.mark.parametrize("descriptor,reference_relpath", CASES)
def test_pipeline_matches_real_footprint(descriptor, reference_relpath):
    generated = generate_footprint(descriptor, FAMILY_TREE_PATH, name="TEST")
    real_text = open(f"{KICAD_FOOTPRINTS}/{reference_relpath}").read()

    generated_pads = _parse_pads(generated)
    real_pads = _parse_pads(real_text)

    assert set(generated_pads.keys()) == set(real_pads.keys()), descriptor
    for number, real in real_pads.items():
        gen = generated_pads[number]
        rx, ry = real["at"]
        gx, gy = gen["at"]
        assert abs(gx - rx) < 1e-4, f"{descriptor} pad {number} x"
        assert abs(gy - ry) < 1e-4, f"{descriptor} pad {number} y"

        assert gen["pad_type"] == real["pad_type"], f"{descriptor} pad {number} pad_type"
        assert gen["shape"] == real["shape"], f"{descriptor} pad {number} shape"

        rsx, rsy = real["size"]
        gsx, gsy = gen["size"]
        assert abs(gsx - rsx) < 1e-4, f"{descriptor} pad {number} size x"
        assert abs(gsy - rsy) < 1e-4, f"{descriptor} pad {number} size y"

        real_rratio = real["roundrect_rratio"]
        gen_rratio = gen["roundrect_rratio"]
        if real_rratio is None or gen_rratio is None:
            assert real_rratio == gen_rratio, f"{descriptor} pad {number} roundrect_rratio presence"
        else:
            # Looser tolerance than position/size: KiCad's own generator
            # clamps corner radius to an absolute maximum on some parts
            # (e.g. R-0805), which shifts the *ratio* slightly away from
            # the nominal 0.25 without indicating a generator bug here.
            assert abs(gen_rratio - real_rratio) < 1e-2, f"{descriptor} pad {number} roundrect_rratio"
