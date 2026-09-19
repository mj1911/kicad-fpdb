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
    text = svg_path.read_text()
    start = text.index('viewBox="') + len('viewBox="')
    end = text.index('"', start)
    _x, _y, w, h = (float(v) for v in text[start:end].split())
    return w, h


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
) -> tuple[Path, Path]:
    """Generates the footprint for (width_class, pin_count, density) and
    rasterizes it alongside the real footprint at reference_path. Writes
    <name>_generated.png / <name>_reference.png into output_dir and
    returns their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        lib_dir = Path(tmp) / "lib"
        lib_dir.mkdir()
        fp = dip.generate(width_class, pin_count, density)
        writer.write_footprint(fp, lib_dir / f"{fp.name}.kicad_mod")
        generated_svg = _export_svg(lib_dir, fp.name, Path(tmp) / "out")
        generated_png = output_dir / f"{name}_generated.png"
        _rasterize_svg(generated_svg, generated_png)

    ref_path = Path(reference_path)
    with tempfile.TemporaryDirectory() as tmp:
        reference_svg = _export_svg(ref_path.parent, ref_path.stem, Path(tmp) / "out")
        reference_png = output_dir / f"{name}_reference.png"
        _rasterize_svg(reference_svg, reference_png)

    return generated_png, reference_png


def render_all_known_cases(output_dir: Path, kicad_dip_dir: str = KICAD_DIP_DIR) -> list[dict]:
    cases = []
    for width_class, pin_count, filename in CASES:
        name = f"{width_class}_{pin_count}"
        reference_path = f"{kicad_dip_dir}/{filename}"
        generated_png, reference_png = render_comparison(
            width_class, pin_count, "N", reference_path, output_dir, name,
        )
        cases.append({
            "name": name,
            "descriptor": f"DIP-{pin_count} {width_class}",
            "reference_relpath": filename,
            "generated_png": generated_png,
            "reference_png": reference_png,
        })
    return cases


def _scale_reference_background() -> Image.Image:
    """A FRAME_PX-square dark background with a checkerboard + dot-grid
    scale reference, matching kicad-fpdb's own review-viewer convention."""
    bg = Image.new("RGB", (FRAME_PX, FRAME_PX), "black")
    draw = ImageDraw.Draw(bg)

    checker = (255, 255, 255, 30)
    checker_layer = Image.new("RGBA", (FRAME_PX, FRAME_PX), (0, 0, 0, 0))
    checker_draw = ImageDraw.Draw(checker_layer)
    x = 0.0
    col = 0
    while x < FRAME_PX:
        y = 0.0
        row = 0
        while y < FRAME_PX:
            if (row + col) % 2 == 0:
                checker_draw.rectangle(
                    [x, y, min(x + CHECKER_PX, FRAME_PX), min(y + CHECKER_PX, FRAME_PX)],
                    fill=checker,
                )
            y += CHECKER_PX
            row += 1
        x += CHECKER_PX
        col += 1
    bg = Image.alpha_composite(bg.convert("RGBA"), checker_layer).convert("RGB")

    draw = ImageDraw.Draw(bg)
    dot_color = (255, 255, 255, 230)
    dot_layer = Image.new("RGBA", (FRAME_PX, FRAME_PX), (0, 0, 0, 0))
    dot_draw = ImageDraw.Draw(dot_layer)
    x = 0.0
    while x < FRAME_PX:
        y = 0.0
        while y < FRAME_PX:
            dot_draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=dot_color)
            y += DOT_GRID_PX
        x += DOT_GRID_PX
    bg = Image.alpha_composite(bg.convert("RGBA"), dot_layer).convert("RGB")

    return bg


def compose_panel(footprint_png: Path) -> Image.Image:
    """A FRAME_PX-square panel: the scale-reference background with the
    footprint PNG centered on top. Centering (rather than pad-1
    anchoring, as kicad-fpdb's own HTML viewer does) is sufficient here
    since jedec-fpdb's generator draws no extra ornament that could shift
    a footprint's bounding box relative to its real counterpart, and DIP
    bodies are symmetric."""
    bg = _scale_reference_background().convert("RGBA")
    fp_img = Image.open(footprint_png).convert("RGBA")
    fw, fh = fp_img.size
    if fw > FRAME_PX or fh > FRAME_PX:
        scale = min(FRAME_PX / fw, FRAME_PX / fh)
        fp_img = fp_img.resize((max(1, int(fw * scale)), max(1, int(fh * scale))))
        fw, fh = fp_img.size
    offset = ((FRAME_PX - fw) // 2, (FRAME_PX - fh) // 2)
    bg.paste(fp_img, offset, fp_img)
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

    def _photo(self, key: str, png_path: Path) -> ImageTk.PhotoImage:
        if key not in self._photo_cache:
            self._photo_cache[key] = ImageTk.PhotoImage(compose_panel(png_path))
        return self._photo_cache[key]

    def render(self) -> None:
        case = self.cases[self.idx]
        self.title_label.config(text=f"{case['descriptor']}  ({self.idx + 1} / {len(self.cases)})")
        status = self.results.get(case["name"], "unmarked")
        color = {"pass": "green", "fail": "red", "unmarked": "gray"}[status]
        self.status_label.config(text=status.upper(), fg=color)

        self.generated_header.config(text=f"Generator: {case['descriptor']}")
        self.reference_header.config(text=f"Reference: {case['reference_relpath']}")

        gen_photo = self._photo(f"{case['name']}_g", case["generated_png"])
        ref_photo = self._photo(f"{case['name']}_r", case["reference_png"])
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
