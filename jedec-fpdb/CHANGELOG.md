# Changes

2026-09-19 v0.1.0:

* Wired up `pytest-xdist` (`dev` extra + `addopts = "-n 6"` in
  `pyproject.toml`), matching `kicad-fpdb`'s own existing setup, so both
  projects' test suites run multi-process consistently. Verified: 101
  tests passed in ~3.5s.
* Backfilled this CHANGELOG.md and fleshed out CLAUDE.md from the full
  git history and design docs — this project previously had neither.

2026-09-18 v0.1.0:

* Added `regular` (JEDEC MS-010, 0.400in/10.16mm row spacing) and `wide`
  (MS-011, 0.600in/15.24mm) DIP width classes alongside the existing
  narrow (MS-001) class, once real copies of those documents became
  available. `data/ms001_dip.py` restructured from flat module
  constants into a `_WidthClass` dataclass keyed by width class.
  Pin-count coverage for each grounded in which real KiCad files
  actually exist, reusing narrow's existing linear-regression
  extrapolation for pin counts outside each class's own documented
  table. 17 new comparison cases against real KiCad files confirm the
  same drill/pad-diameter pattern already found for narrow holds
  independent of width class; courtyard height flips sign for wide
  (real KiCad gives wide-body DIPs more vertical courtyard headroom
  than the flat excess-plus-round-up formula produces) — a new
  observation.
* Fixed a real transcription bug: `LEAD_WIDTH_MAX_MM` had been
  hand-computed from MS-001's 0.022in and typed as a rounded `0.559`,
  not the exact `0.5588`. Every constant in `ms001_dip.py` is now
  computed from its documented inch value in code instead of by hand.
  A second, silently-uncorrected copy of the same stale value was also
  hardcoded in `test_ipc7251.py` — fixed to import the real constant
  instead so it can't drift again.
* Documented the `extra_wide`/`ultra_wide` DIP source-data gap: no
  plastic-DIP JEDEC outline document exists yet for 0.900in/1.000in row
  spacing in this project's `JEDEC/` collection. The one 0.900in
  document present (MS-015a) is for ceramic side-brazed DIPs (CERDIP),
  a different package family, deliberately not adapted as a plastic
  stand-in.
* Added an interactive Tkinter viewer
  (`python -m jedec_fpdb.visual_compare`) cycling through every case in
  a new `jedec_fpdb/reference_cases.py` (extracted from
  `test_compare.py`'s own case list, now shared by both — 23 cases:
  6 narrow + 9 regular + 8 wide), rasterizing generated vs. real
  footprints side by side at matched physical scale with a
  checkerboard/dot-grid ruler background, mirroring `kicad-fpdb`'s own
  review-viewer conventions.
* Fixed the pad-1 grid anchor, which had been computed by subtracting
  the exported SVG's viewBox origin from the raw `.kicad_mod`
  coordinate — wrong, since `kicad-cli`'s SVG export doesn't preserve a
  footprint's own local coordinate frame. Replaced with locating pad 1
  directly in the rendered SVG by its copper-fill color, the same
  technique `kicad-fpdb`'s own viewer already uses.
* Anchored both viewer panels' grid to the real reference file's own
  pad 1 (instead of each panel self-aligning to its own pad 1) — this
  is what actually surfaces a genuine placement mismatch between
  jedec-fpdb's simpler silk body and the real file's bounding box.
* Parallelized the viewer's per-case rendering via a thread pool (each
  case is 4 independent I/O-bound subprocess calls) — ~11.6s → ~0.9s
  for all 23 cases.
* The viewer now terminates any other running instance of itself on
  launch, so re-launching by hand or via the VS Code task doesn't pile
  up duplicate windows.
* Fixed the checkerboard/dot-grid pitch not shrinking along with a
  downscaled panel (e.g. DIP-24, taller than the viewer's frame) — only
  the shared anchor pixel lined up before; every other pad drifted
  off-grid.
* Fixed each panel computing its own independent downscale factor
  instead of one shared factor for the whole case — this had silently
  broken both grid-pitch alignment between panels and the viewer's
  "matched true physical scale" comparison itself. Replaced with one
  shared scale (from whichever image needs the most shrinking to fit)
  plus per-panel centering at that scale.

2026-09-17 v0.1.0:

* Added the design spec for jedec-fpdb: a DIP footprint generator built
  purely from JEDEC MS-001 + IPC-7251 formulas, with no reference to
  real KiCad files as a data source — the deliberate opposite of
  `kicad-fpdb`'s own reverse-engineered-from-real-files approach. Real
  reference files are used only afterward, read-only, as a comparison
  baseline.
* Narrowed the initial scope to MS-001's narrow (0.300in/7.62mm) width
  class only, after reading the real document surfaced that it doesn't
  cover regular/wide, and that its body-length table has no N=8 entry
  (computed instead via linear regression over the table's own
  N=14–28 values).
* Added the six-task TDD implementation plan.
* Replaced an initial best-effort IPC-7251 approximation with the real
  Table 3-5 ("Dual In-Line Packages") values once a real copy of the
  standard was located: annular ring excess is added directly to the
  drill diameter (not doubled), courtyard excess is density-dependent,
  and courtyard dimensions round up to the nearest 0.10mm.
* Built the engine end to end: project scaffolding + the JEDEC MS-001
  DIP data table, the IPC-7251 Table 3-5 sizing formulas, geometry
  primitives + the DIP generator (`dip.py`), the `.kicad_mod` writer,
  the real-file comparison tool (`compare.py`), and a CLI entry point +
  README (`python -m jedec_fpdb <width_class> <pin_count>`).
* Extended body-length extrapolation test coverage to DIP-4 and DIP-6.
* Documented `compare.diff()`'s findings against the real KiCad
  library in the design spec: pitch and row spacing match exactly
  (both are JEDEC Basic dimensions); real KiCad's drill diameter
  tracks IPC-7251's "Most" (Level A) density level almost exactly, but
  its pad diameter exceeds every density level, including Most — real
  KiCad is standards-aligned on hole sizing but consistently more
  generous on annular ring; courtyard height varies non-monotonically
  with pin count, mirroring MS-001's own non-linear body-length table.
