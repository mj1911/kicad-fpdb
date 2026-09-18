"""JEDEC MS-001 (Issue D, "R-PDIP-T ... .300 INCH ROW SPACING") data,
transcribed directly from a copy of the document at docs/Ms-001d.pdf
(repo root `docs/`, gitignored -- JEDEC's document, not ours to
redistribute). Covers only the narrow (0.300in / 7.62mm) row-spacing DIP
family; see the design spec for why regular/wide aren't included yet.
"""

# e: lead pitch, Basic (theoretical exact) dimension, sheet 2 of 2.
PITCH_MM = 2.54  # 0.100in BSC

# eA: row spacing (pin-center-to-pin-center across the two rows), Basic.
ROW_SPACING_MM = 7.62  # 0.300in BSC

# E1: body width, nominal (min 0.240in, max 0.280in).
BODY_WIDTH_MM = 6.35  # 0.250in nominal

# b: lead width, maximum. Used as the effective lead "diameter" for
# round-hole sizing -- DIP leads are rectangular, and the drilled hole
# must clear the lead's largest cross-section dimension.
LEAD_WIDTH_MAX_MM = 0.559  # 0.022in max

# D: body length, nominal, by pin count (N). Full-lead-population
# variations AA-AG only, transcribed from the document's Variations
# table. There is no full-lead entry for N=8 -- it only appears under a
# "1/2 lead" (staggered) variation, a different lead-population style
# than the ordinary fully-populated 8-pin DIP -- see body_length_mm().
_BODY_LENGTH_TABLE_MM = {
    14: 19.05,
    16: 20.066,
    18: 22.86,
    20: 26.162,
    22: 29.337,
    24: 31.75,
    28: 35.687,
}


def _extrapolate_body_length_mm(table: dict[int, float], pin_count: int) -> float:
    """Linear least-squares fit of the table's own (N, D_nominal) pairs,
    evaluated at pin_count. MS-001's own D values are not perfectly
    linear in N (real DIP bodies come in a handful of standardized mold
    sizes, not one continuous formula), so this is an approximation used
    only for pin counts outside the table -- currently just N=8."""
    ns = list(table.keys())
    ds = list(table.values())
    n_mean = sum(ns) / len(ns)
    d_mean = sum(ds) / len(ds)
    sxy = sum((n - n_mean) * (d - d_mean) for n, d in zip(ns, ds))
    sxx = sum((n - n_mean) ** 2 for n in ns)
    slope = sxy / sxx
    intercept = d_mean - slope * n_mean
    return intercept + slope * pin_count


def body_length_mm(pin_count: int) -> float:
    if pin_count % 2 != 0 or pin_count < 4:
        raise ValueError(f"pin_count must be even and >= 4, got {pin_count}")
    if pin_count in _BODY_LENGTH_TABLE_MM:
        return _BODY_LENGTH_TABLE_MM[pin_count]
    return _extrapolate_body_length_mm(_BODY_LENGTH_TABLE_MM, pin_count)
