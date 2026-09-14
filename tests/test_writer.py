import shutil
import subprocess

import pytest

from kicad_fpdb.geometry import Arc, Circle, FootprintGeometry, Line, Pad, Poly, Rect, Text
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


def test_write_reference_and_value_text():
    geom = FootprintGeometry(name="TEST_MIN", texts=[
        Text(kind="reference", text="REF**", at=(3.81, -2.33), layer="F.Fab"),
        Text(kind="value", text="TEST_MIN", at=(3.81, 20.11), layer="F.Fab"),
    ])
    text = write_kicad_mod("TEST_MIN", geom)
    assert '(property "Reference" "REF**"' in text
    assert '(property "Value" "TEST_MIN"' in text
    assert "(at 3.81 -2.33 0)" in text
    assert "(at 3.81 20.11 0)" in text
    assert text.count('(layer "F.Fab")') == 2


def test_write_line():
    line = Line(start=(0.0, 0.0), end=(1.0, 2.0), layer="F.SilkS", width=0.12)
    geom = FootprintGeometry(name="TEST_MIN", lines=[line])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_line" in text
    assert "(start 0 0)" in text
    assert "(end 1 2)" in text
    assert "(width 0.12)" in text
    assert '(layer "F.SilkS")' in text


def test_write_rect():
    rect = Rect(start=(-0.5, -0.5), end=(5.0, 3.0), layer="F.CrtYd", width=0.05)
    geom = FootprintGeometry(name="TEST_MIN", rects=[rect])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_rect" in text
    assert "(start -0.5 -0.5)" in text
    assert "(end 5 3)" in text
    assert "(width 0.05)" in text
    assert "(fill no)" in text
    assert '(layer "F.CrtYd")' in text


def test_write_poly():
    poly = Poly(points=[(0.0, 0.0), (0.5, 0.0), (0.0, 0.5)], layer="F.SilkS")
    geom = FootprintGeometry(name="TEST_MIN", polys=[poly])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_poly" in text
    assert "(pts" in text
    assert "(xy 0 0)" in text
    assert "(xy 0.5 0)" in text
    assert "(xy 0 0.5)" in text
    assert "(fill yes)" in text
    assert '(layer "F.SilkS")' in text


def test_write_circle():
    circle = Circle(center=(0.0, -1.0), radius=0.3, layer="F.SilkS")
    geom = FootprintGeometry(name="TEST_MIN", circles=[circle])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_circle" in text
    assert "(center 0 -1)" in text
    assert "(end 0.3 -1)" in text
    assert "(fill yes)" in text
    assert '(layer "F.SilkS")' in text


def test_write_arc():
    arc = Arc(start=(4.81, -1.33), mid=(3.81, -0.33), end=(2.81, -1.33), layer="F.SilkS")
    geom = FootprintGeometry(name="TEST_MIN", arcs=[arc])
    text = write_kicad_mod("TEST_MIN", geom)
    assert "(fp_arc" in text
    assert "(start 4.81 -1.33)" in text
    assert "(mid 3.81 -0.33)" in text
    assert "(end 2.81 -1.33)" in text
    assert '(layer "F.SilkS")' in text


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_generated_file_is_valid_kicad_mod(tmp_path):
    pad1 = Pad(number="1", pad_type="thru_hole", shape="roundrect",
                at=(0.0, 0.0), size=(1.6, 1.6), drill=0.8, roundrect_rratio=0.15625)
    pad2 = Pad(number="2", pad_type="thru_hole", shape="circle",
                at=(0.0, 2.54), size=(1.6, 1.6), drill=0.8)
    geom = FootprintGeometry(
        name="TEST_MIN", pads=[pad1, pad2],
        texts=[
            Text(kind="reference", text="REF**", at=(0.8, -1.0), layer="F.Fab"),
            Text(kind="value", text="TEST_MIN", at=(0.8, 3.5), layer="F.Fab"),
        ],
        lines=[Line(start=(-0.5, -0.5), end=(2.0, -0.5), layer="F.SilkS")],
        rects=[Rect(start=(-1.0, -1.0), end=(2.5, 3.0), layer="F.CrtYd")],
        polys=[Poly(points=[(-0.5, -0.5), (0.0, -0.5), (-0.5, 0.0)], layer="F.SilkS")],
        circles=[Circle(center=(0.0, -1.5), radius=0.3, layer="F.SilkS")],
        arcs=[Arc(start=(1.0, -0.5), mid=(0.5, -1.0), end=(0.0, -0.5), layer="F.SilkS")],
    )
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
