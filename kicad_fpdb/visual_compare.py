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

_SVG_ROOT_SIZE = re.compile(r'width="([\d.]+)mm" height="([\d.]+)mm"')

from kicad_fpdb.pipeline import generate_footprint
from kicad_fpdb.reference_cases import CASES, FAMILY_TREE_PATH, KICAD_FOOTPRINTS


def _export_svg(library_dir: Path, footprint_name: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "kicad-cli", "fp", "export", "svg",
            "--footprint", footprint_name,
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


def _scale_svg_to_px(svg_markup: str, px_per_mm: float = PX_PER_MM) -> str:
    """Rewrites the root <svg> element's mm-suffixed width/height (as
    emitted by kicad-cli) to plain px values at px_per_mm, leaving the
    viewBox untouched so the same physical size maps to the same pixel
    size across every embedded footprint."""

    def repl(match: re.Match) -> str:
        width_mm, height_mm = float(match.group(1)), float(match.group(2))
        return f'width="{width_mm * px_per_mm:.3f}" height="{height_mm * px_per_mm:.3f}"'

    return _SVG_ROOT_SIZE.sub(repl, svg_markup, count=1)


def _inline_svg(svg_path: Path) -> str:
    text = svg_path.read_text()
    start = text.index("<svg")
    end = text.rindex("</svg>") + len("</svg>")
    return _scale_svg_to_px(text[start:end])


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
        case_divs.append(f"""
<div class="case" data-name="{name}">
  <p><strong>{descriptor}</strong> vs <code>{reference_relpath}</code></p>
  <div class="panels">
    <div class="panel"><h3>Generated</h3><div class="frame">{generated_markup}</div></div>
    <div class="panel"><h3>Reference</h3><div class="frame">{reference_markup}</div></div>
  </div>
</div>""")

    page = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Footprint Review</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 16px; background:#fafafa; color:#111; }}
  h1 {{ font-size: 1.1rem; }}
  .case {{ display: none; }}
  .case.active {{ display: block; }}
  .panels {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .panel {{
    flex: 1; min-width: 280px; max-width: 500px;
    border: 1px solid #ddd; border-radius: 8px; padding: 12px; background: #fff;
  }}
  .panel h3 {{ margin: 0 0 8px; font-size: 0.9rem; color: #555; }}
  .frame {{
    height: 500px; overflow: auto;
    display: flex; align-items: center; justify-content: center;
    background-image:
      linear-gradient(45deg, rgba(0,0,0,0.06) 25%, transparent 25%),
      linear-gradient(-45deg, rgba(0,0,0,0.06) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, rgba(0,0,0,0.06) 75%),
      linear-gradient(-45deg, transparent 75%, rgba(0,0,0,0.06) 75%);
    background-size: {CHECKER_PX * 2:g}px {CHECKER_PX * 2:g}px;
    background-position: 0 0, 0 {CHECKER_PX:g}px, {CHECKER_PX:g}px -{CHECKER_PX:g}px, -{CHECKER_PX:g}px 0;
  }}
  .frame svg {{ display: block; flex-shrink: 0; }}
  .controls {{ display:flex; gap:8px; align-items:center; margin: 16px 0; flex-wrap: wrap; }}
  button {{ font-size: 1rem; padding: 8px 14px; border-radius: 6px; border: 1px solid #ccc; background:#fff; cursor:pointer; }}
  button.pass {{ border-color:#2a2; color:#2a2; }}
  button.fail {{ border-color:#c33; color:#c33; }}
  .tally {{ margin-left: auto; font-size:0.9rem; }}
  .status {{ font-weight:600; }}
  .status.pass {{ color:#2a2; }}
  .status.fail {{ color:#c33; }}
  .status.unmarked {{ color:#999; }}
  #summary {{ white-space: pre-wrap; background:#fff; border:1px solid #ddd; border-radius:8px; padding:12px; margin-top:16px; font-family: monospace; }}
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
