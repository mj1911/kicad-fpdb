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
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

from jedec_fpdb import dip, writer
from jedec_fpdb.compare import _PAD_RE
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


def _svg_viewbox_mm(svg_path: Path) -> tuple[float, float, float, float]:
    """(x0, y0, width, height) of the SVG's viewBox, in mm -- x0/y0 is the
    coordinate-space origin kicad-cli picked for this file's own bounding
    box, needed to place a pad's own footprint-local mm coordinate at its
    correct pixel position within the rasterized image."""
    text = svg_path.read_text()
    start = text.index('viewBox="') + len('viewBox="')
    end = text.index('"', start)
    x0, y0, w, h = (float(v) for v in text[start:end].split())
    return x0, y0, w, h


def _real_pad1_mm(text: str) -> tuple[float, float]:
    """Pad "1"'s (x, y) position, in mm, from a real .kicad_mod file's raw
    text -- reuses compare.py's own pad regex rather than duplicating it."""
    for match in _PAD_RE.finditer(text):
        if match.group(1) == "1":
            return float(match.group(2)), float(match.group(3))
    raise ValueError('no pad "1" found')


def _panel_placement(image_size_px: tuple[int, int]) -> tuple[tuple[int, int], float]:
    """How compose_panel places a footprint image of this pixel size
    within the FRAME_PX square: the paste offset for the (possibly
    downscaled) image, and the scale factor applied (1.0 unless the image
    is larger than the frame on either axis)."""
    fw, fh = image_size_px
    scale = min(FRAME_PX / fw, FRAME_PX / fh, 1.0)
    new_w, new_h = max(1, round(fw * scale)), max(1, round(fh * scale))
    offset = ((FRAME_PX - new_w) // 2, (FRAME_PX - new_h) // 2)
    return offset, scale


def _pad1_frame_position_px(svg_path: Path, pad1_mm: tuple[float, float]) -> tuple[float, float]:
    """Pad 1's pixel position within its FRAME_PX-square panel, once
    compose_panel places this svg's rasterized image (centered, and
    downscaled if it overflows the frame)."""
    x0, y0, w, h = _svg_viewbox_mm(svg_path)
    pad1_px_in_image = ((pad1_mm[0] - x0) * PX_PER_MM, (pad1_mm[1] - y0) * PX_PER_MM)
    image_size_px = (round(w * PX_PER_MM), round(h * PX_PER_MM))
    (offset_x, offset_y), scale = _panel_placement(image_size_px)
    return offset_x + pad1_px_in_image[0] * scale, offset_y + pad1_px_in_image[1] * scale


def _rasterize_svg(svg_path: Path, output_png: Path) -> Path:
    _x0, _y0, width_mm, height_mm = _svg_viewbox_mm(svg_path)
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
    returns a dict of both paths plus each panel's own pad-1 pixel
    position (see _pad1_frame_position_px) -- the reference's is meant to
    become the shared grid anchor both panels' backgrounds are drawn
    with, see render_all_known_cases."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        lib_dir = Path(tmp) / "lib"
        lib_dir.mkdir()
        fp = dip.generate(width_class, pin_count, density)
        writer.write_footprint(fp, lib_dir / f"{fp.name}.kicad_mod")
        generated_svg = _export_svg(lib_dir, fp.name, Path(tmp) / "out")
        pad1 = next(p for p in fp.pads if p.number == 1)
        generated_pad1_px = _pad1_frame_position_px(generated_svg, (pad1.x_mm, pad1.y_mm))
        generated_png = output_dir / f"{name}_generated.png"
        _rasterize_svg(generated_svg, generated_png)

    ref_path = Path(reference_path)
    ref_pad1_mm = _real_pad1_mm(ref_path.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        reference_svg = _export_svg(ref_path.parent, ref_path.stem, Path(tmp) / "out")
        reference_pad1_px = _pad1_frame_position_px(reference_svg, ref_pad1_mm)
        reference_png = output_dir / f"{name}_reference.png"
        _rasterize_svg(reference_svg, reference_png)

    return {
        "generated_png": generated_png,
        "reference_png": reference_png,
        "generated_pad1_px": generated_pad1_px,
        "reference_pad1_px": reference_pad1_px,
    }


def render_all_known_cases(output_dir: Path, kicad_dip_dir: str = KICAD_DIP_DIR) -> list[dict]:
    cases = []
    for width_class, pin_count, filename in CASES:
        name = f"{width_class}_{pin_count}"
        reference_path = f"{kicad_dip_dir}/{filename}"
        result = render_comparison(width_class, pin_count, "N", reference_path, output_dir, name)
        cases.append({
            "name": name,
            "descriptor": f"DIP-{pin_count} {width_class}",
            "reference_relpath": filename,
            # Both panels' grids share this one anchor -- the reference's
            # own pad-1 position -- rather than each being anchored to its
            # own pad 1, so a generated footprint whose pad 1 lands on a
            # different grid dot than the reference is visibly wrong
            # instead of trivially self-aligning.
            "grid_anchor_px": result["reference_pad1_px"],
            **result,
        })
    return cases


def _scale_reference_background(anchor_px: tuple[float, float] | None = None) -> Image.Image:
    """A FRAME_PX-square dark background with a checkerboard + dot-grid
    scale reference, matching kicad-fpdb's own review-viewer convention.
    anchor_px phases both layers so a dot-grid intersection (and a
    checker-square corner) sits exactly on that pixel -- defaults to the
    frame's own (0, 0) corner, the old fixed phase, when omitted."""
    ax, ay = anchor_px if anchor_px is not None else (0.0, 0.0)
    bg = Image.new("RGB", (FRAME_PX, FRAME_PX), "black")

    checker = (255, 255, 255, 30)
    checker_layer = Image.new("RGBA", (FRAME_PX, FRAME_PX), (0, 0, 0, 0))
    checker_draw = ImageDraw.Draw(checker_layer)
    phase_x, phase_y = ax % CHECKER_PX, ay % CHECKER_PX
    x = phase_x - CHECKER_PX
    col = 0
    while x < FRAME_PX:
        y = phase_y - CHECKER_PX
        row = 0
        while y < FRAME_PX:
            if (row + col) % 2 == 0:
                checker_draw.rectangle(
                    [x, y, x + CHECKER_PX, y + CHECKER_PX],
                    fill=checker,
                )
            y += CHECKER_PX
            row += 1
        x += CHECKER_PX
        col += 1
    bg = Image.alpha_composite(bg.convert("RGBA"), checker_layer).convert("RGB")

    dot_color = (255, 255, 255, 230)
    dot_layer = Image.new("RGBA", (FRAME_PX, FRAME_PX), (0, 0, 0, 0))
    dot_draw = ImageDraw.Draw(dot_layer)
    phase_dx, phase_dy = ax % DOT_GRID_PX, ay % DOT_GRID_PX
    x = phase_dx - DOT_GRID_PX
    while x < FRAME_PX:
        y = phase_dy - DOT_GRID_PX
        while y < FRAME_PX:
            dot_draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=dot_color)
            y += DOT_GRID_PX
        x += DOT_GRID_PX
    bg = Image.alpha_composite(bg.convert("RGBA"), dot_layer).convert("RGB")

    return bg


def compose_panel(footprint_png: Path, grid_anchor_px: tuple[float, float] | None = None) -> Image.Image:
    """A FRAME_PX-square panel: the scale-reference background (its grid
    phased to grid_anchor_px, shared across both panels of a case -- see
    render_all_known_cases) with the footprint PNG centered on top. The
    footprint image itself is still placed by its own bounding-box
    center regardless of grid_anchor_px -- centering (rather than
    pad-1-anchoring the image itself) is sufficient here since
    jedec-fpdb's generator draws no extra ornament that could shift a
    footprint's bounding box relative to its real counterpart, and DIP
    bodies are symmetric; the shared grid anchor is what actually
    surfaces a real pad-1 placement mismatch, by no longer trivially
    self-aligning."""
    bg = _scale_reference_background(grid_anchor_px).convert("RGBA")
    fp_img = Image.open(footprint_png).convert("RGBA")
    (offset_x, offset_y), scale = _panel_placement(fp_img.size)
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

    def _photo(self, key: str, png_path: Path, grid_anchor_px: tuple[float, float]) -> ImageTk.PhotoImage:
        if key not in self._photo_cache:
            self._photo_cache[key] = ImageTk.PhotoImage(compose_panel(png_path, grid_anchor_px))
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
        gen_photo = self._photo(f"{case['name']}_g", case["generated_png"], anchor)
        ref_photo = self._photo(f"{case['name']}_r", case["reference_png"], anchor)
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


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Interactively review generated vs. real KiCad DIP footprints."
    )
    parser.add_argument(
        "--output-dir", default="renders",
        help="Directory to write rendered PNGs into (default: renders/)",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    print(f"Rendering {len(CASES)} case(s)...")
    cases = render_all_known_cases(output_dir)

    root = tk.Tk()
    ReviewApp(root, cases)
    root.mainloop()


if __name__ == "__main__":
    main()
