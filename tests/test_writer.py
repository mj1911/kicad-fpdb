import shutil
import subprocess

import pytest

from kicad_fpdb.geometry import FootprintGeometry, Pad
from kicad_fpdb.writer import write_kicad_mod


def test_write_pad_thru_hole_with_drill():
    pad = Pad(number="1", pad_type="thru_hole", shape="roundrect",
               at=(0.0, 0.0), size=(1.6, 1.6), drill=0.8, roundrect_rratio=0.15625)
    geom = FootprintGeometry(name="TEST_MIN", pads=[pad])
    text = write_kicad_mod("TEST_MIN", geom)
    assert '(footprint "TEST_MIN"' in text
    assert '(pad "1" thru_hole roundrect' in text
    assert "(at 0 0)" in text
    assert "(size 1.6 1.6)" in text
    assert "(drill 0.8)" in text
    assert '(layers "*.Cu" "*.Mask")' in text
    assert "(roundrect_rratio 0.15625)" in text


def test_write_pad_smd_no_drill():
    pad = Pad(number="2", pad_type="smd", shape="roundrect",
               at=(0.825, 0.0), size=(0.8, 0.95), roundrect_rratio=0.25)
    geom = FootprintGeometry(name="TEST_SMD", pads=[pad])
    text = write_kicad_mod("TEST_SMD", geom)
    assert '(pad "2" smd roundrect' in text
    assert "(drill" not in text
    assert '(layers "F.Cu" "F.Mask" "F.Paste")' in text


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_generated_file_is_valid_kicad_mod(tmp_path):
    pad1 = Pad(number="1", pad_type="thru_hole", shape="roundrect",
                at=(0.0, 0.0), size=(1.6, 1.6), drill=0.8, roundrect_rratio=0.15625)
    pad2 = Pad(number="2", pad_type="thru_hole", shape="circle",
                at=(0.0, 2.54), size=(1.6, 1.6), drill=0.8)
    geom = FootprintGeometry(name="TEST_MIN", pads=[pad1, pad2])
    text = write_kicad_mod("TEST_MIN", geom)

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "TEST_MIN.kicad_mod").write_text(text)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = subprocess.run(
        ["kicad-cli", "fp", "export", "svg", "--footprint", "TEST_MIN",
         str(lib_dir), "-o", str(out_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out_dir / "TEST_MIN.svg").exists()
