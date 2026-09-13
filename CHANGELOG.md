# Changes

2026-09-13 v0.0.5:

* Updated CLAUDE.md's TODO list: removed the now-done outline-geometry
  item.
* Added generic courtyard (`F.CrtYd`) and silkscreen body outline
  (`F.SilkS`, with a pin-1 corner marker) geometry to generated
  footprints, built purely from the pad bounding box so it works the
  same way across all three generators. Not a per-family match to real
  KiCad's own outline styles — verified visually via the review tool,
  per the spec's stated approach.

2026-09-13 v0.0.4:

* Updated CLAUDE.md's TODO list: flagged the silkscreen/outline gap as
  more conspicuous now that Reference sits on `F.SilkS`.
* Added Reference ("REF**") and Value (the footprint's own name) text
  properties to generated footprints, placed above/below the pad
  bounding box; Reference on `F.SilkS`, Value on `F.Fab`, matching real
  KiCad's layer convention.
* Visual review tool: each footprint is centered within a fixed-size
  viewport frame, like KiCad's own footprint editor.
* Visual review tool: both panels now render at matched true physical
  scale (20px/mm) with a fine checkerboard scale reference behind them,
  instead of each footprint being independently resized to fit its panel
  (which hid real size discrepancies).

2026-09-13 v0.0.3:

* Tightened `.gitignore` (`renders/`, `.pytest_cache/`) instead of
  relying on tool-generated ignore files.
* Added author and repository URL metadata to `pyproject.toml`.
* Extracted the regression suite's reference-case list into
  `kicad_fpdb/reference_cases.py` so the tests and the new tool share
  one source of truth.
* Added a visual comparison tool (`kicad_fpdb/visual_compare.py`):
  renders generated footprints next to their real KiCad references as
  SVGs, and builds a self-contained local HTML page to cycle through
  cases and mark each pass/fail, with a running tally and a summary of
  what needs attention.

2026-09-13 v0.0.2:

* Updated CLAUDE.md's TODO list to reflect the new milestone and known
  follow-up items.
* Validated against 12 real KiCad reference footprints across DIP, SOIC,
  R, C, and QFP families; final review fixed 4 gaps (test coverage,
  fail-fast validation, a pad-size type inconsistency, QFP data-model
  documentation.)
* Implemented the engine: descriptor parser, family-tree loader/resolver,
  three shape-generators (dual-row grid, two-pad chip, quad-perimeter),
  KiCad `.kicad_mod` writer, and pipeline wiring.
* Wrote the implementation plan (14 tasks) for the engine.
* Brainstormed and wrote the design spec for the descriptor + generator engine.

2026-09-13 v0.0.1:

* Idea born; repo constructed.  First build-wave.
