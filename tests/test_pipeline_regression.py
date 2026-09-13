import re

import pytest

from kicad_fpdb.pipeline import generate_footprint

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"
KICAD_FOOTPRINTS = "/usr/share/kicad/footprints"


def _parse_real_pads(path: str) -> dict[str, tuple[float, float]]:
    """Extracts {pad_number: (x, y)} from a real .kicad_mod file."""
    text = open(path).read()
    pads = {}
    for match in re.finditer(r'\(pad "(\d+)" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)', text):
        number, x, y = match.groups()
        pads[number] = (float(x), float(y))
    return pads


def test_dip16_pipeline_matches_real_footprint():
    generated = generate_footprint("DIP-16", FAMILY_TREE_PATH, name="DIP-16_TEST")
    real_pads = _parse_real_pads(f"{KICAD_FOOTPRINTS}/Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod")

    generated_pads = {}
    for match in re.finditer(r'\(pad "(\d+)" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)', generated):
        number, x, y = match.groups()
        generated_pads[number] = (float(x), float(y))

    assert set(generated_pads.keys()) == set(real_pads.keys())
    for number, (rx, ry) in real_pads.items():
        gx, gy = generated_pads[number]
        assert abs(gx - rx) < 1e-4
        assert abs(gy - ry) < 1e-4
