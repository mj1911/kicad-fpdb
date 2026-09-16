# User-defined project goals

* KiCAD dev website (reference): https://dev-docs.kicad.org/en/
* KiCAD add-on specifics: https://dev-docs.kicad.org/en/addons/

Currently, KiCAD ships thousands of footprint files in their library, each
differing by various amounts, many nearly identical.  This is highly
inefficient and limiting, since if a footprint doesn't exist in the library,
one must be created manually.  Footprints are inherently classed; a DIP-16
footprint is very similar to a DIP-18 footprint and differs by only two pins
in a highly-defined way, yet the current implementation means two completely
separate geometry-files to represent nearly identical data.

I'd like to develop a plug-in or add-on to KiCAD which completely changes
the existing footprint paradigm, and offers a much smaller and more efficient
solution - build footprints on-demand, from a database/tree of condensed
footprint info.  If a user wants a desired footprint but it does not exist
yet, pick a similar one and define the changes from a series of questions.
This can't break existing KiCAD workflows; this must be a new workflow.

1. Back-end: instead of having each footprint as a separate file which the
user picks, instead lets build a database or tree of footprints, as text
specifiers, which inherit parent attributes.  This is going to require a
lot of investigation and optimization.  I'm not 100% sure how a specifier
would look yet, but perhaps something like 'DIP-16 r 2.54', where DIP
completely defines a dual-inline-package, 16 is the (variable) number of
pins, 'r' means regular-width (as opposed to narrow or wide), and 2.54 is
the pin spacing in mm (perhaps superfluous for DIP, but a necessity for
some of the other footprint styles.)
2. The entire existing footprint library is converted into this new
(condensed, hierarchical-descriptor) format.  Now when the user wants to
assign a footprint, they use this tool to search for 'dip', find an exact
'dip-16' match, pick it, and the footprint geometry file is created
on-demand and assigned to the component.
3. The new (condensed, hierarchical-descriptor) footprint library
(concept title is 'kicad-fpdb' = footprint database) is a single file
which can be updated regularly.
4. Later milestone: this 'fpdb' must be field-updateable.  As users
generate new footprints, they are asked if they want to contribute their
new ones (once per year, or via an upload button.)  If the user agrees,
their new footprints are uploaded to a server, awaiting moderator review.
If a moderator approves them, they are added to the global database/tree,
and become available for everyone to automatically update to.

## Claude-isms below

* Working across machines (e.g. after moving this folder to another
  computer): this repo was developed against KiCad 10.0.6 on Linux, with
  `kicad-cli` on PATH and the official footprint library at
  `/usr/share/kicad*/footprints/*.pretty`. On a new machine:
  * Run `pip install -e ".[dev]"` again — the editable install isn't part
    of the repo and won't follow the folder.
  * If the repo lives on a FAT32/exFAT drive (e.g. a flash drive), don't
    put the venv inside the repo — FAT has no symlinks and no exec
    permission bits, so `virtualenv`/`venv` creation fails there with a
    `PermissionError` on the python symlink. Create the venv elsewhere
    (e.g. `~/.venvs/kicad-fpdb`) and `pip install -e` the project from
    its path on the drive instead; this has no effect on the repo itself.
  * If the system Python has no `pip` module (e.g. Arch/Manjaro's
    externally-managed Python), use `virtualenv -p python3 <path>` to
    create a venv (it bundles its own pip), then use that venv's
    `bin/pip` / `bin/python` for everything above.
  * If KiCad isn't installed at the same path (different OS, different
    KiCad version, or not installed at all), every test that depends on
    it — the pipeline regression suite, the kicad-cli round-trip test in
    `tests/test_writer.py`, `tests/test_visual_compare.py` — skips
    gracefully rather than failing (all guarded with `pytest.mark.skipif`).
    Core unit tests (geometry, descriptor, family_tree, generators) don't
    need KiCad at all.
  * `python -m kicad_fpdb.visual_compare` needs `kicad-cli` on PATH to do
    anything; without it, it'll error clearly rather than silently.
  * Nothing in the tracked code hardcodes this machine's absolute path —
    verified via `grep -rn "/media/sda1"` before the move — so a plain
    folder copy (not just a git clone) is safe.
  * `.worktrees/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, and
    `renders/` are all gitignored and disposable; fine to delete before
    copying to save space, or just let them come along.
* Design specs live in `docs/superpowers/specs/`. First spec: descriptor
  language + generator engine (`2026-09-13-descriptor-engine-design.md`).
  Scoped deliberately to exclude the KiCad plugin, full-library conversion,
  and the contribution/moderation server — those get their own specs later.
* Local KiCad is installed (`kicad-cli`, `/usr/share/kicad*/footprints/*.pretty`)
  — use these as ground truth for footprint format and validation, rather
  than guessing at S-expression conventions.
* Engine language: Python, chosen partly because it matches KiCad's own
  pcbnew scripting API for eventual plugin integration.
* This repo was git-initialized on 2026-09-13 (it did not exist before).
* First milestone complete (2026-09-13): the descriptor + generator engine
  (`kicad_fpdb/`) exists and is validated against 12 real KiCad reference
  footprints across DIP, SOIC, R, C, and QFP. Implementation plan and specs
  are in `docs/superpowers/specs/` and `docs/superpowers/plans/` — read
  those before extending the engine, they carry the design rationale.
* Visual review tool exists: `python -m kicad_fpdb.visual_compare` renders
  all known reference cases (or an ad-hoc `--descriptor`/`--reference`
  pair) into a local `renders/review.html` page for side-by-side pass/fail
  review, with both panels at matched true physical scale (20px/mm) in a
  500x500px frame with a checkerboard scale reference, pad numbers shown
  on both panels, and a dark-themed page chrome (the frame background is
  black with a grey checkerboard — note that real KiCad's SVG export
  draws silkscreen/outline strokes in black, so those are only visible
  against a light backdrop; on this dark frame only the copper pads
  reliably show up). Use this instead of ad-hoc SVG exports when
  eyeballing generator output — regenerate it after any change to
  `kicad_fpdb/visual_compare.py`. Embedded SVGs get their viewBox
  padded slightly (`SVG_VIEWBOX_PAD_MM`, far edge only, origin
  untouched) before inlining: `kicad-cli`'s exported viewBox wraps path
  centerlines exactly with no stroke-width allowance, and a hairline
  courtyard line sitting right on that boundary (routine now that a
  stepped courtyard's own arm is often the single widest feature) had
  its outer half clipped by the SVG viewport's default
  `overflow:hidden` — invisible at this tool's ~1px render scale.
  Discovered on QFP-32/48 and SOIC-14's right-edge courtyard line
  going missing. Panels for a footprint taller/wider than the 500px
  frame (e.g. DIP-24 w at 696px tall) also fall back from centered to
  `flex-start` on whichever axis overflows (`_frame_overflow_style`):
  `.frame`'s flex-centering splits overflow evenly on both sides, but
  `overflow:auto`'s default scroll origin can only reach the end-side
  half, permanently hiding the start-side half (a tall footprint's top
  edge) — axes that fit stay centered as before. `_pad1_frame_position_px`
  (the dot-grid/checkerboard anchor) applies this same per-axis
  centered-vs-flex-start condition, or the grid drifts off pin 1 on
  exactly the panels the overflow fix touches. The grid's
  `background-attachment` is `local`, not the CSS default `scroll`, so
  it scrolls together with the svg content instead of staying fixed to
  the frame's own viewport while the footprint scrolls underneath it.
  Each panel's grid is anchored to that panel's *own* pad 1
  (`_pad1_frame_position_px` called separately on the generated and
  reference markup), not a single anchor shared from the reference —
  `kicad-cli` assigns each exported svg its own viewBox origin from
  that file's own bounding box, and the generated file has a feature
  the reference doesn't (the pin-1 marker circle) that can shift it;
  sharing one anchor drifted the generated panel's grid ~0.21mm off
  its own pad 1 on DIP-18/DIP-24 w. This is purely a viewer artifact —
  the actual generated pad positions already match the real library
  exactly (0.0mm delta, per `tests/test_pipeline_regression.py`).
  The page footer also shows a size comparison: `data/kicad-fpdb.yaml`'s
  own byte size vs. the combined size of the unique real `.kicad_mod`
  reference files behind every known case, plus the ratio between them
  (`_size_comparison_html`/`_size_stats_html`) — the project's core
  value proposition, made concrete on every run. Below that, a second
  footer line tallies hand-verified reference cases (`CASES`, 32
  today) against the total `.kicad_mod` file count across the whole
  real KiCad library (`_footprint_count_html`/
  `_count_library_footprints`, a recursive glob under
  `KICAD_FOOTPRINTS`) — how much of the real library this project can
  already replace, made visible alongside the size ratio.
* Pin-1 marker: a small filled silkscreen circle sitting directly
  above pad 1 (same X as the pad, offset past its own top edge by a
  fixed clearance), independent of the F.SilkS outline entirely — a
  deliberate departure from real KiCad's own top-center notch
  convention, not an attempt to match it (see
  `kicad_fpdb.pipeline._add_outline`,
  `docs/superpowers/specs/2026-09-14-pin1-circle-marker-design.md`).
  "Above" assumes pin 1 is at the top of the part, true for every
  generator today — pin 1 isn't always at a corner in real packages
  (sometimes mid-side), and this anchor-to-pad-1 approach already
  handles that correctly, but a family with pin 1 on a different edge
  would need the "above" direction generalized. Controlled by a
  `pin1_marker` param (default true, so SOIC/QFP need no declaration);
  `R` and `C` declare it false at their family root in
  `data/kicad-fpdb.yaml` since resistors are never polarized and
  capacitors only occasionally are — see
  `docs/superpowers/specs/2026-09-14-pin1-marker-opt-out-design.md`. A
  future polarized capacitor variant opts back in with
  `pin1_marker: true` in its own params. DIP also declares it false —
  DIP already has a square pin-1 pad and a silk notch, so a third
  circle marker was redundant.
* Generated footprints include Reference ("REF**", on `F.SilkS`) and Value
  (the footprint's own name, on `F.Fab`) text properties — matches real
  KiCad's layer convention. Placed 0.7mm above/below the outermost edge
  of the actual silk/courtyard outline (not the pad bounding box, and
  not the pin-1 marker circle, an ornament with no real-KiCad
  equivalent — see `kicad_fpdb.pipeline._outline_bounding_box`), then
  snapped to the nearest 0.05in (`TEXT_GRID_MM`). Real KiCad's own gap
  here varies a little per family (~0.7-0.8mm checked across DIP, SOIC,
  R, QFP) and isn't itself grid-aligned; this project uses one flat gap
  then grid-snaps for a clean look, rather than chasing per-family
  exactness. The Y snap only rounds *outward* (`_snap_outward`: floor
  for Reference's negative direction, ceil for Value's positive
  direction), never to the plain nearest multiple — nearest-rounding
  can land closer to the outline than the intended 0.7mm gap once a
  family's margin sits close enough to a grid line, confirmed visually
  overlapping the courtyard on R-1206 (only 0.145mm actual gap) and
  tighter than intended on R-0603/R-0805/C-0603/C-0805.
* Generated footprints also carry a separate `fp_text user "${REFERENCE}"`
  on `F.Fab` (`Text.kind == "fab_reference"`, written via a dedicated
  `_write_fab_reference_text` — a distinct s-expression, not a
  `property` block) — matches real KiCad exactly: an assembly-drawing
  overlay, centered on the footprint's true midpoint (not grid-snapped,
  unlike Reference/Value), that resolves to whatever reference
  designator gets assigned (e.g. "U1"). Font size defaults to the
  standard 1mm/0.15 but chip passives override it per package size via
  `fab_reference_font_size`/`fab_reference_thickness` in
  `data/kicad-fpdb.yaml` (hand-copied from real values, same
  no-shared-formula convention as `silk_y`/`silk_half_length`) — the
  default 1mm font badly overflowed their tiny courtyard, confirmed
  visually on R-0603 and R-1206 before adding the override. Also
  rotated 90 degrees for DIP and SOIC (`fab_reference_rotation: 90` at
  each family's root) so it reads along their tall/narrow body's long
  axis, matching real KiCad exactly; QFP and chip passives stay
  unrotated like real KiCad.
* SOT-23 family added (SOT-23, SOT-23-5, SOT-23-6, SOT-23-8 —
  `data/kicad-fpdb.yaml`'s `SOT` root): the first family with an
  asymmetric pin layout (2+1, 3+2, 3+3, 4+4), handled by a new
  `asymmetric_dual_row` generator (`kicad_fpdb/generators/
  asymmetric_dual_row.py`) taking explicit per-pin `left_offsets`/
  `right_offsets` rather than a `pin_count` formula — verified real
  SOT-23-5's right column uses only the outer two positions of a
  3-position lead-frame grid shared with SOT-23-6, not independently
  centered with its own pitch, so no formula holds generally. Real
  courtyard is the same union-of-margin-expanded-rects model already
  used for SOIC/QFP, generalized to accept a `(width, height)` tuple
  for `courtyard_body_size` (a non-square true body) and to union each
  *individual* pad's own bbox rather than a per-side group — needed so
  a gap between two same-side pads (SOT-23-5's right column) stays
  open instead of being bridged; QFP's own per-side-group code is
  untouched, unaffected by this. Real silk is a body rectangle with
  notches cut out wherever a pad crosses an edge — subtractive, the
  opposite topology from the courtyard's additive union, so not worth
  a general algorithm for one family — instead a new `silk_segments`
  param takes a verbatim per-variant line list, same "no shared
  formula, hand-copied" convention as chip-passive `silk_y`/
  `silk_half_length`. F.Fab reference text rotated 90° with a smaller
  font (0.72mm), matching real KiCad. `pin1_marker: false` for SOT-23
  and SOT-23-5 specifically — their asymmetric layouts (2+1, 3+2) are
  only placeable one way; SOT-23-6 (3+3) and SOT-23-8 (4+4) are
  symmetric (a 180° rotation still fits) and keep the marker. See
  `docs/superpowers/specs/2026-09-15-sot23-family-design.md`. `SOT`'s
  yaml root now carries every param shared across all 4 variants
  (`generator`, `pad_shape`/`pad_type`, `courtyard_margin_x`/`_y`,
  `fab_outline`, all 3 `fab_reference_*`), plus an intermediate
  `SOT-23-5-6-8` node (never itself a valid descriptor — just a
  chain-merge grouping point) for the `row_spacing`/
  `courtyard_body_size`/`fab_chamfer` those three additionally share.
  QFP's own root got the same treatment for QFP-32/48's shared params.
* `TSOT-23-5`/`-6`/`-8` added under a new `TSOT` root: byte-diffed each
  against its `SOT-23-*` sibling (e.g. `SOT-23-5.kicad_mod` vs.
  `TSOT-23-5.kicad_mod`) and confirmed the geometry is 100% identical —
  only name/`descr`/`tags`/3D-model path differ. Declared entirely via
  YAML anchors/aliases onto `SOT`'s own param mappings
  (`&sot_common_params`, `&sot_5_6_8_shared`, `&sot23_5_params`, etc.)
  rather than repeating any values, so `TSOT` has zero geometry data of
  its own. The base 3-pin `TSOT-23` (no `SOT-23` equivalent in this
  project) is a different, hand-authored footprint from a different
  vendor spec with its own geometry — deliberately not covered; see
  TODO for `SOT-23W`, the other still-open follow-up from the original
  SOT-23 work.
* First through-hole family: `R-AXIAL0204`/`0207`/`0309`/`0414` (axial
  DIN/JEDEC body sizes), grouped under a new `R-AXIAL` intermediate
  node (shared thru-hole/lead/courtyard params) so it doesn't affect
  the existing SMD `R-*` chip variants. `two_pad_chip` gained
  `pad_type`/`drill`/`centered` (axial pads sit at `(0,0)`/`(pitch,0)`,
  not symmetric about `x=0` like SMD chip passives) rather than
  needing a whole new generator. Silk/F.Fab bodies reuse the existing
  `body_width`/`body_margin` and `fab_body_size` mechanisms unchanged
  (a single-row 2-pad layout collapses `_pad_center_extent`'s Y range
  to a point, so `body_margin` becomes a flat half-height "for free");
  new `silk_leads`/`fab_leads` flags additionally draw two short lead
  lines from each pad to the body edge (silk starts at pad edge + a
  fixed 0.24mm clearance verified constant across all 4 body sizes;
  F.Fab starts exactly at the pad center). Courtyard is a genuinely
  new, simpler shape than SOIC/QFP/SOT's stepped union — `courtyard_
  includes_body` just combines the raw pad bbox and true F.Fab body
  bbox before one flat margin, since that happens to always produce a
  plain rectangle for axial resistors (pad bbox dominates in X, body
  dominates in Y). All match the real reference footprints exactly,
  not just the usual ~0.005mm tolerance. See
  `docs/superpowers/specs/2026-09-15-tht-axial-resistor-design.md`.
* Generated footprints also draw the true physical body on `F.Fab`
  (`kicad_fpdb.pipeline._add_outline`, near the pin-1 marker block),
  chamfered at pin 1's corner for polarized families — an
  assembly-drawing outline distinct from both the oversized F.SilkS
  body and the margin-expanded F.CrtYd courtyard. SOIC, QFP, and all 4
  SOT-23 variants reuse their already-declared
  `courtyard_body_width`/`courtyard_body_margin` or
  `courtyard_body_size` directly via `fab_outline: true` (verified
  those values are already the exact true body real KiCad's own F.Fab
  outline uses); DIP (no reusable courtyard true-body concept — its
  courtyard is a flat margin on the pad bbox) and each `R`/`C` variant
  (no reusable value either) declare their own new
  `fab_body_width`/`fab_body_margin` or `fab_body_size`. Chamfer size
  is its own per-family constant (DIP/QFP 1.0mm, SOIC 0.975mm, SOT-23
  0.325mm, SOT-23-5/6/8 0.4mm); `R`/`C` get no chamfer (no polarity,
  matching their existing `pin1_marker: false`) — a plain `Rect`
  instead of the chamfered `Poly`. See
  `docs/superpowers/specs/2026-09-15-fab-body-outline-design.md`.
* Generated footprints have courtyard (`F.CrtYd`) and silkscreen body
  outline (`F.SilkS`, with a pin-1 corner marker on families that use
  one) geometry (see `kicad_fpdb.pipeline._add_outline`). No family
  uses a generic pad-bbox margin/rectangle for either layer anymore.
  DIP's courtyard uses a real, asymmetric margin
  (`courtyard_margin_x`/`courtyard_margin_y` in `data/kicad-fpdb.yaml`:
  0.25mm perpendicular to the pin rows, 0.72mm along them), matching
  real KiCad almost exactly across every pin count and width checked —
  see `docs/superpowers/specs/2026-09-14-dip-courtyard-margin-design.md`.
  SOIC and QFP have a real *stepped* courtyard instead: the union of
  the true physical body outline (`courtyard_body_width`/
  `courtyard_body_margin` for SOIC, `courtyard_body_size` for QFP —
  deliberately different, smaller numbers than `body_width`/`body_size`,
  which stay oversized for F.SilkS) and one pad-bounding-box arm per
  side that has pads, both independently expanded by a flat 0.25mm
  margin (`courtyard_margin_x`/`_y`), verified exactly against SOIC-8,
  SOIC-14, LQFP-32, and LQFP-48 reference footprints (SOIC-14 carries
  the same ~0.02mm approximation already accepted for SOIC's silk
  body). The rectangle-union math lives in `kicad_fpdb/rect_union.py`
  (`union_outline`), generic over any number of margin-expanded
  rectangles — see
  `docs/superpowers/specs/2026-09-15-stepped-courtyard-design.md`. Chip
  passives (R/C) needed no shape change, just their real per-variant
  flat margin (0.15mm for R-0402, 0.25mm for R-0603/R-0805/C-0603)
  instead of the old generic 0.5mm fallback. None of these 12 reference
  footprints declare an explicit `solder_mask_margin`/
  `solder_paste_margin` override on any pad — both they and the
  generated pads just opt into the board's default mask/paste
  expansion via the pad's `layers` list, so there's no gap there today
  (see TODO for a possible future per-footprint override). For F.SilkS
  geometry: DIP and SOIC both derive body position from `body_width`/
  `body_margin` in `data/kicad-fpdb.yaml` (DIP's body_width keyed by
  width class narrow/regular/wide; SOIC's margin an averaged
  approximation, off by ~0.01-0.02mm — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`),
  but draw different shapes from it. DIP cuts a semicircular notch into
  the top edge of an otherwise closed rectangle (`notch_radius: 1.0` in
  `data/kicad-fpdb.yaml`, constant across every pin count and width
  checked), matching real KiCad's own DIP pin-1-side indicator exactly
  — see `docs/superpowers/specs/2026-09-14-dip-notch-arc-design.md`.
  SOIC instead declares `silk_two_lines: true` and draws only the
  top/bottom body edges, no vertical sides at all — matching real
  KiCad's own SOIC silk (which is not a closed rectangle either),
  and never declares `notch_radius`.
  QFP draws real corner-mark brackets instead of a rectangle
  (`body_size` in `data/kicad-fpdb.yaml`, derived per variant — see
  below), matching real KiCad's own QFP silk convention except for a
  fixed 0.3mm bracket leg length shared by all QFP variants (real
  values vary — see
  `docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md`).
  QFP is now formula-driven like DIP/SOIC rather than each variant
  hand-computing its own `pad_offset`: `quad_perimeter` derives
  `pad_offset = courtyard_body_size/2 + pad_lead_extension` (default
  `0.675`, overridden per variant for the 2 of 8 real LQFP samples
  that need a different value), and `_add_outline` derives the silk
  corner-mark `body_size = courtyard_body_size + 0.22` (exact across
  all 8 samples, 7mm-28mm bodies) — both explicit-value escape
  hatches, same convention as `silk_segments` elsewhere.
  `courtyard_body_size` is now the single body-size input for a QFP
  variant, feeding pad placement, the silk corner marks, the
  courtyard, and (via `fab_outline: true`) the F.Fab body outline all
  at once. 8 QFP variants total now (was 2), spanning 7mm-28mm real
  bodies — see `docs/superpowers/specs/2026-09-15-qfp-formula-driven-
  design.md`.
  R and C (chip passives) draw two short silk lines instead of a
  rectangle (`silk_y`/`silk_half_length` in `data/kicad-fpdb.yaml`,
  declared per variant with no shared formula — each is copied verbatim
  from its real reference footprint, matching real KiCad almost exactly
  — see `docs/superpowers/specs/2026-09-14-chip-passive-silk-lines-
  design.md`); this mode has no pin-1 marker regardless (R/C already
  declare `pin1_marker: false`, and this mode never computes the corner
  point the marker needs). Verified visually via the review tool rather
  than an automated geometry diff, per the spec's stated approach for
  outline geometry.
* `roundrect_rratio` (the roundrect corner ratio) is now computed by one
  shared `kicad_fpdb.geometry.clamped_roundrect_rratio` for every
  generator: nominally 0.25, clamped so the corner radius never exceeds
  an absolute 0.25mm — matches real KiCad, only visibly different from a
  flat 0.25 once a pad's min dimension exceeds ~1mm (surfaced by
  R-1206's 1.125mm pad). Previously a DIP-only special case; now the one
  formula everywhere.
* Chip passives small enough that real KiCad draws no F.SilkS outline at
  all (0201 and below) declare `no_silk: true` in `data/kicad-fpdb.yaml`
  (R-0201 is the first) — `_add_outline` skips the whole silk branch,
  courtyard is unaffected.
* `data/kicad-fpdb.yaml` coverage widened: DIP's wide (15.24mm) width
  class now has a verified regression case (DIP-24 w) alongside
  narrow/regular; SOIC-16 is a third verified pin count; R-0201, R-1206,
  C-0402, and C-0805 add four new chip-passive sizes. 18 reference cases
  total, up from 12.
* Pads support an optional per-descriptor solder mask/paste margin
  override (`Pad.solder_mask_margin`/`solder_paste_margin` in
  `kicad_fpdb/geometry.py`, emitted by the writer only when set). New
  `solder_mask_margin`/`solder_paste_margin` YAML params are popped in
  `generate_footprint` and applied uniformly to every pad in the
  generated geometry after the generator runs — no generator-specific
  plumbing needed, since it's a flat post-generation override rather
  than something any generator computes. No real reference footprint
  declares it yet (all 18 just opt into the board's default mask/paste
  expansion via the pad's `layers` list), so `data/kicad-fpdb.yaml` is
  untouched; covered by synthetic writer and pipeline tests instead of
  a reference-footprint regression case.
* Generated footprints get a descriptive dimension suffix appended to
  their identity/Value text, matching each family's own real KiCad
  naming convention exactly (verified against real reference
  footprints) — e.g. `DIP-16` → `DIP-16_W7.62mm`, `SOIC-8` →
  `SOIC-8_3.9x4.9mm_P1.27mm`, `LQFP-32` → `LQFP-32_7x7mm_P0.8mm`,
  `R-0603` → `R-0603_1608Metric`, `R-AXIAL0204` →
  `R-AXIAL0204_L3.6_D1.6_P7.62mm` — so a user assigning a
  generated footprint can sanity-check its real dimensions at a
  glance, the way real KiCad's own descriptive filenames already let
  them (real KiCad's `Value` text and footprint identity are the
  filename itself, no separate display name — matched here rather
  than inventing a new convention). New `kicad_fpdb/naming.py`
  (`descriptive_suffix`, `fab_outline_bounding_box`) dispatches per
  family: DIP uses its `row_spacing` param directly (real DIP names
  encode lead-to-lead spacing, not body size); SOIC/LQFP use the
  generated F.Fab true-body outline's own bounding box (generic across
  any generator that draws one, rather than a per-family formula) plus
  the `pitch` param; R/C chip passives use a small fixed
  imperial→metric code lookup table (`IMPERIAL_TO_METRIC` — real
  KiCad's numbers there are a standard pairing, not derivable from our
  params); R-AXIAL uses the F.Fab outline bbox (lead length/diameter)
  plus `pad_pitch` — only the trailing `P{pitch}` carries an explicit
  `mm` unit (`_L3.6_D1.6_P7.62mm`), since real KiCad's own axial names
  do the same (`R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_...`, redundantly
  units-suffixing all three, but this project's shorter form still
  reads unambiguously as mm throughout). SOT/TSOT get no suffix,
  matching real KiCad exactly
  — those families have no single `pitch`/`pad_pitch` param (asymmetric
  per-pin offsets instead). One subtlety: the descriptor grammar splits
  on the first hyphen only, so `R-AXIAL0204` parses to family `"R"`,
  variant `"AXIAL0204"` — `descriptive_suffix` checks
  `variant.startswith("AXIAL")` before the plain chip-lookup branch, or
  axial descriptors would (mis)match as an unknown metric code.
* Renamed the `QFP` family to `LQFP` (`data/kicad-fpdb.yaml`'s root and
  all 8 variant descriptors, `LQFP-32` etc.) to match real KiCad's own
  naming exactly — its library tracks distinct QFP lead-frame profiles
  by name (LQFP, PQFP, TQFP, ...), and this project only implements
  the low-profile one (`quad_perimeter`), so the family name now says
  so explicitly instead of implying it covers every QFP variant. Pure
  rename, no behavior change — earlier narrative entries above still
  say "QFP" since they describe the family as it was named at the
  time; only the naming-suffix examples just above were updated since
  they document current behavior. A future `PQFP`/`TQFP` family, if
  one turns out to need genuinely different geometry, would get its
  own root rather than folding into `LQFP`.
* Fixed a bug the LQFP rename surfaced: the review viewer's default
  case-name derivation (`render_all_known_cases`) stripped hyphens as
  well as spaces out of the descriptor (`DIP-14` → `DIP_14`), harmless
  before the descriptive-naming feature but now leaking into the
  generated footprint's own Value text (`DIP_14_W7.62mm` instead of
  the correct `DIP-14_W7.62mm`) — `render_comparison`'s own default
  didn't have this extra `.replace("-", "_")`, so the two copies had
  quietly drifted. Deduped into one `_default_case_name` helper used
  by both, plus the CLI entry point, so this can't drift again.
* The review viewer's preview now omits the 5 largest LQFP variants
  (80/100/144/176/208-pin) via `_preview_cases`/
  `PREVIEW_EXCLUDED_DESCRIPTORS` in `visual_compare.py` — each one's
  pad count roughly doubles `review.html`'s size for no extra review
  value (same stepped-courtyard validation regardless of size). `CASES`
  itself is untouched, so `test_pipeline_regression.py` still verifies
  all 35; only the HTML preview and its rendered SVG count (30) shrink.
  The footprint-count footer reads `CASES` directly, so it still
  correctly reports 35.
* Real KiCad's own library has 281 DIP footprints (`Package_DIP.pretty`)
  — grown from 5 to 230 total verified reference cases across all
  families since, closing a large share of that gap; see below.
* DIP grew two more width classes, `extra_wide`/`ultra_wide` (letters
  `x`/`u`, row spacing 22.86mm/25.4mm) — same mechanism as the existing
  narrow/regular/wide classes, no new code.
* Added `CERDIP` (ceramic side-brazed DIP, JEDEC MS-015) as a sibling
  family reusing `dual_row_grid` and almost all of DIP's own constants
  — only the F.Fab true-body width differs (7.49mm flat vs DIP's
  6.35mm). `CERDIP-8`/`CERDIP-14` additionally override `body_margin`/
  `fab_body_margin`/`courtyard_margin_y` for a JEDEC-mandated minimum
  ceramic body length at small pin counts. Real KiCad names always
  carry a trailing `_SideBrazed`, unconditional (not a selectable
  modifier) — see `kicad_fpdb.naming.descriptive_suffix`.
* Added a "socket" modifier (e.g. `DIP-14 socket`, also on CERDIP):
  real KiCad's `_Socket` variant draws one extra F.SilkS rectangle
  around the pads. Its silk *and* courtyard margins are measured from
  each pin's own **center**, not the pad bbox edge (`socket_margin_x/y`,
  `courtyard_from_pad_center` in `kicad_fpdb.pipeline._add_outline`) —
  this only looked edge-based before because every pad was the same
  1.6mm size; LongPads (below) exposed the real behavior.
* Added a "longpads" modifier (e.g. `DIP-14 longpads`): widens the pad
  to 2.4×1.6mm and shrinks the silk body by a flat 0.8mm (except DIP's
  "regular" width at pin counts 4–16, which real KiCad leaves
  unchanged). Required generalizing `dual_row_grid`'s non-pin-1 pad
  shape to "oval" whenever the pad is non-square (`_non_pin1_shape` in
  `kicad_fpdb/generators/dual_row.py`) — previously always "circle".
  Socket+LongPads together need their own distinct silk margin
  (1.44mm vs Socket-alone's 1.33mm, courtyard unchanged) — handled by
  a new reserved `_with` key inside a modifier's own override dict in
  `data/kicad-fpdb.yaml`, applied order-independently against the full
  set of active modifier tokens rather than sequentially (see
  `kicad_fpdb.family_tree.resolve_descriptor`).
* Fixed a naming redundancy: `DIP-16 r` produced a Value of
  `DIP-16_r_W10.16mm` — the width letter, now redundant since the
  dimension suffix already encodes it. Root cause was `_default_case_name`
  (which keeps every modifier token, for unique on-disk file naming)
  being reused as the footprint's own identity name; decoupled via a
  new `footprint_name` parameter on `render_comparison` backed by
  `_descriptor_head` (strips modifier tokens entirely). Fixed alongside:
  Socket's suffix ordering (`_socket_W7.62mm` → `_W7.62mm_Socket`) and
  CERDIP getting no suffix at all (`descriptive_suffix` only checked
  `family == "DIP"`). `MODIFIER_DISPLAY_NAMES` in `kicad_fpdb/naming.py`
  maps a modifier token to its exact-capitalization real-KiCad display
  name (`"longpads"` → `"LongPads"`, not `.capitalize()`'s `"Longpads"`).
* `remove_unused_layers no` was missing from every thru-hole pad the
  writer emits — real KiCad puts it on every one (never on SMD pads);
  fixed in `kicad_fpdb/writer.py`.
* Fixed the review viewer's footer size-comparison stat going stale
  once `PREVIEW_ONLY_DESCRIPTORS` (below) started filtering the
  rendered case list — `_size_comparison_html` was being passed that
  filtered list instead of the full `CASES`.
* Added `SMDIP` (surface-mount DIP): reuses essentially all of DIP's
  numeric constants but has its own `body_width`/`fab_body_width`
  tiers and `courtyard_margin_y`, `pad_type: smd`, `centered: true`.
* The review viewer's preview can now be pinned to just the newest
  batch of cases via `PREVIEW_ONLY_DESCRIPTORS` in
  `kicad_fpdb/visual_compare.py` (checked before the existing
  `PREVIEW_EXCLUDED_DESCRIPTORS` exclusion list) — `CASES` and the
  regression suite always cover everything regardless; this only
  narrows what `review.html` renders, so a reviewer isn't stuck
  paging through hundreds of already-verified cases every round.
  Left non-empty between sessions is intentional-for-now, not a
  leftover bug.
* Added SOIC's `wide` width class (the real `*W` 7.5mm-body variants,
  e.g. `SOIC-16W`), selected the same way as DIP's width classes
  (`SOIC-16 w`) — zero generator changes, same `dual_row_grid` +
  stepped-courtyard/naming code already used for narrow.
* Added SOIC-8's exposed-pad (`-1EP`) variants: a center thermal
  ("heatsink") pad plus a 4-way paste-stencil split, both new pad
  concepts. `Pad` gained optional `layers`/`pad_prop`/`zone_connect`
  overrides (`kicad_fpdb/geometry.py`, `kicad_fpdb/writer.py`) since
  these don't fit the plain pad_type-derived layer set every other pad
  uses. The paste-split size/position formula was reverse-engineered
  from all 8 real `SOIC-8-1EP_*.kicad_mod` files (no formula is
  published for it): per axis, `size = 0.8094 * (H/1) - 0.0057` where
  H is half the effective size, position = `effective_size / 4`, fit
  by least squares (max residual 0.006mm across all 8 samples). Two of
  the eight additionally declare a separate `ep_mask_size` (a smaller
  solder-mask opening over the same copper pad) — real KiCad computes
  the paste split from *that* size instead, and drops F.Mask from the
  copper pad itself in favor of a dedicated mask-only pad. Each of the
  8 real files needed its own hand-verified outer-pad `row_spacing`/
  `pad_size` too (5 of the 8 shrink/shift the ordinary 8 pads to clear
  the larger EP; only 3 sit on the plain narrow SOIC-8 grid unchanged)
  — modeled as one SOIC modifier per EP size (e.g. `SOIC-8
  ep2_41x3_3`) rather than a formula, since vendor EP sizing has none.
  Real KiCad's own `_ThermalVias` sibling of each of these (adds an
  actual via array inside the pad) is not yet implemented — see TODO.

## TODO

This is a running list of everything yet planned, updated at the end of
each session, in roughly chronological order:

* Generalize the pin-1 marker's "above pad 1" direction: every current
  generator places pin 1 at the top, so the marker just offsets in -Y.
  Real packages sometimes put pin 1 mid-side rather than at a corner
  (already handled, since the marker anchors to pad 1 directly — see
  memory `pin1-position-variation`), but a family with pin 1 on a
  different edge entirely (not top) would need the offset direction
  derived rather than assumed.
* Expand `data/kicad-fpdb.yaml` coverage: more DIP/SOIC pitches and
  widths, more chip passive sizes, additional package families (QFN,
  BGA, etc.) — each needs its own hand-verified real-footprint
  regression case per the existing pattern in
  `tests/test_pipeline_regression.py`. SOT-23/-5/-6/-8 and
  TSOT-23-5/-6/-8 are done.
* SOT-23W: a natural follow-up under the existing `SOT` root, but NOT a
  mechanical addition like TSOT-23-5/6/8 was — its real reference
  footprint uses a filled-triangle silk polygon for the pin-1 marker
  and a chamfered-pentagon F.Fab outline, neither of which the current
  outline generator supports (today's shapes are: notch, two-lines,
  corner-marks, or plain rect for silk; plain-rect or single-corner-
  chamfer for fab). Needs a small design pass for the new primitives
  before it fits the existing pattern.
* Descriptor grammar will need to grow to express more variation (see the
  spec's "Expected evolution" note) — grow it deliberately, not organically.
* SOIC-8-1EP's `_ThermalVias` siblings (8 real files): same EP/paste
  layout as the plain EP variants already done, plus an actual via
  array inside the thermal pad — a genuinely new primitive.
* SOIC-32 (`SOIC-32_7.518x20.777mm_P1.27mm.kicad_mod`): looks like it
  should fit the `wide` class but its pad width/pitch is subtly
  different from the other six real `*W` files (4.7875mm vs 4.65mm
  pad-x) — likely its own anomaly, needs its own investigation before
  it can be added (same category as DIP-32_W7.62mm's rect-vs-roundrect
  anomaly).
* SOIC-10 (`SOIC-10_3.9x4.9mm_P1mm.kicad_mod`): a genuinely different
  pitch (1mm, not 1.27mm) and its own row spacing — not a clean fit
  under the existing narrow/wide classes without a custom-pitch case.
* SOIC-14-16 and SOIC-5-6 (combined-pin-count files: one real footprint
  populating two different pin counts via unpopulated pads) aren't
  expressible in the current per-descriptor model — same unsupported
  modeling quirk as DIP-24's RTC-module files below.
* DIP: `SMDSocket` (51 files) — a third, distinct socket-adapter style
  needing new design work beyond the existing thru-hole Socket.
  Oddball partial-pin DIPs (`DIP-5-6`, `DIP-8-16`, `DIP-8-N6`,
  `DIP-8-N7`, 13 files) need generator support for a non-full pin
  population. `DIP-24_18.0mmx34.29mm_*` (4 files) is not a real DIP-24
  variant at all — a distinct RTC/battery-module footprint using
  `pcbnew`-generator-specific features (UUIDs, `unlocked` properties)
  this project's writer doesn't support — out of scope.
* SMDIP: a `Clearance8mm` modifier (10 files) and a `_W25.24mm` 5th
  width tier (4 files) are still unconverted; plus 12 vendor one-off
  footprints across the library that don't fit the family model at all.
* SOT-23W: a natural follow-up under the existing `SOT` root, but NOT a
  mechanical addition like TSOT-23-5/6/8 was — its real reference
  footprint uses a filled-triangle silk polygon for the pin-1 marker
  and a chamfered-pentagon F.Fab outline, neither of which the current
  outline generator supports (today's shapes are: notch, two-lines,
  corner-marks, or plain rect for silk; plain-rect or single-corner-
  chamfer for fab). Needs a small design pass for the new primitives
  before it fits the existing pattern.
* Convert the entire existing KiCad footprint library into descriptor form
  (separate future spec, per the original design spec's non-goals).
* KiCad plugin/UI integration (separate future spec).
* Contribution/moderation server (separate future spec).
