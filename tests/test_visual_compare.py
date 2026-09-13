import os

import pytest

from kicad_fpdb.reference_cases import KICAD_FOOTPRINTS
from kicad_fpdb.visual_compare import build_review_html, render_comparison, _raise_pad_numbers_on_top

pytestmark = pytest.mark.skipif(
    not os.path.isdir(KICAD_FOOTPRINTS),
    reason=f"{KICAD_FOOTPRINTS} not present on this machine",
)


def test_raise_pad_numbers_on_top_moves_stroked_text_after_later_content():
    svg = (
        '<svg>'
        '<g class="stroked-text"><desc>1</desc><path d="M0 0" /></g>'
        '<circle cx="1" cy="1" r="1" />'
        '</svg>'
    )
    result = _raise_pad_numbers_on_top(svg)
    assert result.index('<g class="stroked-text">') > result.index("<circle")


def test_raise_pad_numbers_on_top_is_a_noop_without_stroked_text():
    svg = "<svg><circle cx=\"1\" cy=\"1\" r=\"1\" /></svg>"
    assert _raise_pad_numbers_on_top(svg) == svg


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
