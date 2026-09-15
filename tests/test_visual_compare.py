import os

import pytest

from kicad_fpdb.reference_cases import KICAD_FOOTPRINTS
from kicad_fpdb.visual_compare import (
    FRAME_PX,
    PX_PER_MM,
    build_review_html,
    render_comparison,
    _frame_overflow_style,
    _pad1_frame_position_px,
    _raise_pad_numbers_on_top,
)

pytestmark = pytest.mark.skipif(
    not os.path.isdir(KICAD_FOOTPRINTS),
    reason=f"{KICAD_FOOTPRINTS} not present on this machine",
)


def test_raise_pad_numbers_on_top_moves_stroked_text_after_later_content():
    svg = (
        '<svg>'
        '<g style="fill:none; stroke:#AFAFAF;">'
        '<text x="0" y="0" opacity="0">1</text>'
        '<g class="stroked-text"><desc>1</desc><path d="M0 0" /></g>'
        '</g>'
        '<circle cx="1" cy="1" r="1" />'
        '</svg>'
    )
    result = _raise_pad_numbers_on_top(svg)
    assert result.index('<g class="stroked-text">') > result.index("<circle")


def test_raise_pad_numbers_on_top_preserves_stroke_color():
    # A stroked-text group carries no color of its own — it inherits from
    # the enclosing <g style="..."> — so moving the group must carry that
    # wrapper along too, or the glyphs fall back to the SVG default of
    # stroke:none and become invisible.
    svg = (
        '<svg>'
        '<g style="fill:none; stroke:#AFAFAF;">'
        '<text x="0" y="0" opacity="0">1</text>'
        '<g class="stroked-text"><desc>1</desc><path d="M0 0" /></g>'
        '</g>'
        '<circle cx="1" cy="1" r="1" />'
        '</svg>'
    )
    result = _raise_pad_numbers_on_top(svg)
    moved = result[result.index("<circle") :]
    assert "stroke:#AFAFAF" in moved
    assert moved.index("stroke:#AFAFAF") < moved.index('<g class="stroked-text">')


def test_raise_pad_numbers_on_top_is_a_noop_without_stroked_text():
    svg = "<svg><circle cx=\"1\" cy=\"1\" r=\"1\" /></svg>"
    assert _raise_pad_numbers_on_top(svg) == svg


def test_frame_overflow_style_empty_when_svg_fits():
    svg = f'<svg width="{FRAME_PX - 1}" height="{FRAME_PX - 1}">'
    assert _frame_overflow_style(svg) == ""


def test_frame_overflow_style_flex_start_when_height_overflows():
    # A tall footprint (e.g. DIP-24 wide) centered via flex in an
    # overflow:auto frame has its top-side excess permanently
    # unreachable by scrolling -- flex-start on the overflowing axis
    # keeps the whole footprint scrollable into view.
    svg = f'<svg width="{FRAME_PX - 1}" height="{FRAME_PX + 200}">'
    assert _frame_overflow_style(svg) == "align-items: flex-start"


def test_frame_overflow_style_justify_start_when_width_overflows():
    svg = f'<svg width="{FRAME_PX + 200}" height="{FRAME_PX - 1}">'
    assert _frame_overflow_style(svg) == "justify-content: flex-start"


def test_pad1_frame_position_centers_when_svg_fits_both_axes():
    svg = (
        '<svg width="100" height="50">'
        '<g style="fill:#C83434;"><circle cx="2" cy="1" r="0.3"/></g>'
        "</svg>"
    )
    x, y = _pad1_frame_position_px(svg)
    assert x == pytest.approx((FRAME_PX - 100) / 2 + 2 * PX_PER_MM)
    assert y == pytest.approx((FRAME_PX - 50) / 2 + 1 * PX_PER_MM)


def test_pad1_frame_position_flush_to_start_when_axis_overflows():
    # A frame taller than FRAME_PX falls back to flex-start on that axis
    # (see _frame_overflow_style) -- the anchor must use offset 0 there
    # too, not the centered offset, or the grid drifts out of alignment
    # with the pad it's supposed to be locked to.
    tall_height = FRAME_PX + 200
    svg = (
        f'<svg width="100" height="{tall_height}">'
        '<g style="fill:#C83434;"><circle cx="2" cy="300" r="0.3"/></g>'
        "</svg>"
    )
    x, y = _pad1_frame_position_px(svg)
    assert x == pytest.approx((FRAME_PX - 100) / 2 + 2 * PX_PER_MM)
    assert y == pytest.approx(300 * PX_PER_MM)


def test_render_comparison_produces_two_svgs(tmp_path):
    reference_path = f"{KICAD_FOOTPRINTS}/Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod"

    generated_svg, reference_svg = render_comparison(
        "DIP-16", reference_path, str(tmp_path), name="dip16_test",
    )

    assert generated_svg.exists()
    assert reference_svg.exists()
    assert generated_svg.name == "dip16_test_generated.svg"
    assert reference_svg.name == "dip16_test_reference.svg"
    assert "<svg" in generated_svg.read_text()
    assert "<svg" in reference_svg.read_text()


def test_build_review_html_embeds_both_svgs_and_case_metadata(tmp_path):
    reference_path = f"{KICAD_FOOTPRINTS}/Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod"
    generated_svg, reference_svg = render_comparison(
        "DIP-16", reference_path, str(tmp_path), name="dip16_test",
    )
    cases = [{
        "name": "dip16_test",
        "descriptor": "DIP-16",
        "reference_relpath": "Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod",
        "generated_svg": generated_svg,
        "reference_svg": reference_svg,
    }]

    review_path = build_review_html(cases, tmp_path / "review.html")

    text = review_path.read_text()
    assert 'data-name="dip16_test"' in text
    assert "DIP-16" in text
    assert text.count("<svg") >= 2
    assert "Pass (P)" in text
    assert "Fail (F)" in text


def test_review_html_grid_scrolls_with_footprint(tmp_path):
    # Default background-attachment: scroll keeps the grid fixed to the
    # frame's own viewport, ignoring scroll position -- local makes it
    # move with the svg content instead, so it stays visually locked to
    # the footprint on a panel tall/wide enough to scroll.
    reference_path = f"{KICAD_FOOTPRINTS}/Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod"
    generated_svg, reference_svg = render_comparison(
        "DIP-16", reference_path, str(tmp_path), name="dip16_test",
    )
    cases = [{
        "name": "dip16_test",
        "descriptor": "DIP-16",
        "reference_relpath": "Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod",
        "generated_svg": generated_svg,
        "reference_svg": reference_svg,
    }]

    review_path = build_review_html(cases, tmp_path / "review.html")

    assert "background-attachment: local" in review_path.read_text()
