"""Verifies every known case (kicad_fpdb.reference_cases.CASES, or a
--family subset) against its real KiCad reference footprint, and prints a
human-readable report of any differences -- the same field-by-field
comparison tests/test_pipeline_regression.py uses (kicad_fpdb.footprint_diff
is the shared source of truth for both), but reporting every discrepancy
found per case instead of stopping at the first one, so this can be run
any time an investigation needs a full picture instead of pytest's
pass/fail output.

CLI usage:
    python -m kicad_fpdb.verify_library
        Verifies every case in CASES.

    python -m kicad_fpdb.verify_library --family LQFP QFN
        Verifies only cases whose descriptor's family head matches one of
        these (e.g. LQFP QFN).

Exits 0 if every checked case matches exactly (within the same tolerances
the regression suite uses), 1 if any case has at least one difference --
usable as a scriptable check, not just for reading by hand.
"""

import argparse
import os

from kicad_fpdb.footprint_diff import KNOWN_UNNUMBERED_PAD_GAPS, diff_footprint
from kicad_fpdb.pipeline import generate_footprint
from kicad_fpdb.reference_cases import CASES, FAMILY_TREE_PATH, KICAD_FOOTPRINTS
from kicad_fpdb.visual_compare import _descriptor_head


def verify_case(
    descriptor: str, reference_relpath: str,
    family_tree_path: str = FAMILY_TREE_PATH, kicad_footprints: str = KICAD_FOOTPRINTS,
) -> list[str]:
    """Returns the list of diffs for one case (empty means an exact
    match). Skips the unnumbered-pad comparison for descriptors in
    KNOWN_UNNUMBERED_PAD_GAPS, same as the regression suite -- those are
    pre-existing, unrelated gaps already tracked separately, not
    something this report should flag again on every run."""
    generated = generate_footprint(descriptor, family_tree_path, name="TEST")
    real_text = open(f"{kicad_footprints}/{reference_relpath}").read()
    return diff_footprint(descriptor, generated, real_text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--family", nargs="+", default=None,
        help="Only verify cases whose descriptor's family head matches one of these (e.g. LQFP QFN).",
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(KICAD_FOOTPRINTS):
        print(f"{KICAD_FOOTPRINTS} not present on this machine -- nothing to verify against.")
        return 1

    cases = CASES
    if args.family:
        families = set(args.family)
        cases = [(d, r) for d, r in CASES if _descriptor_head(d).split("-")[0] in families]

    mismatched = 0
    known_gap_skipped = 0
    for descriptor, reference_relpath in cases:
        if descriptor in KNOWN_UNNUMBERED_PAD_GAPS:
            known_gap_skipped += 1
        diffs = verify_case(descriptor, reference_relpath)
        if diffs:
            mismatched += 1
            print(f"{descriptor} ({reference_relpath}):")
            for diff in diffs:
                print(f"  {diff}")

    matched = len(cases) - mismatched
    print(f"\n{matched}/{len(cases)} cases match exactly.")
    if known_gap_skipped:
        print(f"({known_gap_skipped} of those skip the unnumbered-pad check: known pre-existing gap, see KNOWN_UNNUMBERED_PAD_GAPS.)")
    if mismatched:
        print(f"{mismatched} case(s) have differences -- see above.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
