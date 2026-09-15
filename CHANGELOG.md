# Changes

2026-09-15 v0.0.9:

* Added `fp_text user "${REFERENCE}"` on `F.Fab` — a separate
  assembly-drawing overlay real KiCad carries on every footprint,
  distinct from the Reference/Value properties. Chip passives get a
  smaller font per package size (`fab_reference_font_size`/
  `_thickness`, hand-copied from real values) since the default 1mm
  font badly overflowed their tiny courtyard.
* Fixed Reference/Value text landing too close to (or visibly
  overlapping, on R-1206) the courtyard on several chip-passive sizes:
  the 0.05in grid snap rounded to the *nearest* multiple, which could
  round inward and shrink the intended 0.7mm gap. Now rounds only
  outward (away from the part), guaranteeing the full clearance for
  every family.
* Removed the pin-1 circle marker from DIP packages — DIP already has
  a square pin-1 pad and a silk notch, so a third indicator was
  redundant. `pin1_marker: false` in `data/kicad-fpdb.yaml`, same
  mechanism R/C already use; SOIC and QFP are unaffected.
* Changed SOIC's F.SilkS to two horizontal lines (top/bottom body
  edges only, no vertical sides) instead of a closed rectangle,
  matching real KiCad's own SOIC silk convention. New opt-in
  `silk_two_lines` param on the existing body_width/body_margin
  branch; DIP is unaffected.
* Fixed review viewer panels permanently hiding part of a footprint
  taller or wider than the 500px frame (e.g. DIP-24 w): scrolling down
  reached the bottom fine, but scrolling up always cut off the top a
  couple mm. Falls back from centered to flex-start on whichever axis
  overflows, since `overflow:auto`'s default scroll origin can't reach
  the start-side half of a centered, overflowing flex item.
* Fixed the dot-grid/checkerboard drifting off pin 1 on exactly those
  overflow-fixed panels — the anchor math still assumed the svg was
  always centered.
* Fixed the dot-grid/checkerboard staying fixed to the frame's
  viewport while scrolling instead of moving with the footprint
  (`background-attachment: local` instead of the CSS default
  `scroll`).
* Fixed each panel's grid drifting ~0.21mm off its own pad 1 on
  DIP-18/DIP-24 w: it shared one anchor derived only from the
  reference svg, but `kicad-cli` assigns each exported svg its own
  coordinate origin from that file's own bounding box, and the
  generated file's pin-1 marker circle (a feature the reference
  doesn't have) shifts it relative to the reference. Each panel is
  now anchored to its own pad 1 independently. Purely a viewer
  artifact — the actual generated pad positions already match the
  real library exactly (0.0mm delta, verified separately).
* Widened `data/kicad-fpdb.yaml` coverage with 6 new hand-verified
  variants: DIP-24 w (first verified case for DIP's wide width class),
  SOIC-16 (third verified pin count), and four new chip-passive sizes
  (R-0201, R-1206, C-0402, C-0805) — 18 reference cases total, up from
  12.
* Added a `no_silk` outline option for chip passives too small for a
  real silk outline at all (R-0201 is the first to use it).
* Fixed `roundrect_rratio` to clamp to an absolute 0.25mm max corner
  radius (matching real KiCad) instead of a flat 0.25 ratio for every
  generator — closes a previously parked TODO item, surfaced concretely
  by R-1206's 1.125mm pad.
* Review viewer panel titles now show which case is on screen
  ("Generator: DIP-16" / "Reference: Package_DIP.pretty/
  DIP-16_W7.62mm.kicad_mod"), and dropped the now-redundant
  descriptor-vs-reference line above the panels.
* Reference/Value text now sits 0.7mm outside the real silk/courtyard
  outline (matching real KiCad's own convention, which the previous
  flat 1.0mm-from-pad-bbox margin predates) rather than the pin-1
  marker circle (an ornament with no real-KiCad equivalent), with both
  coordinates snapped to the nearest 0.05in grid point.
* Gave SOIC and QFP their real stepped `F.CrtYd` courtyard shape (union
  of the true physical body outline and one pad-bbox arm per side,
  each expanded by a flat 0.25mm margin) via a new generic
  `kicad_fpdb/rect_union.py` rectangle-union utility, verified exactly
  against SOIC-8, SOIC-14, LQFP-32, and LQFP-48 real reference
  footprints.
* Fixed chip-passive (R/C) courtyard margins to their real per-variant
  values (0.15mm for R-0402, 0.25mm for R-0603/R-0805/C-0603),
  replacing the generic flat 0.5mm fallback — a data-only change, no
  shape change needed.
* Fixed the new stepped courtyard lines rendering at the wrong stroke
  width (0.12mm silkscreen-line default instead of real KiCad's
  0.05mm courtyard stroke) — caught by eye in the review viewer.
* Fixed a review-viewer-only display bug where a stepped courtyard's
  outer edge could vanish entirely on one side (seen on QFP-32/48 and
  SOIC-14): `kicad-cli`'s exported SVG viewBox wraps path centerlines
  with no stroke-width margin, so a hairline stroke sitting exactly on
  that boundary had its outer half clipped by the SVG viewport. The
  underlying `.kicad_mod` geometry was already correct; fixed by
  padding the embedded SVG's viewBox in `visual_compare.py`.
* Added a design spec for the courtyard work
  (`docs/superpowers/specs/2026-09-15-stepped-courtyard-design.md`).
* Confirmed neither the library nor generated pads declare an explicit
  solder mask/paste margin override on any of the 12 reference
  footprints checked — both just opt into the board's default
  expansion. Noted as a possible future per-footprint modifier in the
  TODO list.

2026-09-14 v0.0.8:

* Pushed the repo to GitHub (`mj1911/kicad-fpdb`) to work across machines.
* Review viewer: anchored both the checkerboard and dot-grid backgrounds to
  pad 1's true geometric center (taken from the first F.Cu-colored pad
  shape in document order in the reference SVG, not the pad-number text,
  which has a variable baseline offset from the true center), applied
  identically to the generated and reference panels — so any misalignment
  of the generated footprint's own pad 1 against that shared grid is now
  a visible signal. Fixed `.frame` to a true 500x500px square (previously
  only height was fixed) so the anchor lines up correctly in both panels.
* Review viewer: added a grey/white dot-grid overlay at standard 0.1in
  (2.54mm) pitch on top of the existing 0.5mm checkerboard, as a second
  scale reference at a more familiar perfboard/breadboard spacing.
* Added a terse "Under Construction" `README.md` for GitHub.
* Left a design question comment in `data/kicad-fpdb.yaml` on whether
  `two_pad_chip` should move to `params` (rather than being called out
  per-family) to accommodate future through-hole resistor variants —
  unresolved, for a later session.
* Updated CLAUDE.md's TODO list with follow-ups surfaced this session
  (matching SOIC's real stepped courtyard shape; generalizing the pin-1
  marker's "above pad 1" direction assumption for a future family with
  pin 1 on a non-top edge).
* Added a real semicircular notch to DIP's F.SilkS outline (radius
  1.0mm, centered at the body's horizontal center) — real KiCad's
  DIP pin-1-side indicator, confirmed constant across every pin count
  and row-spacing width checked; SOIC shares the same rectangle branch
  but correctly gets no notch, since real SOIC footprints have none.
  Added a generic `Arc` geometry primitive and `fp_arc` writer support.
* Fixed the pin-1 marker circle overlapping its own pad: the clearance
  offset moved the circle's center away from the pad edge but never
  accounted for the circle's own radius extending back toward it; also
  widened the clearance to comfortably clear typical solder-mask
  expansion, which isn't otherwise modeled in this project's data.
* Replaced the pin-1 marker — previously a triangle anchored to the
  F.SilkS outline's nearest corner — with a filled circle anchored
  purely to pad 1's own position, always directly above it, regardless
  of outline mode; this let the now-dead corner-anchoring helper be
  removed entirely. Added a generic `Circle` geometry primitive and
  `fp_circle` writer support.
* Tightened DIP's courtyard margin to real KiCad's asymmetric values
  (0.25mm perpendicular to the pin rows, 0.72mm along them) instead of
  the generic flat 0.5mm margin still used by every other family.
* Gave R and C (chip passives) a real two-line F.SilkS outline —
  matching real KiCad's chip-resistor/capacitor convention, since the
  component body is always smaller than its pads — instead of a
  generic pad-bounding-box rectangle; each variant's line position and
  length is copied verbatim from its real reference footprint.
* Turned off the pin-1 marker for R and C (resistors are never
  polarized; capacitors only occasionally are) via a new `pin1_marker`
  opt-out flag, declared once per family and inherited by every child;
  a future polarized capacitor variant can opt back in.
* Gave QFP real corner-mark F.SilkS brackets instead of a generic
  pad-bounding-box rectangle, matching real KiCad's own QFP silk
  convention (fixed leg length shared across variants; real values
  differ slightly per package).
* Gave DIP and SOIC a real body-derived F.SilkS rectangle
  (`body_width`/`body_margin`) instead of a generic pad-bounding-box
  rectangle — DIP's body width is keyed by row-spacing width class,
  matching real KiCad almost exactly. Also made the review viewer's
  frame background black with a grey checkerboard, and fixed a bug
  where moving pad-number/REF**/value text groups to the top of the
  SVG dropped the styled wrapper carrying their stroke color, making
  them invisible against any background.
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
