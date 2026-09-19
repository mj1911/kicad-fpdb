# jedec-fpdb

A spec-derived DIP footprint generator: builds `.kicad_mod` files purely
from JEDEC MS-001/MS-010/MS-011 (package body/lead outline) and IPC-7251
Table 3-5 (Dual In-Line Packages thru-hole land pattern sizing),
independent of `kicad-fpdb`'s own reverse-engineered-from-real-files
approach at the repo root. See
`docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md` for the
full design rationale.

Covers all three plastic DIP width classes: narrow (0.300in/7.62mm row
spacing, MS-001), regular (0.400in/10.16mm, MS-010), and wide
(0.600in/15.24mm, MS-011). Pin counts outside each class's own documented
table are regression-extrapolated (see the spec) and cross-checked
against real KiCad files in `tests/test_compare.py`.

## Usage

```bash
cd jedec-fpdb
python -m jedec_fpdb narrow 16                 # writes DIP-16_narrow_N.kicad_mod
python -m jedec_fpdb narrow 8 --density M      # Most (most generous) density level
python -m jedec_fpdb regular 24
python -m jedec_fpdb wide 40
```

## Tests

```bash
cd jedec-fpdb
python -m pytest -v
```

`tests/test_compare.py` diffs generated output against real KiCad
reference files and is skipped automatically if
`/usr/share/kicad/footprints/Package_DIP.pretty` isn't present on the
machine.

## Visual review

```bash
cd jedec-fpdb
python -m jedec_fpdb.visual_compare
```

Opens an interactive Tkinter window cycling through every case in
`jedec_fpdb/reference_cases.py`, rendering the generated footprint next
to its real KiCad reference at matched physical scale (checkerboard +
0.1in dot-grid background as a ruler). Prev/Next (buttons or Left/Right
arrows), Pass/Fail (buttons or P/F) to mark each case; closing the
window prints a summary of failed/unmarked cases to the terminal (marks
aren't persisted to disk). Requires `kicad-cli` and `rsvg-convert` on
PATH in addition to the real KiCad footprint library.

## Scope

Fully independent of `kicad-fpdb`: no shared code, no shared data. See
the design spec's Non-goals and Open follow-ups sections for what's
deliberately out of scope (other DIP width classes like extra_wide,
other package families, cosmetic silkscreen conventions).
