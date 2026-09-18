from jedec_fpdb import dip, writer


def test_write_footprint_contains_expected_tokens(tmp_path):
    fp = dip.generate("narrow", 4, "N")
    out_path = tmp_path / "test.kicad_mod"

    writer.write_footprint(fp, out_path)

    text = out_path.read_text()
    assert text.startswith('(footprint "DIP-4_narrow_N"')
    assert text.count('(pad "') == 4
    assert '(pad "1" thru_hole rect' in text
    assert '(pad "4" thru_hole circle' in text
    assert '(layer "F.SilkS")' in text
    assert '(layer "F.CrtYd")' in text
    pad1 = next(p for p in fp.pads if p.number == 1)
    assert f'(drill {pad1.drill_mm:.4f})' in text
    assert f'(size {pad1.diameter_mm:.4f} {pad1.diameter_mm:.4f})' in text
