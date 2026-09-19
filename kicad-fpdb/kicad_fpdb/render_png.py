"""Renders every known case (or a chosen subset) as a single flat PNG per
case, generated footprint next to its real KiCad reference, for quick
visual review without opening a browser.

CLI usage:
    python -m kicad_fpdb.render_png
        Renders every case in kicad_fpdb.reference_cases.CASES.

    python -m kicad_fpdb.render_png --family LQFP QFN
        Renders only cases whose descriptor starts with one of the given
        family names (matching the same "FAMILY-VARIANT ..." head
        kicad_fpdb.naming/visual_compare use elsewhere).

Renders up to --jobs cases in parallel via a thread pool (default: 12).
Each case is an independent kicad-cli/rsvg-convert subprocess pair with no
shared state, so this scales cleanly (measured ~2.8x on a 4-core machine
at -j 8 -- kicad-cli itself is CPU-bound, so gains cap out around the
core count rather than the job count). Pass -j 1 to force serial.

Writes <output-dir>/<case_name>.png for each case (default: renders_png/).
"""

import argparse
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from kicad_fpdb.reference_cases import CASES, FAMILY_TREE_PATH, KICAD_FOOTPRINTS
from kicad_fpdb.visual_compare import _default_case_name, _descriptor_head, render_comparison

# Pixels per millimeter, matching visual_compare.PX_PER_MM so a PNG here
# and a review.html panel show a case at the same physical scale.
PX_PER_MM = 20.0
# rsvg-convert takes DPI, not px/mm directly -- 1 inch = 25.4mm.
_DPI = PX_PER_MM * 25.4

# Gap, in px, drawn between the generated and reference panels.
PANEL_GAP_PX = 20

DEFAULT_OUTPUT_DIR = "renders_png"


def _svg_to_png(svg_path: Path, png_path: Path) -> None:
    # White background: real KiCad's own SVG export draws silkscreen and
    # outline strokes in black (see CLAUDE.md's visual-review-tool notes),
    # invisible against a dark or transparent background.
    result = subprocess.run(
        [
            "rsvg-convert", "-d", str(_DPI), "-p", str(_DPI),
            "-b", "white", str(svg_path), "-o", str(png_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"rsvg-convert failed for {svg_path}: {result.stderr}")


def _compose_side_by_side(generated_png: Path, reference_png: Path, output_path: Path) -> None:
    generated = Image.open(generated_png)
    reference = Image.open(reference_png)
    width = generated.width + PANEL_GAP_PX + reference.width
    height = max(generated.height, reference.height)
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(generated, (0, (height - generated.height) // 2))
    canvas.paste(reference, (generated.width + PANEL_GAP_PX, (height - reference.height) // 2))
    canvas.save(output_path)


def render_case_png(
    descriptor: str,
    reference_relpath: str,
    output_dir: str,
    family_tree_path: str = FAMILY_TREE_PATH,
    kicad_footprints: str = KICAD_FOOTPRINTS,
) -> Path:
    """Renders one case (generated | reference, side by side) to a PNG in
    output_dir, named after the descriptor. Returns the PNG's path."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    case_name = _default_case_name(descriptor)
    reference_path = f"{kicad_footprints}/{reference_relpath}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        generated_svg, reference_svg = render_comparison(
            descriptor, reference_path, str(tmp_path), name=case_name,
            footprint_name=_descriptor_head(descriptor), family_tree_path=family_tree_path,
        )
        generated_png = tmp_path / f"{case_name}_generated.png"
        reference_png = tmp_path / f"{case_name}_reference.png"
        _svg_to_png(generated_svg, generated_png)
        _svg_to_png(reference_svg, reference_png)

        png_path = output_path / f"{case_name}.png"
        _compose_side_by_side(generated_png, reference_png, png_path)

    return png_path


def render_cases(
    cases: list[tuple[str, str]],
    output_dir: str,
    family_tree_path: str = FAMILY_TREE_PATH,
    kicad_footprints: str = KICAD_FOOTPRINTS,
    jobs: int = 1,
) -> list[Path]:
    # Each case renders in its own temp dir via render_case_png, so there's
    # no shared state between them -- and the work here is almost entirely
    # kicad-cli/rsvg-convert subprocess calls, which release the GIL while
    # running, so a thread pool parallelizes cleanly with no extra locking.
    if jobs == 1:
        return [
            render_case_png(descriptor, relpath, output_dir, family_tree_path, kicad_footprints)
            for descriptor, relpath in cases
        ]
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(
                render_case_png, descriptor, relpath, output_dir, family_tree_path, kicad_footprints,
            )
            for descriptor, relpath in cases
        ]
        return [future.result() for future in futures]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--family", nargs="+", default=None,
        help="Only render cases whose descriptor's family head matches one of these (e.g. LQFP QFN).",
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=12,
        help="Render this many cases in parallel (each is an independent kicad-cli/rsvg-convert subprocess pair). Default: 12.",
    )
    args = parser.parse_args(argv)

    cases = CASES
    if args.family:
        families = set(args.family)
        cases = [(d, r) for d, r in CASES if _descriptor_head(d).split("-")[0] in families]

    paths = render_cases(cases, args.output_dir, jobs=args.jobs)
    print(f"Wrote {len(paths)} PNG(s) to {args.output_dir}/")


if __name__ == "__main__":
    main()
