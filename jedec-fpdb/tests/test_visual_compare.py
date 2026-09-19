import os
import shutil

import pytest
from PIL import Image

from jedec_fpdb.reference_cases import KICAD_DIP_DIR
from jedec_fpdb.visual_compare import (
    FRAME_PX,
    compose_panel,
    render_comparison,
    _pad1_frame_position_px,
    _panel_placement,
    _real_pad1_mm,
    _scale_reference_background,
    _svg_viewbox_mm,
)

requires_tools = pytest.mark.skipif(
    not (os.path.isdir(KICAD_DIP_DIR) and shutil.which("kicad-cli") and shutil.which("rsvg-convert")),
    reason="kicad-cli, rsvg-convert, and the real KiCad DIP library are all required",
)


def test_scale_reference_background_is_frame_sized():
    bg = _scale_reference_background()
    assert bg.size == (FRAME_PX, FRAME_PX)


def test_scale_reference_background_dot_lands_on_anchor():
    anchor = (123.0, 77.0)
    bg = _scale_reference_background(anchor)
    x, y = int(anchor[0]), int(anchor[1])
    # The dot layer draws a small filled circle centered on the anchor --
    # its center pixel should be close to the bright dot color (not exact,
    # since it's alpha-composited over black/the faint checker tint), well
    # above the checker-only background level.
    assert all(channel > 200 for channel in bg.getpixel((x, y)))


def test_panel_placement_centers_image_smaller_than_frame():
    offset, scale = _panel_placement((40, 60))
    assert scale == 1.0
    assert offset == ((FRAME_PX - 40) // 2, (FRAME_PX - 60) // 2)


def test_panel_placement_downscales_image_larger_than_frame():
    offset, scale = _panel_placement((FRAME_PX + 100, FRAME_PX + 50))
    assert scale < 1.0
    assert 0 <= offset[0] < FRAME_PX
    assert 0 <= offset[1] < FRAME_PX


def test_real_pad1_mm_finds_pad_one_not_pad_two():
    text = (
        '(pad "2" thru_hole circle (at 1.27 2.54) (size 1.6 1.6) (drill 0.8))\n'
        '(pad "1" thru_hole rect (at -1.27 -2.54) (size 1.6 1.6) (drill 0.8))\n'
    )
    assert _real_pad1_mm(text) == (-1.27, -2.54)


def test_real_pad1_mm_raises_when_no_pad_one():
    with pytest.raises(ValueError):
        _real_pad1_mm('(pad "2" thru_hole circle (at 0 0) (size 1 1) (drill 0.5))')


def test_svg_viewbox_mm_parses_origin_and_size(tmp_path):
    svg_path = tmp_path / "case.svg"
    svg_path.write_text('<svg viewBox="1.500000 2.000000 9.000000 11.000000"></svg>')
    assert _svg_viewbox_mm(svg_path) == (1.5, 2.0, 9.0, 11.0)


def test_pad1_frame_position_px_accounts_for_viewbox_origin(tmp_path):
    svg_path = tmp_path / "case.svg"
    # A 10x10mm viewBox starting at (1, 1) -- pad 1 sits at its footprint-
    # local (1, 1), i.e. exactly the viewBox origin, so it should land at
    # pixel (0, 0) of the rasterized image, then centered by _panel_placement.
    svg_path.write_text('<svg viewBox="1.000000 1.000000 10.000000 10.000000"></svg>')
    px = _pad1_frame_position_px(svg_path, (1.0, 1.0))
    offset, _scale = _panel_placement((200, 200))  # 10mm * PX_PER_MM(20)
    assert px == offset


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
    result = render_comparison(
        "narrow", 8, "N", f"{KICAD_DIP_DIR}/DIP-8_W7.62mm.kicad_mod", tmp_path, "narrow_8",
    )
    assert result["generated_png"].is_file()
    assert result["reference_png"].is_file()
    with Image.open(result["generated_png"]) as im:
        assert im.width > 0 and im.height > 0
    # Both are frame-relative pixel positions, so within the frame bounds.
    for px in (result["generated_pad1_px"], result["reference_pad1_px"]):
        assert 0 <= px[0] <= FRAME_PX
        assert 0 <= px[1] <= FRAME_PX
