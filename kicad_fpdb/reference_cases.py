"""Known descriptor -> real KiCad reference footprint pairs.

Shared by the pipeline regression suite (tests/test_pipeline_regression.py)
and the visual comparison tool (kicad_fpdb/visual_compare.py) so both use
the same single list of hand-verified cases.
"""

FAMILY_TREE_PATH = "data/kicad-fpdb.yaml"
KICAD_FOOTPRINTS = "/usr/share/kicad/footprints"

CASES = [
    # (descriptor, real reference file relative to KICAD_FOOTPRINTS)
    ("DIP-16", "Package_DIP.pretty/DIP-16_W7.62mm.kicad_mod"),
    ("DIP-14", "Package_DIP.pretty/DIP-14_W7.62mm.kicad_mod"),
    ("DIP-18", "Package_DIP.pretty/DIP-18_W7.62mm.kicad_mod"),
    ("DIP-16 r", "Package_DIP.pretty/DIP-16_W10.16mm.kicad_mod"),
    ("DIP-24 w", "Package_DIP.pretty/DIP-24_W15.24mm.kicad_mod"),
    ("SOIC-8", "Package_SO.pretty/SOIC-8_3.9x4.9mm_P1.27mm.kicad_mod"),
    ("SOIC-14", "Package_SO.pretty/SOIC-14_3.9x8.7mm_P1.27mm.kicad_mod"),
    ("SOIC-16", "Package_SO.pretty/SOIC-16_3.9x9.9mm_P1.27mm.kicad_mod"),
    ("R-0201", "Resistor_SMD.pretty/R_0201_0603Metric.kicad_mod"),
    ("R-0402", "Resistor_SMD.pretty/R_0402_1005Metric.kicad_mod"),
    ("R-0603", "Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod"),
    ("R-0805", "Resistor_SMD.pretty/R_0805_2012Metric.kicad_mod"),
    ("R-1206", "Resistor_SMD.pretty/R_1206_3216Metric.kicad_mod"),
    ("C-0402", "Capacitor_SMD.pretty/C_0402_1005Metric.kicad_mod"),
    ("C-0603", "Capacitor_SMD.pretty/C_0603_1608Metric.kicad_mod"),
    ("C-0805", "Capacitor_SMD.pretty/C_0805_2012Metric.kicad_mod"),
    ("QFP-32", "Package_QFP.pretty/LQFP-32_7x7mm_P0.8mm.kicad_mod"),
    ("QFP-48", "Package_QFP.pretty/LQFP-48_7x7mm_P0.5mm.kicad_mod"),
]
