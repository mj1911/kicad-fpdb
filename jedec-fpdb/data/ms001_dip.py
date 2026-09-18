"""JEDEC MS-001 (narrow, .300in row spacing), MS-010 (regular, .400in row
spacing), and MS-011 (wide, .600in row spacing) DIP outline data,
transcribed from real copies of those documents in `jedec-fpdb/JEDEC/`
(gitignored -- JEDEC's documents, not ours to redistribute):
  - MS-001 Issue D, "R-PDIP-T ... .300 INCH ROW SPACING"
  - MS-010 Issue C, "... .400 INCH ROW SPACING" (this copy documents only
    the AA-AD variations, N=22/24/28/32 -- an addendum, not the full base
    standard; see body_length_mm())
  - MS-011 Issue B, "... .600 INCH ROW SPACING [PLASTIC]" (this copy
    documents only the AA-AD variations, N=24/28/40/48 -- likewise an
    addendum)

All mm constants below are computed from the document's own inch values
via `_in()` rather than hand-rounded, so each is exact to the source
digit -- see feedback memory on this (a prior hand-computed conversion,
LEAD_WIDTH_MAX_MM, had been mistakenly rounded to 3 decimals, 0.559mm
instead of the exact 0.5588mm).
"""

from dataclasses import dataclass, field

MM_PER_INCH = 25.4


def _in(inches: float) -> float:
    """Exact inch -> mm conversion (25.4mm/inch is a defined exact
    ratio) -- use this instead of hand-computing and typing a rounded
    mm literal."""
    return inches * MM_PER_INCH


# e: lead pitch, Basic (theoretical exact) dimension, sheet 2 of 2. Same
# across all three width classes (confirmed in each document's own table).
PITCH_MM = _in(0.100)  # 0.100in BSC

# b: lead width, maximum. Used as the effective lead "diameter" for
# round-hole sizing -- DIP leads are rectangular, and the drilled hole
# must clear the lead's largest cross-section dimension. Same across all
# three width classes (confirmed in each document's own table).
LEAD_WIDTH_MAX_MM = _in(0.022)  # 0.022in max


@dataclass(frozen=True)
class _WidthClass:
    # eA: row spacing (pin-center-to-pin-center across the two rows), Basic.
    row_spacing_mm: float
    # E1: body width, nominal.
    body_width_mm: float
    # D: body length, nominal, by pin count (N). Only the pin counts the
    # source document actually lists -- see body_length_mm() for how
    # other pin counts are handled.
    body_length_table_mm: dict = field(default_factory=dict)


_WIDTH_CLASSES = {
    # MS-001 Issue D. E1 min/nom/max = .240/.250/.280in. D table: full-lead
    # variations AA-AG (N=14..28) transcribed from the document's own
    # Variations table; there is no full-lead N=8 entry (see
    # body_length_mm()).
    "narrow": _WidthClass(
        row_spacing_mm=_in(0.300),
        body_width_mm=_in(0.250),
        body_length_table_mm={
            14: _in(0.750),
            16: _in(0.790),
            18: _in(0.900),
            20: _in(1.030),
            22: _in(1.155),
            24: _in(1.250),
            28: _in(1.405),
        },
    ),
    # MS-010 Issue C. E1 min/nom/max = .330/.360/.390in. eA is documented
    # as .400in REF (not BSC, unlike narrow/wide) -- doesn't change the
    # numeric value used here, just its tolerancing semantics, which this
    # project doesn't model. D table: this copy only documents variations
    # AA-AD (N=22/24/28/32) -- a perfectly linear D-vs-N relationship
    # (slope exactly half the lead pitch), which makes extrapolating
    # outside this range low-risk relative to narrow's noisier table.
    "regular": _WidthClass(
        row_spacing_mm=_in(0.400),
        body_width_mm=_in(0.360),
        body_length_table_mm={
            22: _in(1.085),
            24: _in(1.185),
            28: _in(1.385),
            32: _in(1.585),
        },
    ),
    # MS-011 Issue B. E1 has no NOM column (only min/max: .485/.580in) --
    # uses the midpoint. D likewise has no NOM column; this copy only
    # documents variations AA-AD (N=24/28/40/48), each given directly as
    # an already-converted mm range (this document publishes both an
    # inch and an mm table) -- midpoint used the same way, not re-derived
    # via _in() since the mm values are the document's own, not ours to
    # convert.
    "wide": _WidthClass(
        row_spacing_mm=_in(0.600),
        body_width_mm=(_in(0.485) + _in(0.580)) / 2,
        body_length_table_mm={
            24: (29.3 + 32.7) / 2,
            28: (35.1 + 39.7) / 2,
            40: (50.3 + 53.2) / 2,
            48: (60.7 + 63.1) / 2,
        },
    ),
}

SUPPORTED_WIDTH_CLASSES = tuple(_WIDTH_CLASSES.keys())


def _check_width_class(width_class: str) -> _WidthClass:
    if width_class not in _WIDTH_CLASSES:
        raise ValueError(
            f"unsupported width_class {width_class!r}, expected one of {SUPPORTED_WIDTH_CLASSES}"
        )
    return _WIDTH_CLASSES[width_class]


def row_spacing_mm(width_class: str) -> float:
    return _check_width_class(width_class).row_spacing_mm


def body_width_mm(width_class: str) -> float:
    return _check_width_class(width_class).body_width_mm


def _extrapolate_body_length_mm(table: dict[int, float], pin_count: int) -> float:
    """Linear least-squares fit of the table's own (N, D_nominal) pairs,
    evaluated at pin_count. Real DIP bodies come in a handful of
    standardized mold sizes rather than one continuous formula, so this
    is an approximation used only for pin counts outside the table."""
    ns = list(table.keys())
    ds = list(table.values())
    n_mean = sum(ns) / len(ns)
    d_mean = sum(ds) / len(ds)
    sxy = sum((n - n_mean) * (d - d_mean) for n, d in zip(ns, ds))
    sxx = sum((n - n_mean) ** 2 for n in ns)
    slope = sxy / sxx
    intercept = d_mean - slope * n_mean
    return intercept + slope * pin_count


def body_length_mm(width_class: str, pin_count: int) -> float:
    wc = _check_width_class(width_class)
    if pin_count % 2 != 0 or pin_count < 4:
        raise ValueError(f"pin_count must be even and >= 4, got {pin_count}")
    if pin_count in wc.body_length_table_mm:
        return wc.body_length_table_mm[pin_count]
    return _extrapolate_body_length_mm(wc.body_length_table_mm, pin_count)
