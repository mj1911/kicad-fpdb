# Changes

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
