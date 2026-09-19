import os
import shutil
import subprocess
import time

import pytest
from PIL import Image

from jedec_fpdb.reference_cases import KICAD_DIP_DIR
from jedec_fpdb.visual_compare import (
    FRAME_PX,
    compose_panel,
    render_comparison,
    _pad1_center_mm,
    _pad1_frame_position_px,
    _panel_placement,
    _scale_reference_background,
    _svg_size_mm,
    _terminate_other_running_instances,
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


def test_svg_size_mm_parses_viewbox_size(tmp_path):
    svg_path = tmp_path / "case.svg"
    svg_path.write_text('<svg viewBox="1.500000 2.000000 9.000000 11.000000"></svg>')
    assert _svg_size_mm(svg_path) == (9.0, 11.0)


# A minimal kicad-cli-shaped SVG fragment: pad "1" as the first #C83434
# path (kicad-cli's copper fill color), matching how a rect/roundrect
# thru-hole pad is actually rendered -- see real output inspected while
# diagnosing the viewBox-origin bug this replaced.
_PAD1_PATH_SVG = (
    '<g style="fill:#C83434; fill-opacity:1.000000; stroke:none;">'
    '<path style="fill:#C83434; fill-opacity:1.000000; stroke:none;" '
    'd="M 2.000000,3.000000 4.000000,3.000000 4.000000,5.000000 2.000000,5.000000 Z" />'
    '</g>'
    '<g style="fill:#C83434; fill-opacity:1.000000;"><circle cx="9.0" cy="3.0" r="0.8" /></g>'
)

# A round (non-pin-1) pad rendered first, pad 1's own circle second --
# pad 1 must still be the one picked, by document order, not shape.
_PAD1_CIRCLE_SVG = (
    '<g style="fill:#C83434; fill-opacity:1.000000;"><circle cx="9.0" cy="3.0" r="0.8" /></g>'
    '<g style="fill:#C83434; fill-opacity:1.000000;"><circle cx="2.0" cy="2.0" r="0.8" /></g>'
)


def test_pad1_center_mm_finds_earliest_path_shape():
    assert _pad1_center_mm(_PAD1_PATH_SVG) == (3.0, 4.0)


def test_pad1_center_mm_finds_earliest_circle_shape():
    assert _pad1_center_mm(_PAD1_CIRCLE_SVG) == (9.0, 3.0)


def test_pad1_center_mm_raises_when_no_copper_fill_found():
    with pytest.raises(ValueError):
        _pad1_center_mm('<path style="fill:#000000;" d="M 0,0 1,1 Z" />')


def test_pad1_frame_position_px_scales_and_centers():
    # pad 1's own center at (3, 4)mm in a 10x10mm image -- pixel-in-image
    # is (60, 80) at PX_PER_MM(20), then centered by _panel_placement.
    px = _pad1_frame_position_px(_PAD1_PATH_SVG, (200, 200))
    offset, _scale = _panel_placement((200, 200))
    assert px == (offset[0] + 60.0, offset[1] + 80.0)


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


def _spawn_marked_process(marker: str) -> subprocess.Popen:
    """A real python subprocess whose cmdline contains `marker` -- put
    literally in its -c script text, which becomes part of its own
    argv/cmdline without actually needing to run visual_compare itself."""
    proc = subprocess.Popen(["python3", "-c", f"import time; time.sleep(30)  # {marker}"])
    time.sleep(0.3)  # let it actually start before we look for it
    return proc


def test_terminate_other_running_instances_kills_matching_process():
    proc = _spawn_marked_process("jedec_fpdb.visual_compare")
    try:
        assert proc.poll() is None
        _terminate_other_running_instances()
        assert proc.wait(timeout=3) is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_terminate_other_running_instances_ignores_unrelated_process():
    proc = _spawn_marked_process("some unrelated marker")
    try:
        _terminate_other_running_instances()
        time.sleep(0.3)
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()
