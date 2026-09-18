# jedec-fpdb

A spec-derived DIP footprint generator: builds `.kicad_mod` files purely
from JEDEC MS-001 (package body/lead outline) and IPC-7251 Table 3-5
(Dual In-Line Packages thru-hole land pattern sizing), independent of
`kicad-fpdb`'s own reverse-engineered-from-real-files approach at the
repo root. See `docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md`
for the full design rationale.

Currently covers narrow (0.300in/7.62mm row spacing) DIP only, pin
counts 4, 6, 8 (regression-extrapolated -- MS-001's own table starts at
14, see the spec), 14, 16, 18, 20, 22, 24, 28. The extrapolated pin
counts are cross-checked against real KiCad DIP-4/6/8 files in
`tests/test_compare.py`.

## Usage

```bash
cd jedec-fpdb
python -m jedec_fpdb narrow 16                 # writes DIP-16_narrow_N.kicad_mod
python -m jedec_fpdb narrow 8 --density M      # Most (most generous) density level
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

## Scope

Fully independent of `kicad-fpdb`: no shared code, no shared data. See
the design spec's Non-goals and Open follow-ups sections for what's
deliberately out of scope (regular/wide width classes, other package
families, cosmetic silkscreen conventions).
