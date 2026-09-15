import os

import pytest

from kicad_fpdb.reference_cases import KICAD_FOOTPRINTS
from kicad_fpdb.visual_compare import (
    FRAME_PX,
    build_review_html,
    render_comparison,
    _frame_overflow_style,
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
