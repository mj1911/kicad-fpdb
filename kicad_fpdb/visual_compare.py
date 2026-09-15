"""Renders generated footprints next to their real KiCad references for
visual, human review, and builds a self-contained local HTML page to cycle
through the pairs and mark each one pass/fail.

CLI usage:
    python -m kicad_fpdb.visual_compare
        Renders all known cases from kicad_fpdb.reference_cases.

    python -m kicad_fpdb.visual_compare --descriptor "DIP-16 r" \\
        --reference /path/to/real.kicad_mod --name my_case
        Renders one ad-hoc case.

Either invocation writes <name>_generated.svg / <name>_reference.svg plus a
review.html into --output-dir (default: renders/).
"""

import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

# Pixels per millimeter used when embedding SVGs in the review page. Both
# panels for a case are scaled by this same constant (rather than each
# being independently resized to fit its container) so a real physical
# size difference between the generated and reference footprint stays
# visible instead of being scaled away.
PX_PER_MM = 20.0

# Checkerboard square size, in mm, drawn behind each panel as a scale
# reference — fine enough to act as a ruler without overpowering the
# footprint geometry drawn on top of it.
CHECKER_MM = 0.5
CHECKER_PX = PX_PER_MM * CHECKER_MM

# Dot-grid pitch, in mm, drawn on top of the checkerboard as a second scale
# reference at standard 0.1in (2.54mm) perfboard/breadboard spacing.
DOT_GRID_MM = 0.1 * 25.4
DOT_GRID_PX = PX_PER_MM * DOT_GRID_MM

_SVG_ROOT_SIZE = re.compile(r'width="([\d.]+)mm" height="([\d.]+)mm"')
_SVG_ROOT_VIEWBOX = re.compile(
    r'width="([\d.]+)mm" height="([\d.]+)mm" viewBox="([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)"'
)
_SVG_PX_SIZE = re.compile(r'width="([\d.]+)" height="([\d.]+)"')

# kicad-cli's exported viewBox exactly wraps each footprint's path
# *centerlines*, with no allowance for stroke width. A hairline courtyard
# line sitting exactly on that boundary (common now that a stepped
# courtyard's own arm is often the single widest feature) has its outer
# half fall outside the viewBox and get clipped by the SVG viewport's
# default overflow:hidden — invisible at the ~1px stroke width this tool
# renders at. Padding only the far (width/height) edge, not the origin,
# fixes this without disturbing _pad1_frame_position_px's assumption that
# every viewBox origin is exactly 0,0.
SVG_VIEWBOX_PAD_MM = 0.1

# kicad-cli's default theme fills F.Cu copper (pads) with this exact color —
# verified across every reference/generated SVG this tool produces. Pads are
# the only filled shapes using it, and kicad-cli plots them in a footprint's
# own pad-declaration order, so the first #C83434 shape in document order is
# always pad "1" for every case in kicad_fpdb.reference_cases (each lists
# pad "1" first in its .kicad_mod, the near-universal KiCad convention).
_PAD1_PATH = re.compile(r'<path style="fill:#C83434[^"]*"\s*d="([^"]+)"', re.DOTALL)
_PAD1_CIRCLE = re.compile(r'<g style="fill:#C83434[^"]*">\s*<circle cx="(-?[\d.]+)" cy="(-?[\d.]+)"')
_COORD_PAIR = re.compile(r'(-?[\d.]+),(-?[\d.]+)')

# Grid frame size, in px — both panels render into a fixed square box (per
# CLAUDE.md's documented review-viewer design) so a background-position
# computed from one panel lines up identically in the other.
FRAME_PX = 500.0

# kicad-cli's --sketch-pads-on-fab-layers draws each pad's number early in
# the SVG, then draws drill-hole circles for through-hole pads afterward —
# opaque and centered on the same point, so they paint over the number
# regardless of which --layers are requested. Moving these groups to the
# very end of the document keeps them on top of everything else. Each
# stroked-text group carries no color/width of its own — it inherits from
# the enclosing <g style="..."> that also holds its (invisible, for
# selection only) plain <text> sibling — so the whole styled wrapper must
# move together, or the moved glyphs fall back to the SVG-default
# stroke:none and vanish entirely.
_STROKED_TEXT = re.compile(
    r'<g style="[^"]*">\s*<text\b.*?</text>\s*<g class="stroked-text">.*?</g>\s*</g>',
    re.DOTALL,
)

from kicad_fpdb.pipeline import generate_footprint
from kicad_fpdb.reference_cases import CASES, FAMILY_TREE_PATH, KICAD_FOOTPRINTS


def _export_svg(library_dir: Path, footprint_name: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "kicad-cli", "fp", "export", "svg",
            "--footprint", footprint_name,
            "--sketch-pads-on-fab-layers",
            # Restrict layers so pad numbers (drawn on F.Fab) aren't
            # painted over by the many additional mask/paste fill layers
            # a full export draws afterward — worst on through-hole pads,
            # which have the most overlapping layers.
            "--layers", "F.Cu,F.SilkS,F.Fab,F.CrtYd",
            str(library_dir), "-o", str(output_dir),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kicad-cli failed for {footprint_name!r}: {result.stderr}")
    return output_dir / f"{footprint_name}.svg"


def render_comparison(
    descriptor: str,
    reference_path: str,
    output_dir: str,
    name: str | None = None,
    family_tree_path: str = FAMILY_TREE_PATH,
) -> tuple[Path, Path]:
    """Renders the generated footprint for `descriptor` and the real footprint
    at `reference_path` to SVG. Writes <name>_generated.svg and
    <name>_reference.svg into output_dir and returns their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    case_name = name or descriptor.replace(" ", "_")

    with tempfile.TemporaryDirectory() as tmp:
        lib_dir = Path(tmp) / "lib"
        lib_dir.mkdir()
        text = generate_footprint(descriptor, family_tree_path, name=case_name)
        (lib_dir / f"{case_name}.kicad_mod").write_text(text)
        generated_svg = _export_svg(lib_dir, case_name, Path(tmp) / "out")
        generated_dest = output_dir / f"{case_name}_generated.svg"
        generated_dest.write_text(generated_svg.read_text())

    ref_path = Path(reference_path)
    with tempfile.TemporaryDirectory() as tmp:
        reference_svg = _export_svg(ref_path.parent, ref_path.stem, Path(tmp) / "out")
        reference_dest = output_dir / f"{case_name}_reference.svg"
        reference_dest.write_text(reference_svg.read_text())

    return generated_dest, reference_dest


def render_all_known_cases(
    output_dir: str,
    family_tree_path: str = FAMILY_TREE_PATH,
    kicad_footprints: str = KICAD_FOOTPRINTS,
) -> list[dict]:
    cases = []
    for descriptor, relpath in CASES:
        name = descriptor.replace(" ", "_").replace("-", "_")
        reference_path = f"{kicad_footprints}/{relpath}"
        generated_svg, reference_svg = render_comparison(
            descriptor, reference_path, output_dir, name=name,
            family_tree_path=family_tree_path,
        )
        cases.append({
            "name": name,
            "descriptor": descriptor,
            "reference_relpath": relpath,
            "generated_svg": generated_svg,
            "reference_svg": reference_svg,
        })
    return cases


def _pad_svg_viewbox(svg_markup: str, pad_mm: float = SVG_VIEWBOX_PAD_MM) -> str:
    """Extends the root <svg>'s width/height and viewBox by pad_mm on the
    far edge only (the viewBox origin, always 0,0 in kicad-cli's output,
    is left untouched) so a hairline stroke sitting exactly on kicad-cli's
    tight bounding box isn't clipped by the SVG viewport. See
    SVG_VIEWBOX_PAD_MM."""

    def repl(match: re.Match) -> str:
        w, h, vx, vy, vw, vh = (float(g) for g in match.groups())
        return (
            f'width="{w + pad_mm:.6f}mm" height="{h + pad_mm:.6f}mm" '
            f'viewBox="{vx:.6f} {vy:.6f} {vw + pad_mm:.6f} {vh + pad_mm:.6f}"'
        )

    return _SVG_ROOT_VIEWBOX.sub(repl, svg_markup, count=1)


def _scale_svg_to_px(svg_markup: str, px_per_mm: float = PX_PER_MM) -> str:
    """Rewrites the root <svg> element's mm-suffixed width/height (as
    emitted by kicad-cli) to plain px values at px_per_mm, leaving the
    viewBox untouched so the same physical size maps to the same pixel
    size across every embedded footprint."""

    def repl(match: re.Match) -> str:
        width_mm, height_mm = float(match.group(1)), float(match.group(2))
        return f'width="{width_mm * px_per_mm:.3f}" height="{height_mm * px_per_mm:.3f}"'

    return _SVG_ROOT_SIZE.sub(repl, svg_markup, count=1)


def _raise_pad_numbers_on_top(svg_markup: str) -> str:
    texts = _STROKED_TEXT.findall(svg_markup)
    if not texts:
        return svg_markup
    without_texts = _STROKED_TEXT.sub("", svg_markup)
    closing_index = without_texts.rindex("</svg>")
    return without_texts[:closing_index] + "".join(texts) + without_texts[closing_index:]


def _inline_svg(svg_path: Path) -> str:
    text = svg_path.read_text()
    start = text.index("<svg")
    end = text.rindex("</svg>") + len("</svg>")
    markup = _pad_svg_viewbox(text[start:end])
    markup = _scale_svg_to_px(markup)
    return _raise_pad_numbers_on_top(markup)


def _pad1_center_mm(svg_markup: str) -> tuple[float, float] | None:
    """Returns pad 1's exact geometric center, in viewBox mm units (every
    case's viewBox origin is confirmed 0,0, so this is a direct px scale
    away), or None if no pad shape is found."""
    candidates = []
    path_match = _PAD1_PATH.search(svg_markup)
    if path_match:
        candidates.append((path_match.start(), path_match))
    circle_match = _PAD1_CIRCLE.search(svg_markup)
    if circle_match:
        candidates.append((circle_match.start(), circle_match))
    if not candidates:
        return None
    _, match = min(candidates, key=lambda c: c[0])
    if match.re is _PAD1_CIRCLE:
        return float(match.group(1)), float(match.group(2))
    coords = [(float(x), float(y)) for x, y in _COORD_PAIR.findall(match.group(1))]
    xs, ys = [x for x, _ in coords], [y for _, y in coords]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _pad1_frame_position_px(svg_markup: str) -> tuple[float, float] | None:
    """Returns pad 1's pixel position within its FRAME_PX-square .frame box,
    or None if pad 1 can't be found. Matches whichever alignment
    _frame_overflow_style picked for this same svg_markup: centered
    (offset (FRAME_PX - size) / 2) on an axis that fits, flex-start
    (offset 0) on an axis that overflows -- using the centered offset
    unconditionally would drift the anchor out of alignment with the pad
    on any panel taller or wider than the frame."""
    center_mm = _pad1_center_mm(svg_markup)
    if center_mm is None:
        return None
    size_match = _SVG_PX_SIZE.search(svg_markup)
    svg_w_px, svg_h_px = float(size_match.group(1)), float(size_match.group(2))
    offset_x = 0.0 if svg_w_px > FRAME_PX else (FRAME_PX - svg_w_px) / 2
    offset_y = 0.0 if svg_h_px > FRAME_PX else (FRAME_PX - svg_h_px) / 2
    return offset_x + center_mm[0] * PX_PER_MM, offset_y + center_mm[1] * PX_PER_MM


def _frame_overflow_style(svg_markup: str) -> str:
    """CSS overrides for `.frame`'s flex centering when an embedded SVG is
    larger than FRAME_PX on either axis. Centering an overflowing flex
    item splits the excess evenly on both sides, but overflow:auto's
    default scroll origin can only reach the *end*-side excess -- the
    start-side portion (e.g. a tall footprint's top edge) is
    permanently unreachable by scrolling. Falling back to flex-start on
    whichever axis overflows keeps that axis's content fully
    scrollable, while axes that fit stay centered as before."""
    match = _SVG_PX_SIZE.search(svg_markup)
    if not match:
        return ""
    width_px, height_px = float(match.group(1)), float(match.group(2))
    overrides = []
    if width_px > FRAME_PX:
        overrides.append("justify-content: flex-start")
    if height_px > FRAME_PX:
        overrides.append("align-items: flex-start")
    return "; ".join(overrides)


def _grid_position_style(anchor_px: tuple[float, float] | None) -> str:
    """CSS background-position aligning both grid layers (dot centers, and
    checker square corners) to `anchor_px` within a .frame box — or, if
    None, the same phase the grids always used before per-case alignment."""
    x, y = anchor_px or (0.0, 0.0)
    c = CHECKER_PX
    return (
        "background-position: "
        f"{x - DOT_GRID_PX / 2:g}px {y - DOT_GRID_PX / 2:g}px, "
        f"{x:g}px {y:g}px, {x:g}px {y + c:g}px, "
        f"{x + c:g}px {y - c:g}px, {x - c:g}px {y:g}px;"
    )


def build_review_html(cases: list[dict], output_path: str) -> Path:
    """Builds a self-contained HTML review page for the given cases (each a
    dict with name/descriptor/reference_relpath/generated_svg/reference_svg,
    as produced by render_comparison/render_all_known_cases)."""
    case_divs = []
    for case in cases:
        name = html.escape(case["name"])
        descriptor = html.escape(case["descriptor"])
        reference_relpath = html.escape(str(case.get("reference_relpath", "")))
        generated_markup = _inline_svg(Path(case["generated_svg"]))
        reference_markup = _inline_svg(Path(case["reference_svg"]))
        anchor = _pad1_frame_position_px(reference_markup)
        grid_style = _grid_position_style(anchor)
        generated_style = html.escape(f"{grid_style} {_frame_overflow_style(generated_markup)}", quote=True)
        reference_style = html.escape(f"{grid_style} {_frame_overflow_style(reference_markup)}", quote=True)
        case_divs.append(f"""
<div class="case" data-name="{name}">
  <div class="panels">
    <div class="panel"><h3>Generator: {descriptor}</h3><div class="frame" style="{generated_style}">{generated_markup}</div></div>
    <div class="panel"><h3>Reference: {reference_relpath}</h3><div class="frame" style="{reference_style}">{reference_markup}</div></div>
  </div>
</div>""")

    page = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Footprint Review</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 16px; background:#1e1e1e; color:#ddd; }}
  h1 {{ font-size: 1.1rem; }}
  .case {{ display: none; }}
  .case.active {{ display: block; }}
  .panels {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .panel {{
    flex: 1; min-width: 280px; max-width: 500px;
    border: 1px solid #444; border-radius: 8px; padding: 12px; background: #2a2a2a;
  }}
  .panel h3 {{ margin: 0 0 8px; font-size: 0.9rem; color: #aaa; }}
  .frame {{
    width: {FRAME_PX:g}px; height: {FRAME_PX:g}px; overflow: auto;
    display: flex; align-items: center; justify-content: center;
    background-color: #000;
    background-image:
      radial-gradient(circle, rgba(255,255,255,0.9) 1px, transparent 1px),
      linear-gradient(45deg, rgba(255,255,255,0.12) 25%, transparent 25%),
      linear-gradient(-45deg, rgba(255,255,255,0.12) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.12) 75%),
      linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.12) 75%);
    background-size:
      {DOT_GRID_PX:g}px {DOT_GRID_PX:g}px,
      {CHECKER_PX * 2:g}px {CHECKER_PX * 2:g}px, {CHECKER_PX * 2:g}px {CHECKER_PX * 2:g}px,
      {CHECKER_PX * 2:g}px {CHECKER_PX * 2:g}px, {CHECKER_PX * 2:g}px {CHECKER_PX * 2:g}px;
    /* Default background-attachment: scroll keeps a background fixed to
       the element's own box, ignoring its content's scroll position --
       local makes it scroll together with the svg, so the grid stays
       visually locked to the footprint (not just the frame's viewport)
       on panels tall/wide enough to scroll. */
    background-attachment: local, local, local, local, local;
    /* background-position is set per-case (inline style), anchored to the
       reference footprint's pad 1 center — see _grid_position_style. */
  }}
  .frame svg {{ display: block; flex-shrink: 0; }}
  .controls {{ display:flex; gap:8px; align-items:center; margin: 16px 0; flex-wrap: wrap; }}
  button {{ font-size: 1rem; padding: 8px 14px; border-radius: 6px; border: 1px solid #555; background:#2a2a2a; color:#ddd; cursor:pointer; }}
  button.pass {{ border-color:#4c4; color:#4c4; }}
  button.fail {{ border-color:#e55; color:#e55; }}
  .tally {{ margin-left: auto; font-size:0.9rem; }}
  .status {{ font-weight:600; }}
  .status.pass {{ color:#4c4; }}
  .status.fail {{ color:#e55; }}
  .status.unmarked {{ color:#888; }}
  #summary {{ white-space: pre-wrap; background:#2a2a2a; color:#ddd; border:1px solid #444; border-radius:8px; padding:12px; margin-top:16px; font-family: monospace; }}
</style>
</head>
<body>
<h1>Footprint Review &mdash; <span id="counter"></span> &mdash; <span id="status" class="status unmarked"></span></h1>
<div id="cases">{"".join(case_divs)}
</div>
<div class="controls">
  <button id="prev">&larr; Prev</button>
  <button id="pass" class="pass">Pass (P)</button>
  <button id="fail" class="fail">Fail (F)</button>
  <button id="next">Next &rarr;</button>
  <span class="tally" id="tally"></span>
</div>
<div id="summary"></div>
<script>
const results = {{}};
let idx = 0;
const cases = Array.from(document.querySelectorAll(".case"));

function render() {{
  cases.forEach((el, i) => el.classList.toggle("active", i === idx));
  document.getElementById("counter").textContent = (idx + 1) + " / " + cases.length;
  const name = cases[idx].dataset.name;
  const status = results[name] || "unmarked";
  const statusEl = document.getElementById("status");
  statusEl.textContent = status;
  statusEl.className = "status " + status;
  updateTally();
}}

function updateTally() {{
  let pass = 0, fail = 0;
  cases.forEach(el => {{
    const r = results[el.dataset.name];
    if (r === "pass") pass++;
    else if (r === "fail") fail++;
  }});
  const unmarked = cases.length - pass - fail;
  document.getElementById("tally").textContent =
    "Passed: " + pass + "  Failed: " + fail + "  Unmarked: " + unmarked;
  updateSummary();
}}

function updateSummary() {{
  const failed = cases.filter(el => results[el.dataset.name] === "fail").map(el => el.dataset.name);
  const unmarked = cases.filter(el => !results[el.dataset.name]).map(el => el.dataset.name);
  let text = "";
  if (failed.length) text += "FAILED:\\n  " + failed.join("\\n  ") + "\\n\\n";
  if (unmarked.length) text += "UNMARKED:\\n  " + unmarked.join("\\n  ") + "\\n";
  if (!failed.length && !unmarked.length) text = "All cases passed.";
  document.getElementById("summary").textContent = text;
}}

function mark(status) {{
  results[cases[idx].dataset.name] = status;
  if (idx < cases.length - 1) idx++;
  render();
}}

document.getElementById("prev").onclick = () => {{ idx = Math.max(0, idx - 1); render(); }};
document.getElementById("next").onclick = () => {{ idx = Math.min(cases.length - 1, idx + 1); render(); }};
document.getElementById("pass").onclick = () => mark("pass");
document.getElementById("fail").onclick = () => mark("fail");

document.addEventListener("keydown", (e) => {{
  if (e.key === "ArrowLeft") {{ idx = Math.max(0, idx - 1); render(); }}
  else if (e.key === "ArrowRight") {{ idx = Math.min(cases.length - 1, idx + 1); render(); }}
  else if (e.key.toLowerCase() === "p") mark("pass");
  else if (e.key.toLowerCase() === "f") mark("fail");
}});

render();
</script>
</body>
</html>
"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page)
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Render generated vs. real KiCad footprints for visual comparison."
    )
    parser.add_argument("--descriptor", help="Ad-hoc descriptor to render, e.g. 'DIP-16 r'")
    parser.add_argument("--reference", help="Path to the real .kicad_mod reference file (required with --descriptor)")
    parser.add_argument("--name", help="Case name for ad-hoc output files (default: derived from descriptor)")
    parser.add_argument("--output-dir", default="renders", help="Directory to write SVGs and review.html into (default: renders/)")
    args = parser.parse_args(argv)

    if bool(args.descriptor) != bool(args.reference):
        parser.error("--descriptor and --reference must be given together")

    if args.descriptor:
        name = args.name or args.descriptor.replace(" ", "_")
        generated_svg, reference_svg = render_comparison(
            args.descriptor, args.reference, args.output_dir, name=name,
        )
        cases = [{
            "name": name,
            "descriptor": args.descriptor,
            "reference_relpath": args.reference,
            "generated_svg": generated_svg,
            "reference_svg": reference_svg,
        }]
    else:
        cases = render_all_known_cases(args.output_dir)

    review_path = Path(args.output_dir) / "review.html"
    build_review_html(cases, review_path)
    print(f"Wrote {len(cases)} case(s) to {args.output_dir}/")
    print(f"Open {review_path} in a browser to review.")


if __name__ == "__main__":
    main()
