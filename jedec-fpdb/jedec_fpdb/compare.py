"""Diff a generated Footprint against a real KiCad DIP reference file.

Reads the real file directly from the filesystem (read-only) -- see the
design spec's Code sharing section for why this doesn't import
kicad-fpdb code, only a plain path string that happens to match where
kicad-fpdb's own tests look.

Both real files used in this project's own tests draw F.SilkS with
fp_line/fp_arc (never a single fp_rect) and F.CrtYd as exactly one plain
fp_rect, so the courtyard regex below assumes there is exactly one
fp_rect block in the file.
"""

import re
from dataclasses import dataclass

from jedec_fpdb.geometry import Footprint

_PAD_RE = re.compile(
    r'\(pad "(\d+)" thru_hole \w+\s*'
    r'\(at\s+([-\d.]+)\s+([-\d.]+)\)\s*'
    r'\(size\s+([-\d.]+)\s+([-\d.]+)\)\s*'
    r'\(drill\s+([-\d.]+)\)'
)

_CRTYD_RE = re.compile(
    r'\(fp_rect\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)'
    r'.*?\(layer "F\.CrtYd"\)',
    re.DOTALL,
)


@dataclass
class _Measurements:
    pitch_mm: float
    row_spacing_mm: float
    drill_mm: float
    pad_diameter_mm: float
    courtyard_width_mm: float
    courtyard_height_mm: float


def _measure_pads(pads: list[tuple[int, float, float, float, float]]) -> tuple[float, float, float, float]:
    """pads: list of (number, x_mm, y_mm, drill_or_size_w_mm, drill_mm).
    Returns (pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm)."""
    by_number = {p[0]: p for p in pads}
    pins_per_row = len(pads) // 2
    pad1 = by_number[1]
    pad2 = by_number[2]
    pad_right_first = by_number[pins_per_row + 1]

    pitch_mm = abs(pad2[2] - pad1[2])
    row_spacing_mm = abs(pad_right_first[1] - pad1[1])
    pad_diameter_mm = pad1[3]
    drill_mm = pad1[4]
    return pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm


def parse_real_dip(text: str) -> _Measurements:
    pads = []
    for m in _PAD_RE.finditer(text):
        number, x, y, w, _h, drill = m.groups()
        pads.append((int(number), float(x), float(y), float(w), float(drill)))
    if len(pads) < 4:
        raise ValueError(f"expected at least 4 pads, found {len(pads)}")

    pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm = _measure_pads(pads)

    crtyd_match = _CRTYD_RE.search(text)
    if crtyd_match is None:
        raise ValueError("no F.CrtYd fp_rect found")
    x1, y1, x2, y2 = (float(v) for v in crtyd_match.groups())

    return _Measurements(
        pitch_mm=pitch_mm,
        row_spacing_mm=row_spacing_mm,
        drill_mm=drill_mm,
        pad_diameter_mm=pad_diameter_mm,
        courtyard_width_mm=abs(x2 - x1),
        courtyard_height_mm=abs(y2 - y1),
    )


def _measure_generated(fp: Footprint) -> _Measurements:
    pads = [(p.number, p.x_mm, p.y_mm, p.diameter_mm, p.drill_mm) for p in fp.pads]
    pitch_mm, row_spacing_mm, drill_mm, pad_diameter_mm = _measure_pads(pads)

    c = fp.courtyard
    return _Measurements(
        pitch_mm=pitch_mm,
        row_spacing_mm=row_spacing_mm,
        drill_mm=drill_mm,
        pad_diameter_mm=pad_diameter_mm,
        courtyard_width_mm=abs(c.x2_mm - c.x1_mm),
        courtyard_height_mm=abs(c.y2_mm - c.y1_mm),
    )


def diff(generated: Footprint, real_text: str) -> dict[str, float]:
    g = _measure_generated(generated)
    r = parse_real_dip(real_text)
    return {
        "pitch_mm": g.pitch_mm - r.pitch_mm,
        "row_spacing_mm": g.row_spacing_mm - r.row_spacing_mm,
        "drill_mm": g.drill_mm - r.drill_mm,
        "pad_diameter_mm": g.pad_diameter_mm - r.pad_diameter_mm,
        "courtyard_width_mm": g.courtyard_width_mm - r.courtyard_width_mm,
        "courtyard_height_mm": g.courtyard_height_mm - r.courtyard_height_mm,
    }
