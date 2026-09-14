# Changes

2026-09-14 v0.0.6:

* Fixed occluded pad numbers in the review viewer: kicad-cli draws
  drill-hole circles after pad-number text regardless of `--layers`
  selection, painting over them (worst on through-hole pads) — a
  post-processing step now moves pad-number groups to the end of the
  embedded SVG so they always render on top.
* Restricted the review viewer's exported layers to
  `F.Cu,F.SilkS,F.Fab,F.CrtYd` to stop extra mask/paste fill layers
  from covering pad numbers.
* Added pad numbers to the review viewer via kicad-cli's
  `--sketch-pads-on-fab-layers`.
* Switched the review viewer's page chrome to a dark theme, keeping
  each footprint's own frame white (the SVG colors are tuned for a
  light backdrop).
* Enlarged the review viewer's panel/frame from 420x380px to 500x500px
  — outline geometry and long reference filenames were clipping several
  cases.
* Fixed the pin-1 marker triangle to actually point at pad 1's real
  position (computed from the corner-to-pad vector) instead of just
  sitting as a right-angle wedge in the body corner.
* Replaced the pin-1 marker (previously a subtle line notch) with a
  small filled silkscreen triangle, matching real KiCad's own
  convention (confirmed against the SOIC-8 reference file) — much more
  visually obvious.

2026-09-13 v0.0.5:

* Updated CLAUDE.md's TODO list: removed the now-done outline-geometry
  item.
* Added generic courtyard (`F.CrtYd`) and silkscreen body outline
  (`F.SilkS`, with a pin-1 corner marker) geometry to generated
  footprints, built purely from the pad bounding box so it works the
  same way across all three generators. Not a per-family match to real
  KiCad's own outline styles — verified visually via the review tool,
  per the spec's stated approach.
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
* Idea born; repo constructed.  First build-wave.
