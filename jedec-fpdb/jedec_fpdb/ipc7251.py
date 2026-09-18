"""IPC-7251 ("Generic Requirements for Through-Hole Design and Land
Pattern Standard") thru-hole land pattern sizing, transcribed directly
from Table 3-5 ("Dual In-Line Packages") of a copy of the document at
docs/IPC-7251-req-for-Through-Hole-Designs.pdf (repo root `docs/`,
gitignored -- IPC's document, not ours to redistribute).

Density level is one of "M" (Most material condition / Table 3-5's
"Maximum Level A", the most generous -- easiest to assemble/rework),
"N" (Nominal / Level B), or "L" (Least material condition / Level C,
the tightest -- highest density).
"""

import math

_DENSITY_LEVELS = ("M", "N", "L")

# Table 3-5, "Hole Diameter Factor" ("Max Lead dia. plus value"): hole
# diameter = max lead diameter + this factor.
_HOLE_DIAMETER_FACTOR_MM = {"M": 0.25, "N": 0.20, "L": 0.15}

# Table 3-5, "Int. & Ext. Annular ring Excess (added to hole dia.)":
# pad diameter = hole diameter + this value, added directly to the
# diameter (Table 3-5's own wording), not doubled as a per-side value.
_ANNULAR_RING_EXCESS_MM = {"M": 0.50, "N": 0.35, "L": 0.30}

# Table 3-5, "Courtyard Excess from Component body and/or lands"
# ("Which ever is greater" of the component-body or pad-derived
# bounding box -- see dip.py, which does that max() before adding this).
_COURTYARD_EXCESS_MM = {"M": 0.5, "N": 0.25, "L": 0.1}


def _check_density(density: str) -> None:
    if density not in _DENSITY_LEVELS:
        raise ValueError(
            f"unknown density level {density!r}, expected one of {_DENSITY_LEVELS}"
        )


def drill_diameter_mm(lead_diameter_mm: float, density: str) -> float:
    _check_density(density)
    return lead_diameter_mm + _HOLE_DIAMETER_FACTOR_MM[density]


def pad_diameter_mm(lead_diameter_mm: float, density: str) -> float:
    _check_density(density)
    return drill_diameter_mm(lead_diameter_mm, density) + _ANNULAR_RING_EXCESS_MM[density]


def courtyard_excess_mm(density: str) -> float:
    _check_density(density)
    return _COURTYARD_EXCESS_MM[density]


def round_up_to_0_1mm(value_mm: float) -> float:
    """Table 3-5's "Courtyard Round-off factor": round up to the nearest
    0.10mm (e.g. 1.00, 1.10, 1.20, ..., always rounding up, never down),
    applied to the courtyard's own final width/height."""
    return math.ceil(value_mm * 10 - 1e-9) / 10
