# Changes

2026-09-13 v0.0.3:

* Added a visual comparison tool (`kicad_fpdb/visual_compare.py`):
  renders generated footprints next to their real KiCad references as
  SVGs, and builds a self-contained local HTML page to cycle through
  cases and mark each pass/fail, with a running tally and a summary of
  what needs attention.
* Extracted the regression suite's reference-case list into
  `kicad_fpdb/reference_cases.py` so the tests and the new tool share
  one source of truth.
* Added author and repository URL metadata to `pyproject.toml`.
* Tightened `.gitignore` (`renders/`, `.pytest_cache/`) instead of
  relying on tool-generated ignore files.

2026-09-13 v0.0.2:

* Brainstormed and wrote the design spec for the descriptor + generator engine.
* Wrote the implementation plan (14 tasks) for the engine.
* Implemented the engine: descriptor parser, family-tree loader/resolver,
  three shape-generators (dual-row grid, two-pad chip, quad-perimeter),
  KiCad `.kicad_mod` writer, and pipeline wiring.
* Validated against 12 real KiCad reference footprints across DIP, SOIC,
  R, C, and QFP families; final review fixed 4 gaps (test coverage,
  fail-fast validation, a pad-size type inconsistency, QFP data-model
  documentation.)
* Updated CLAUDE.md's TODO list to reflect the new milestone and known
  follow-up items.

2026-09-13 v0.0.1: Idea born; repo constructed.  First build-wave.
