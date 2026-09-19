"""Shared list of hand-verified real KiCad DIP files this project's
generator is checked against -- one source of truth for both
tests/test_compare.py's numeric diff and visual_compare.py's viewer."""

KICAD_DIP_DIR = "/usr/share/kicad/footprints/Package_DIP.pretty"

# (width_class, pin_count, real filename).
CASES = [
    ("narrow", 4, "DIP-4_W7.62mm.kicad_mod"),
    ("narrow", 6, "DIP-6_W7.62mm.kicad_mod"),
    ("narrow", 8, "DIP-8_W7.62mm.kicad_mod"),
    ("narrow", 14, "DIP-14_W7.62mm.kicad_mod"),
    ("narrow", 16, "DIP-16_W7.62mm.kicad_mod"),
    ("narrow", 24, "DIP-24_W7.62mm.kicad_mod"),
    # regular (.400in / 10.16mm row spacing) -- N=22/24 come directly from
    # MS-010's own table, the rest are regression extrapolation (see
    # test_ms001_dip.py).
    ("regular", 4, "DIP-4_W10.16mm.kicad_mod"),
    ("regular", 6, "DIP-6_W10.16mm.kicad_mod"),
    ("regular", 8, "DIP-8_W10.16mm.kicad_mod"),
    ("regular", 10, "DIP-10_W10.16mm.kicad_mod"),
    ("regular", 12, "DIP-12_W10.16mm.kicad_mod"),
    ("regular", 14, "DIP-14_W10.16mm.kicad_mod"),
    ("regular", 16, "DIP-16_W10.16mm.kicad_mod"),
    ("regular", 22, "DIP-22_W10.16mm.kicad_mod"),
    ("regular", 24, "DIP-24_W10.16mm.kicad_mod"),
    # wide (.600in / 15.24mm row spacing) -- N=24/28/40/48 come directly
    # from MS-011's own table, the rest are regression extrapolation.
    ("wide", 24, "DIP-24_W15.24mm.kicad_mod"),
    ("wide", 26, "DIP-26_W15.24mm.kicad_mod"),
    ("wide", 28, "DIP-28_W15.24mm.kicad_mod"),
    ("wide", 32, "DIP-32_W15.24mm.kicad_mod"),
    ("wide", 40, "DIP-40_W15.24mm.kicad_mod"),
    ("wide", 42, "DIP-42_W15.24mm.kicad_mod"),
    ("wide", 48, "DIP-48_W15.24mm.kicad_mod"),
    ("wide", 64, "DIP-64_W15.24mm.kicad_mod"),
]
