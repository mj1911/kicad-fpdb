from jedec_fpdb.__main__ import main


def test_cli_writes_a_kicad_mod_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["narrow", "16"])

    assert exit_code == 0
    out_file = tmp_path / "DIP-16_narrow_N.kicad_mod"
    assert out_file.exists()
    assert out_file.read_text().count('(pad "') == 16


def test_cli_accepts_density_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    main(["narrow", "8", "--density", "M"])

    assert (tmp_path / "DIP-8_narrow_M.kicad_mod").exists()
