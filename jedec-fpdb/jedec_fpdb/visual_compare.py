"""Interactive Tkinter viewer: cycles through jedec-fpdb's generated DIP
footprints next to their real KiCad reference files for visual, human
review. Requires `kicad-cli` (footprint export) and `rsvg-convert` (SVG
rasterization) on PATH, plus Pillow for image compositing/display.

CLI usage:
    python -m jedec_fpdb.visual_compare
        Renders all cases from jedec_fpdb.reference_cases and opens the
        viewer. Prev/Next (buttons or Left/Right), Pass/Fail (buttons or
        P/F). Closing the window prints a summary of failed/unmarked
        cases to the terminal -- marks aren't persisted to disk.
"""

import argparse
import os
import re
import signal
import subprocess
import tempfile
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

from jedec_fpdb import dip, writer
from jedec_fpdb.reference_cases import CASES, KICAD_DIP_DIR

# Pixels per millimeter for rasterizing both panels -- both use this same
# constant (rather than each being independently resized to fit its
# frame) so a real physical size difference between the generated and
# reference footprint stays visible instead of being scaled away.
PX_PER_MM = 20.0

# Checkerboard square size, in mm, drawn behind each panel as a scale
# reference -- fine enough to act as a ruler without overpowering the
# footprint geometry drawn on top of it.
CHECKER_MM = 0.5
CHECKER_PX = PX_PER_MM * CHECKER_MM

# Dot-grid pitch, in mm, drawn on top of the checkerboard as a second
# scale reference at standard 0.1in (2.54mm) perfboard/breadboard spacing.
DOT_GRID_MM = 0.1 * 25.4
DOT_GRID_PX = PX_PER_MM * DOT_GRID_MM

# Both panels render into a fixed square frame so same-scale footprints
# of different sizes stay visually comparable.
FRAME_PX = 500


def _export_svg(library_dir: Path, footprint_name: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "kicad-cli", "fp", "export", "svg",
            "--footprint", footprint_name,
            "--sketch-pads-on-fab-layers",
            "--layers", "F.Cu,F.SilkS,F.Fab,F.CrtYd",
            str(library_dir), "-o", str(output_dir),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kicad-cli failed for {footprint_name!r}: {result.stderr}")
    return output_dir / f"{footprint_name}.svg"


def _svg_size_mm(svg_path: Path) -> tuple[float, float]:
    """(width, height) of the SVG's viewBox, in mm."""
    text = svg_path.read_text()
    start = text.index('viewBox="') + len('viewBox="')
    end = text.index('"', start)
    _x0, _y0, w, h = (float(v) for v in text[start:end].split())
    return w, h


# kicad-cli's default theme fills F.Cu copper (pads) with this exact color.
# Pads are the only filled shapes using it, and kicad-cli plots them in a
# footprint's own pad-declaration order, so the first #C83434 shape in
# document order is always pad "1" for every case here (both this
# project's own writer and every real reference file list pad "1" first,
# the near-universal KiCad convention). Coordinates in the SVG are
# already in the rasterized image's own mm-per-unit frame -- unlike a
# pad's raw .kicad_mod "at" coordinate, which cannot be mapped to a pixel
# position by subtracting the SVG's viewBox origin: kicad-cli's exported
# viewBox does not preserve the footprint's own local coordinate frame
# (confirmed on DIP-4 narrow, whose real courtyard extends to local
# (-1.06, -1.52) yet the exported SVG's viewBox starts at exactly
# (0.0, 0.0) regardless). Locating pad 1 directly in the rendered output,
# the same technique kicad_fpdb's own review viewer already uses and for
# the same reason, sidesteps that mismatch entirely.
_PAD1_PATH = re.compile(r'<path style="fill:#C83434[^"]*"\s*d="([^"]+)"', re.DOTALL)
_PAD1_CIRCLE = re.compile(r'<g style="fill:#C83434[^"]*">\s*<circle cx="(-?[\d.]+)" cy="(-?[\d.]+)"')
_COORD_PAIR = re.compile(r'(-?[\d.]+),(-?[\d.]+)')


def _pad1_center_mm(svg_text: str) -> tuple[float, float]:
    """Pad 1's exact geometric center, in the SVG's own mm-per-unit
    coordinate frame (i.e. directly scalable to a pixel position by
    PX_PER_MM, no viewBox-origin correction needed)."""
    candidates = []
    path_match = _PAD1_PATH.search(svg_text)
    if path_match:
        candidates.append((path_match.start(), path_match))
    circle_match = _PAD1_CIRCLE.search(svg_text)
    if circle_match:
        candidates.append((circle_match.start(), circle_match))
    if not candidates:
        raise ValueError("no pad 1 (#C83434 fill) found in rendered SVG")
    _, match = min(candidates, key=lambda c: c[0])
    if match.re is _PAD1_CIRCLE:
        return float(match.group(1)), float(match.group(2))
    coords = [(float(x), float(y)) for x, y in _COORD_PAIR.findall(match.group(1))]
    xs, ys = [x for x, _ in coords], [y for _, y in coords]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _shared_scale(*image_sizes_px: tuple[int, int]) -> float:
    """One downscale factor (<=1.0) used for every panel of a case,
    rather than each panel computing its own independently from its own
    image size. Generated and reference images are rarely the exact
    same pixel size (jedec-fpdb's silk is simpler than a real file's,
    with no REF**/Value text bulking out its bounding box), so
    per-panel scaling would give each panel a different scale whenever
    either overflows FRAME_PX -- silently breaking two things at once:
    the "matched true physical scale" comparison this viewer is built
    around (a real size difference would get scaled away instead of
    staying visible), and the dot-grid pitch, which would then also
    differ between panels since each is tied to its own panel's scale.
    Takes the largest dimension across *all* given images and shrinks
    by the one factor needed to fit that alone within FRAME_PX -- 1.0
    (no shrinking at all) unless at least one image actually overflows."""
    max_dim = max(dim for size in image_sizes_px for dim in size)
    return min(1.0, FRAME_PX / max_dim)


def _panel_offset(image_size_px: tuple[int, int], scale: float) -> tuple[int, int]:
    """Where compose_panel pastes an image of this native pixel size,
    once scaled by the case's shared scale (see _shared_scale), to
    center it within the FRAME_PX square."""
    fw, fh = image_size_px
    new_w, new_h = max(1, round(fw * scale)), max(1, round(fh * scale))
    return (FRAME_PX - new_w) // 2, (FRAME_PX - new_h) // 2


def _pad1_frame_position_px(svg_text: str, image_size_px: tuple[int, int], scale: float) -> tuple[float, float]:
    """Pad 1's pixel position within its FRAME_PX-square panel, once
    compose_panel places this svg's rasterized image at the case's
    shared scale (centered, and downscaled if either panel's image
    overflows the frame)."""
    center_mm = _pad1_center_mm(svg_text)
    pad1_px_in_image = (center_mm[0] * PX_PER_MM, center_mm[1] * PX_PER_MM)
    offset_x, offset_y = _panel_offset(image_size_px, scale)
    return offset_x + pad1_px_in_image[0] * scale, offset_y + pad1_px_in_image[1] * scale


def _rasterize_svg(svg_path: Path, output_png: Path) -> Path:
    width_mm, height_mm = _svg_size_mm(svg_path)
    result = subprocess.run(
        [
            "rsvg-convert",
            "-w", f"{width_mm * PX_PER_MM:.3f}",
            "-h", f"{height_mm * PX_PER_MM:.3f}",
            str(svg_path), "-o", str(output_png),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"rsvg-convert failed for {svg_path}: {result.stderr}")
    return output_png


def render_comparison(
    width_class: str, pin_count: int, density: str,
    reference_path: str, output_dir: Path, name: str,
) -> dict:
    """Generates the footprint for (width_class, pin_count, density) and
    rasterizes it alongside the real footprint at reference_path. Writes
    <name>_generated.png / <name>_reference.png into output_dir and
    returns a dict of both paths, the one scale shared by both panels
    (see _shared_scale), and each panel's own pad-1 pixel position (see
    _pad1_frame_position_px) -- the reference's is meant to become the
    shared grid anchor both panels' backgrounds are drawn with, see
    render_all_known_cases."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ref_path = Path(reference_path)

    with tempfile.TemporaryDirectory() as tmp:
        lib_dir = Path(tmp) / "lib"
        lib_dir.mkdir()
        fp = dip.generate(width_class, pin_count, density)
        writer.write_footprint(fp, lib_dir / f"{fp.name}.kicad_mod")
        generated_svg = _export_svg(lib_dir, fp.name, Path(tmp) / "gen_out")
        generated_svg_text = generated_svg.read_text()
        generated_image_size_px = tuple(round(v * PX_PER_MM) for v in _svg_size_mm(generated_svg))

        reference_svg = _export_svg(ref_path.parent, ref_path.stem, Path(tmp) / "ref_out")
        reference_svg_text = reference_svg.read_text()
        reference_image_size_px = tuple(round(v * PX_PER_MM) for v in _svg_size_mm(reference_svg))

        scale = _shared_scale(generated_image_size_px, reference_image_size_px)
        generated_pad1_px = _pad1_frame_position_px(generated_svg_text, generated_image_size_px, scale)
        reference_pad1_px = _pad1_frame_position_px(reference_svg_text, reference_image_size_px, scale)

        generated_png = output_dir / f"{name}_generated.png"
        _rasterize_svg(generated_svg, generated_png)
        reference_png = output_dir / f"{name}_reference.png"
        _rasterize_svg(reference_svg, reference_png)

    return {
        "generated_png": generated_png,
        "reference_png": reference_png,
        "scale": scale,
        "generated_pad1_px": generated_pad1_px,
        "reference_pad1_px": reference_pad1_px,
    }


def _render_case(job: tuple[str, int, str], output_dir: Path, kicad_dip_dir: str) -> dict:
    width_class, pin_count, filename = job
    name = f"{width_class}_{pin_count}"
    reference_path = f"{kicad_dip_dir}/{filename}"
    result = render_comparison(width_class, pin_count, "N", reference_path, output_dir, name)
    return {
        "name": name,
        "descriptor": f"DIP-{pin_count} {width_class}",
        "reference_relpath": filename,
        # Both panels' grids share this one anchor -- the reference's own
        # pad-1 position -- rather than each being anchored to its own
        # pad 1, so a generated footprint whose pad 1 lands on a
        # different grid dot than the reference is visibly wrong instead
        # of trivially self-aligning.
        "grid_anchor_px": result["reference_pad1_px"],
        **result,
    }


def render_all_known_cases(output_dir: Path, kicad_dip_dir: str = KICAD_DIP_DIR) -> list[dict]:
    """Renders every case in CASES. Each case is 4 independent, purely
    I/O-bound subprocess calls (kicad-cli x2, rsvg-convert x2) with no
    shared state -- output_dir is the only thing cases have in common,
    and each writes distinct, uniquely-named files into it -- so a
    thread pool (GIL released while waiting on each subprocess) cuts
    wall-clock time roughly to the slowest single case instead of the
    sum of all of them."""
    with ThreadPoolExecutor() as executor:
        # map (not submit+as_completed) preserves CASES's own order in
        # the result regardless of which case's subprocesses finish
        # first, so the viewer's case order doesn't depend on scheduling.
        return list(executor.map(lambda job: _render_case(job, output_dir, kicad_dip_dir), CASES))


def _scale_reference_background(
    anchor_px: tuple[float, float] | None = None, scale: float = 1.0,
) -> Image.Image:
    """A FRAME_PX-square dark background with a checkerboard + dot-grid
    scale reference, matching kicad-fpdb's own review-viewer convention.
    anchor_px phases both layers so a dot-grid intersection (and a
    checker-square corner) sits exactly on that pixel -- defaults to the
    frame's own (0, 0) corner, the old fixed phase, when omitted. scale
    must match whatever _panel_placement chose for the footprint image
    this background sits behind (1.0 unless that image overflows the
    frame and gets downscaled to fit): CHECKER_PX/DOT_GRID_PX are real
    physical pitches (0.5mm/2.54mm) only at the image's native
    PX_PER_MM rendering -- a downscaled footprint needs its grid pitch
    shrunk by the same factor, or the grid no longer lines up with the
    footprint's own real features once panned across it (only the one
    anchor pixel would still coincide, by construction, everywhere else
    would drift). Confirmed on DIP-24 (taller than FRAME_PX, downscaled
    ~0.73x): the fixed, unscaled grid pitch used before this only ever
    looked right on a case small enough to render at 1:1."""
    ax, ay = anchor_px if anchor_px is not None else (0.0, 0.0)
    checker_px = CHECKER_PX * scale
    dot_grid_px = DOT_GRID_PX * scale
    bg = Image.new("RGB", (FRAME_PX, FRAME_PX), "black")

    checker = (255, 255, 255, 30)
    checker_layer = Image.new("RGBA", (FRAME_PX, FRAME_PX), (0, 0, 0, 0))
    checker_draw = ImageDraw.Draw(checker_layer)
    phase_x, phase_y = ax % checker_px, ay % checker_px
    x = phase_x - checker_px
    col = 0
    while x < FRAME_PX:
        y = phase_y - checker_px
        row = 0
        while y < FRAME_PX:
            if (row + col) % 2 == 0:
                checker_draw.rectangle(
                    [x, y, x + checker_px, y + checker_px],
                    fill=checker,
                )
            y += checker_px
            row += 1
        x += checker_px
        col += 1
    bg = Image.alpha_composite(bg.convert("RGBA"), checker_layer).convert("RGB")

    dot_color = (255, 255, 255, 230)
    dot_layer = Image.new("RGBA", (FRAME_PX, FRAME_PX), (0, 0, 0, 0))
    dot_draw = ImageDraw.Draw(dot_layer)
    phase_dx, phase_dy = ax % dot_grid_px, ay % dot_grid_px
    x = phase_dx - dot_grid_px
    while x < FRAME_PX:
        y = phase_dy - dot_grid_px
        while y < FRAME_PX:
            dot_draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=dot_color)
            y += dot_grid_px
        x += dot_grid_px
    bg = Image.alpha_composite(bg.convert("RGBA"), dot_layer).convert("RGB")

    return bg


def compose_panel(
    footprint_png: Path, scale: float = 1.0, grid_anchor_px: tuple[float, float] | None = None,
) -> Image.Image:
    """A FRAME_PX-square panel: the scale-reference background (its grid
    phased to grid_anchor_px, shared across both panels of a case -- see
    render_all_known_cases; its pitch matched to the case's own shared
    scale -- see _scale_reference_background/_shared_scale) with the
    footprint PNG centered on top, at that same scale. The footprint
    image itself is still placed by its own bounding-box center
    regardless of grid_anchor_px -- centering (rather than
    pad-1-anchoring the image itself) is sufficient here since
    jedec-fpdb's generator draws no extra ornament that could shift a
    footprint's bounding box relative to its real counterpart, and DIP
    bodies are symmetric; the shared grid anchor is what actually
    surfaces a real pad-1 placement mismatch, by no longer trivially
    self-aligning. `scale` must be the case's one shared scale (see
    _shared_scale), not recomputed from this image's own size alone --
    generated and reference images are rarely the same pixel size, so
    doing that would give the two panels of one case different scales
    (and thus different grid pitches) whenever either overflows the
    frame."""
    fp_img = Image.open(footprint_png).convert("RGBA")
    offset_x, offset_y = _panel_offset(fp_img.size, scale)
    bg = _scale_reference_background(grid_anchor_px, scale).convert("RGBA")
    if scale != 1.0:
        fp_img = fp_img.resize((max(1, round(fp_img.width * scale)), max(1, round(fp_img.height * scale))))
    bg.paste(fp_img, (offset_x, offset_y), fp_img)
    return bg.convert("RGB")


class ReviewApp:
    def __init__(self, root: tk.Tk, cases: list[dict]):
        self.root = root
        self.cases = cases
        self.results: dict[str, str] = {}
        self.idx = 0
        # Keep references so Tkinter doesn't garbage-collect the images.
        self._photo_cache: dict[str, ImageTk.PhotoImage] = {}

        root.title("jedec-fpdb Footprint Review")

        self.title_label = tk.Label(root, font=("", 13, "bold"))
        self.title_label.pack(pady=(8, 0))
        self.status_label = tk.Label(root, font=("", 11))
        self.status_label.pack()

        panels = tk.Frame(root)
        panels.pack(padx=12, pady=12)
        self.generated_header = tk.Label(panels, font=("", 10))
        self.generated_header.grid(row=0, column=0)
        self.reference_header = tk.Label(panels, font=("", 10))
        self.reference_header.grid(row=0, column=1)
        self.generated_canvas = tk.Label(panels, bg="black")
        self.generated_canvas.grid(row=1, column=0, padx=8)
        self.reference_canvas = tk.Label(panels, bg="black")
        self.reference_canvas.grid(row=1, column=1, padx=8)

        controls = tk.Frame(root)
        controls.pack(pady=(0, 10))
        tk.Button(controls, text="← Prev", command=self.prev).grid(row=0, column=0, padx=4)
        tk.Button(controls, text="Pass (P)", command=lambda: self.mark("pass")).grid(row=0, column=1, padx=4)
        tk.Button(controls, text="Fail (F)", command=lambda: self.mark("fail")).grid(row=0, column=2, padx=4)
        tk.Button(controls, text="Next →", command=self.next).grid(row=0, column=3, padx=4)
        self.tally_label = tk.Label(controls, font=("", 10))
        self.tally_label.grid(row=0, column=4, padx=(20, 0))

        root.bind("<Left>", lambda e: self.prev())
        root.bind("<Right>", lambda e: self.next())
        root.bind("<KeyPress-p>", lambda e: self.mark("pass"))
        root.bind("<KeyPress-P>", lambda e: self.mark("pass"))
        root.bind("<KeyPress-f>", lambda e: self.mark("fail"))
        root.bind("<KeyPress-F>", lambda e: self.mark("fail"))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.render()

    def _photo(
        self, key: str, png_path: Path, scale: float, grid_anchor_px: tuple[float, float],
    ) -> ImageTk.PhotoImage:
        if key not in self._photo_cache:
            self._photo_cache[key] = ImageTk.PhotoImage(compose_panel(png_path, scale, grid_anchor_px))
        return self._photo_cache[key]

    def render(self) -> None:
        case = self.cases[self.idx]
        self.title_label.config(text=f"{case['descriptor']}  ({self.idx + 1} / {len(self.cases)})")
        status = self.results.get(case["name"], "unmarked")
        color = {"pass": "green", "fail": "red", "unmarked": "gray"}[status]
        self.status_label.config(text=status.upper(), fg=color)

        self.generated_header.config(text=f"Generator: {case['descriptor']}")
        self.reference_header.config(text=f"Reference: {case['reference_relpath']}")

        anchor = case["grid_anchor_px"]
        scale = case["scale"]
        gen_photo = self._photo(f"{case['name']}_g", case["generated_png"], scale, anchor)
        ref_photo = self._photo(f"{case['name']}_r", case["reference_png"], scale, anchor)
        self.generated_canvas.config(image=gen_photo)
        self.reference_canvas.config(image=ref_photo)

        self.update_tally()

    def update_tally(self) -> None:
        passed = sum(1 for v in self.results.values() if v == "pass")
        failed = sum(1 for v in self.results.values() if v == "fail")
        unmarked = len(self.cases) - passed - failed
        self.tally_label.config(text=f"Passed: {passed}  Failed: {failed}  Unmarked: {unmarked}")

    def prev(self) -> None:
        self.idx = max(0, self.idx - 1)
        self.render()

    def next(self) -> None:
        self.idx = min(len(self.cases) - 1, self.idx + 1)
        self.render()

    def mark(self, status: str) -> None:
        self.results[self.cases[self.idx]["name"]] = status
        if self.idx < len(self.cases) - 1:
            self.idx += 1
        self.render()

    def on_close(self) -> None:
        failed = [c["name"] for c in self.cases if self.results.get(c["name"]) == "fail"]
        unmarked = [c["name"] for c in self.cases if c["name"] not in self.results]
        print()
        if failed:
            print("FAILED:")
            for name in failed:
                print(f"  {name}")
        if unmarked:
            print("UNMARKED:")
            for name in unmarked:
                print(f"  {name}")
        if not failed and not unmarked:
            print("All cases passed.")
        self.root.destroy()


def _terminate_other_running_instances() -> None:
    """SIGTERMs any other `python ... jedec_fpdb.visual_compare` process
    still running, so re-launching (by hand, or via the VS Code task)
    after a previous window never got closed doesn't pile up duplicate
    viewer windows -- Linux-only (/proc), matching this project's
    stated dev environment. Only matches actual python processes (via
    /proc/<pid>/comm) rather than a plain substring match on cmdline
    alone, so a shell that merely launched one with this string in its
    own argv (e.g. `bash -c "python3 -m jedec_fpdb.visual_compare"`)
    isn't mistaken for the process itself. A killed instance skips its
    normal on_close summary -- acceptable, since pass/fail marks were
    never persisted anyway."""
    my_pid = os.getpid()
    killed = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == my_pid:
            continue
        pid = int(entry.name)
        try:
            comm = (entry / "comm").read_text().strip()
            if "python" not in comm:
                continue
            cmdline = (entry / "cmdline").read_bytes().decode(errors="replace")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if "jedec_fpdb.visual_compare" in cmdline:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
            except ProcessLookupError:
                pass

    # Best-effort wait so the old window is actually gone before the new
    # one appears, rather than briefly overlapping -- a Tk process with
    # no custom SIGTERM handler exits almost immediately, so this rarely
    # uses its full budget.
    deadline = time.monotonic() + 2.0
    for pid in killed:
        while Path(f"/proc/{pid}").exists() and time.monotonic() < deadline:
            time.sleep(0.05)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Interactively review generated vs. real KiCad DIP footprints."
    )
    parser.add_argument(
        "--output-dir", default="renders",
        help="Directory to write rendered PNGs into (default: renders/)",
    )
    args = parser.parse_args(argv)

    _terminate_other_running_instances()

    output_dir = Path(args.output_dir)
    print(f"Rendering {len(CASES)} case(s)...")
    cases = render_all_known_cases(output_dir)

    root = tk.Tk()
    ReviewApp(root, cases)
    root.mainloop()


if __name__ == "__main__":
    main()
