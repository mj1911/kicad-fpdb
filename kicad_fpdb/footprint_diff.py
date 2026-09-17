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
- Pin-1 triangle points (QFN only): rounded to 0.01mm, compared as sets
  since winding order isn't guaranteed to match.
"""

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

# Known, pre-existing, unrelated gaps -- not something a caller's diff
# should report, since they're already tracked separately (see each
# entry's own reasoning in the regression suite this mirrors).
KNOWN_UNNUMBERED_PAD_GAPS = {"R-0201"}

NUMBERED_TOLERANCE_MM = 1e-4
UNNUMBERED_TOLERANCE_MM = 1e-2
RRATIO_TOLERANCE = 1e-2
TRIANGLE_ROUND_DP = 2


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

    if descriptor.split()[0] == "QFN":
        # Scoped to QFN only -- see kicad_fpdb.naming/pipeline's own pin-1
        # triangle work; other families (SOIC, SOT, LQFP) have real
        # triangle markers too but this project still draws a circle for
        # them, tracked separately, not a diff this tool should report.
        real_triangle = parse_silk_triangle(real_text)
        generated_triangle = parse_silk_triangle(generated)
        if real_triangle is None:
            diffs.append("real file has no pin-1 triangle marker (unexpected for QFN)")
        elif generated_triangle is None:
            diffs.append("missing pin-1 triangle marker")
        else:
            real_points = {(round(x, TRIANGLE_ROUND_DP), round(y, TRIANGLE_ROUND_DP)) for x, y in real_triangle}
            gen_points = {
                (round(x, TRIANGLE_ROUND_DP), round(y, TRIANGLE_ROUND_DP)) for x, y in generated_triangle
            }
            if gen_points != real_points:
                diffs.append(f"pin-1 triangle points: generated={gen_points} real={real_points}")

    return diffs
