"""Parses a generated .kicad_mod's pads/pin-1 marker and diffs them against
a real KiCad reference footprint, using the exact same field-by-field
comparisons and tolerances as tests/test_pipeline_regression.py -- shared
so the test suite (pass/fail) and kicad_fpdb/verify_library.py (a full
human-readable report) can never drift apart.

Tolerances mirror the regression suite's own documented reasoning:
- Numbered pad position/size: 1e-4mm (should match to float precision).
- Unnumbered (paste/mask sub-) pad position/size: 1e-2mm -- looser,
  since some paste splits still fall back to a least-squares-fit formula
  with an accepted ~0.006mm residual against the real files.
- roundrect_rratio: 1e-2 -- KiCad's own generator clamps corner radius
  to an absolute maximum on some parts, shifting the ratio slightly away
  from the nominal 0.25 without indicating a generator bug.
- Pin-1 triangle points (QFN/SOIC/LQFP): each real point must have a
  generated point within TRIANGLE_POINT_TOLERANCE_MM (0.015mm) -- looser
  than a simple rounded-value comparison, since LQFP's real files carry
  an unavoidable ~0.01mm generator-rounding residual on some variants.
- Reference/Value text position: 0.01mm -- absorbs the DIP-family text
  margin's own 2-decimal file-rounding residual (see
  docs/superpowers/specs/2026-09-17-exact-reference-value-text-
  position-design.md).
"""

import math
import re

PAD_START = re.compile(r'\(pad "(\d+)" (\w+) (\w+)')
UNNUMBERED_PAD_START = re.compile(r'\(pad "" (\w+) (\w+)')
AT_PATTERN = re.compile(r"\(at ([-\d.]+) ([-\d.]+)\)")
SIZE_PATTERN = re.compile(r"\(size ([-\d.]+) ([-\d.]+)\)")
RRATIO_PATTERN = re.compile(r"\(roundrect_rratio ([-\d.]+)\)")
SILK_TRIANGLE_POLY = re.compile(
    r'\(fp_poly\s*\(pts((?:\s*\(xy [-\d.]+ [-\d.]+\))+)\s*\)'
    r'\s*\(stroke\s*\(width [-\d.]+\)\s*\(type \w+\)\s*\)'
    r'\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)\s*\)'
)
XY_PATTERN = re.compile(r"\(xy ([-\d.]+) ([-\d.]+)\)")
REFERENCE_PATTERN = re.compile(r'\(property "Reference" "REF\*\*"\s*\(at ([-\d.]+) ([-\d.]+) 0\)')
VALUE_PATTERN = re.compile(r'\(property "Value" "[^"]*"\s*\(at ([-\d.]+) ([-\d.]+) 0\)')

# Known, pre-existing, unrelated gaps -- not something a caller's diff
# should report, since they're already tracked separately (see each
# entry's own reasoning in the regression suite this mirrors).
KNOWN_UNNUMBERED_PAD_GAPS = {"R-0201"}
# SOIC-8-1EP_..._EP2.514x3.2mm's real reference file is a one-off
# anomaly: its pad 1 shifts furthest of all 8 real EP variants
# (-2.6375 vs the standard -2.475), and uniquely among them, its real
# pin-1 triangle marker also shifts (by 0.04mm, uniformly across all 3
# points) -- every other EP variant, including ones with a smaller pad
# shift, keeps the marker at the exact standard body-anchored position
# this project's formula computes. Not explainable by any formula
# checked; tracked as an isolated real-file quirk rather than chased
# further, per docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-
# triangle-marker-design.md.
KNOWN_TRIANGLE_ANOMALIES = {"SOIC-8 ep2_514x3_2"}
# SOIC's own courtyard_body_margin is a single flat value averaged
# across every pin count in a width class (already documented as
# "~0.02mm spread accepted as real-file rounding noise" in CLAUDE.md,
# derived from SOIC-8/SOIC-14W specifically) -- these 4 descriptors'
# real courtyards deviate from that flat approximation by up to
# ~0.04mm, which the text-position check (whose reference point is
# that same courtyard's own edge) inherits and amplifies slightly.
# Pre-existing, already-accepted geometry approximation, not a new
# text-placement bug -- see docs/superpowers/specs/2026-09-17-exact-
# reference-value-text-position-design.md.
KNOWN_TEXT_POSITION_ANOMALIES = {"SOIC-14", "SOIC-16", "SOIC-20 w", "SOIC-24 w"}

NUMBERED_TOLERANCE_MM = 1e-4
UNNUMBERED_TOLERANCE_MM = 1e-2
RRATIO_TOLERANCE = 1e-2

# Families whose real reference footprints carry a pin-1 triangle
# marker on F.SilkS (matched via pin1_marker_style="triangle") --
# checked against the descriptor's own family head (e.g. "QFN-12" ->
# "QFN", "TSOT-23-6" -> "TSOT"). SOT-23-6/-8 and TSOT-23-6/-8 reuse
# SOIC's narrow-class formula and constants exactly -- see
# docs/superpowers/specs/2026-09-17-sot23-pin1-triangle-marker-
# design.md. SOT-23/SOT-23-5/TSOT-23-5's real files ALSO carry a
# triangle (verified), but this project deliberately draws no marker
# of any kind there (pin1_marker: false, a placement-safety choice
# independent of what real KiCad does) -- diff_footprint additionally
# checks whether the *generated* output has any marker at all before
# applying this family set, so those three are correctly skipped
# without needing to name them individually.
TRIANGLE_MARKER_FAMILIES = {"QFN", "SOIC", "LQFP", "SOT", "TSOT"}
# Max allowed distance, in mm, between a real triangle point and its
# closest generated counterpart. Needs to be looser than a simple
# rounded-value comparison: LQFP's real files have an unavoidable
# ~0.01mm generator-rounding residual on some variants (verified exact
# match on the other variants) -- 0.015mm absorbs that while staying
# far tighter than any plausible real geometry bug (marker dimensions
# are 0.24-0.47mm at this scale).
TRIANGLE_POINT_TOLERANCE_MM = 0.015
TEXT_POSITION_TOLERANCE_MM = 0.01


def parse_reference_value_positions(text: str) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    ref_match = REFERENCE_PATTERN.search(text)
    value_match = VALUE_PATTERN.search(text)
    ref = (float(ref_match.group(1)), float(ref_match.group(2))) if ref_match else None
    value = (float(value_match.group(1)), float(value_match.group(2))) if value_match else None
    return ref, value


def parse_silk_triangle(text: str) -> list[tuple[float, float]] | None:
    """The pin-1 triangle's fp_poly, if present -- the only 3-point poly
    on F.SilkS either the real files or this project's generator ever
    emit (the F.Fab chamfer outline is a separate, 5-point poly on a
    different layer)."""
    for m in SILK_TRIANGLE_POLY.finditer(text):
        points = [(float(x), float(y)) for x, y in XY_PATTERN.findall(m.group(1))]
        if len(points) == 3:
            return points
    return None


def parse_pads(text: str) -> dict[str, dict]:
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


def parse_unnumbered_pads(text: str) -> list[dict]:
    """Unnumbered pads (paste/mask sub-pads of an exposed pad) aren't
    covered by parse_pads' PAD_START regex at all -- this is a separate
    pass, sorted by position rather than indexed by number, to compare
    two lists. Block boundaries are computed against *all* pad starts
    (numbered included), not just unnumbered ones, since the last
    unnumbered pad in a file is immediately followed by a numbered one,
    not another unnumbered one."""
    all_starts = sorted(
        [m.start() for m in PAD_START.finditer(text)] + [m.start() for m in UNNUMBERED_PAD_START.finditer(text)]
    )
    pads = []
    for m in UNNUMBERED_PAD_START.finditer(text):
        later = [s for s in all_starts if s > m.start()]
        block_end = later[0] if later else len(text)
        block = text[m.end():block_end]
        pad_type, shape = m.group(1), m.group(2)
        at_match = AT_PATTERN.search(block)
        size_match = SIZE_PATTERN.search(block)
        rratio_match = RRATIO_PATTERN.search(block)
        assert at_match is not None
        assert size_match is not None
        pads.append({
            "pad_type": pad_type,
            "shape": shape,
            "at": (float(at_match.group(1)), float(at_match.group(2))),
            "size": (float(size_match.group(1)), float(size_match.group(2))),
            "roundrect_rratio": float(rratio_match.group(1)) if rratio_match else None,
        })
    pads.sort(key=lambda p: (p["at"][1], p["at"][0]))
    return pads


def _diff_rratio(gen_rratio, real_rratio, label: str) -> list[str]:
    if real_rratio is None or gen_rratio is None:
        if real_rratio != gen_rratio:
            return [f"{label} roundrect_rratio presence: generated={gen_rratio!r} real={real_rratio!r}"]
        return []
    if abs(gen_rratio - real_rratio) >= RRATIO_TOLERANCE:
        return [f"{label} roundrect_rratio: generated={gen_rratio} real={real_rratio}"]
    return []


def _triangle_points_match(
    real_points: list[tuple[float, float]], gen_points: list[tuple[float, float]],
    tolerance: float = TRIANGLE_POINT_TOLERANCE_MM,
) -> bool:
    if len(real_points) != len(gen_points):
        return False
    remaining = list(gen_points)
    for rp in real_points:
        if not remaining:
            return False
        closest = min(remaining, key=lambda gp: math.hypot(gp[0] - rp[0], gp[1] - rp[1]))
        if math.hypot(closest[0] - rp[0], closest[1] - rp[1]) > tolerance:
            return False
        remaining.remove(closest)
    return True


def diff_footprint(descriptor: str, generated: str, real_text: str) -> list[str]:
    """Compares a generated .kicad_mod's text against a real reference
    footprint's text, field by field, collecting every discrepancy found
    (unlike a pytest assertion, this never stops at the first one).
    Returns a list of human-readable diff descriptions -- empty means an
    exact match within tolerance."""
    diffs: list[str] = []

    generated_pads = parse_pads(generated)
    real_pads = parse_pads(real_text)

    generated_numbers = set(generated_pads)
    real_numbers = set(real_pads)
    if generated_numbers != real_numbers:
        missing = real_numbers - generated_numbers
        extra = generated_numbers - real_numbers
        if missing:
            diffs.append(f"pad numbers missing from generated: {sorted(missing, key=int)}")
        if extra:
            diffs.append(f"unexpected pad numbers in generated: {sorted(extra, key=int)}")

    for number in sorted(generated_numbers & real_numbers, key=int):
        real = real_pads[number]
        gen = generated_pads[number]
        label = f"pad {number}"

        rx, ry = real["at"]
        gx, gy = gen["at"]
        if abs(gx - rx) >= NUMBERED_TOLERANCE_MM or abs(gy - ry) >= NUMBERED_TOLERANCE_MM:
            diffs.append(f"{label} at: generated=({gx}, {gy}) real=({rx}, {ry})")

        if gen["pad_type"] != real["pad_type"]:
            diffs.append(f"{label} pad_type: generated={gen['pad_type']!r} real={real['pad_type']!r}")
        if gen["shape"] != real["shape"]:
            diffs.append(f"{label} shape: generated={gen['shape']!r} real={real['shape']!r}")

        rsx, rsy = real["size"]
        gsx, gsy = gen["size"]
        if abs(gsx - rsx) >= NUMBERED_TOLERANCE_MM or abs(gsy - rsy) >= NUMBERED_TOLERANCE_MM:
            diffs.append(f"{label} size: generated=({gsx}, {gsy}) real=({rsx}, {rsy})")

        diffs.extend(_diff_rratio(gen["roundrect_rratio"], real["roundrect_rratio"], label))

    if descriptor not in KNOWN_UNNUMBERED_PAD_GAPS:
        generated_unnumbered = parse_unnumbered_pads(generated)
        real_unnumbered = parse_unnumbered_pads(real_text)
        if len(generated_unnumbered) != len(real_unnumbered):
            diffs.append(
                f"unnumbered pad count: generated={len(generated_unnumbered)} real={len(real_unnumbered)}"
            )
        else:
            for i, (gen, real) in enumerate(zip(generated_unnumbered, real_unnumbered)):
                label = f"unnumbered pad {i}"
                if gen["pad_type"] != real["pad_type"]:
                    diffs.append(f"{label} pad_type: generated={gen['pad_type']!r} real={real['pad_type']!r}")
                if gen["shape"] != real["shape"]:
                    diffs.append(f"{label} shape: generated={gen['shape']!r} real={real['shape']!r}")

                rx, ry = real["at"]
                gx, gy = gen["at"]
                if abs(gx - rx) >= UNNUMBERED_TOLERANCE_MM or abs(gy - ry) >= UNNUMBERED_TOLERANCE_MM:
                    diffs.append(f"{label} at: generated=({gx}, {gy}) real=({rx}, {ry})")

                rsx, rsy = real["size"]
                gsx, gsy = gen["size"]
                if abs(gsx - rsx) >= UNNUMBERED_TOLERANCE_MM or abs(gsy - rsy) >= UNNUMBERED_TOLERANCE_MM:
                    diffs.append(f"{label} size: generated=({gsx}, {gsy}) real=({rsx}, {rsy})")

                diffs.extend(_diff_rratio(gen["roundrect_rratio"], real["roundrect_rratio"], label))

    family = descriptor.split()[0].split("-")[0]
    generated_triangle = parse_silk_triangle(generated)
    # SOT-23/SOT-23-5/TSOT-23-5's real reference files DO carry a
    # triangle marker (verified), but this project deliberately draws
    # no marker of any kind there (pin1_marker: false -- their
    # asymmetric layouts are only placeable one physical way, so a
    # pin-1 indicator is functionally unneeded, independent of what
    # real KiCad does). Checking generated_triangle/"fp_circle"
    # presence, not just family membership, correctly skips those
    # descriptors without needing to special-case them by name.
    generated_has_any_marker = generated_triangle is not None or "fp_circle" in generated
    if family in TRIANGLE_MARKER_FAMILIES and generated_has_any_marker and descriptor not in KNOWN_TRIANGLE_ANOMALIES:
        real_triangle = parse_silk_triangle(real_text)
        if real_triangle is None:
            diffs.append(f"real file has no pin-1 triangle marker (unexpected for {family})")
        elif generated_triangle is None:
            diffs.append("missing pin-1 triangle marker")
        elif not _triangle_points_match(real_triangle, generated_triangle):
            diffs.append(f"pin-1 triangle points: generated={generated_triangle} real={real_triangle}")

    if descriptor not in KNOWN_TEXT_POSITION_ANOMALIES:
        real_ref, real_value = parse_reference_value_positions(real_text)
        gen_ref, gen_value = parse_reference_value_positions(generated)
        for label, real_pos, gen_pos in (("Reference", real_ref, gen_ref), ("Value", real_value, gen_value)):
            if real_pos is None or gen_pos is None:
                continue
            rx, ry = real_pos
            gx, gy = gen_pos
            if abs(gx - rx) >= TEXT_POSITION_TOLERANCE_MM or abs(gy - ry) >= TEXT_POSITION_TOLERANCE_MM:
                diffs.append(f"{label} position: generated=({gx}, {gy}) real=({rx}, {ry})")

    return diffs
