import os
import shutil

import pytest
from PIL import Image

from jedec_fpdb.reference_cases import KICAD_DIP_DIR
from jedec_fpdb.visual_compare import (
    FRAME_PX,
    compose_panel,
    render_comparison,
    _scale_reference_background,
)

requires_tools = pytest.mark.skipif(
    not (os.path.isdir(KICAD_DIP_DIR) and shutil.which("kicad-cli") and shutil.which("rsvg-convert")),
    reason="kicad-cli, rsvg-convert, and the real KiCad DIP library are all required",
)


def test_scale_reference_background_is_frame_sized():
    bg = _scale_reference_background()
    assert bg.size == (FRAME_PX, FRAME_PX)


def test_compose_panel_centers_small_footprint_on_frame(tmp_path):
    small = Image.new("RGBA", (40, 60), (200, 52, 52, 255))
    png_path = tmp_path / "small.png"
    small.save(png_path)

    panel = compose_panel(png_path)

    assert panel.size == (FRAME_PX, FRAME_PX)
    center_x, center_y = FRAME_PX // 2, FRAME_PX // 2
    assert panel.getpixel((center_x, center_y)) == (200, 52, 52)


def test_compose_panel_downscales_footprint_larger_than_frame(tmp_path):
    big = Image.new("RGBA", (FRAME_PX + 100, FRAME_PX + 50), (200, 52, 52, 255))
    png_path = tmp_path / "big.png"
    big.save(png_path)

    panel = compose_panel(png_path)

    assert panel.size == (FRAME_PX, FRAME_PX)


@requires_tools
def test_render_comparison_writes_both_pngs(tmp_path):
    generated_png, reference_png = render_comparison(
        "narrow", 8, "N", f"{KICAD_DIP_DIR}/DIP-8_W7.62mm.kicad_mod", tmp_path, "narrow_8",
    )
    assert generated_png.is_file()
    assert reference_png.is_file()
    with Image.open(generated_png) as im:
        assert im.width > 0 and im.height > 0
