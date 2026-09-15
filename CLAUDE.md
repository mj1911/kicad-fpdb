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
  exactly the panels the overflow fix touches.
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
  `pin1_marker` param (default true, so DIP/SOIC/QFP need no
  declaration); `R` and `C` declare it false at their family root in
  `data/kicad-fpdb.yaml` since resistors are never polarized and
  capacitors only occasionally are — see
  `docs/superpowers/specs/2026-09-14-pin1-marker-opt-out-design.md`. A
  future polarized capacitor variant opts back in with
  `pin1_marker: true` in its own params.
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
  exactness.
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
  geometry: DIP and
  SOIC draw a real body-derived rectangle (`body_width`/`body_margin`
  in `data/kicad-fpdb.yaml`) — DIP's body_width is keyed by width class
  (narrow/regular/wide), matching real KiCad almost exactly (SOIC's
  margin is an averaged approximation, off by ~0.01-0.02mm — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`).
  DIP additionally cuts a semicircular notch into the top edge
  (`notch_radius: 1.0` in `data/kicad-fpdb.yaml`, constant across every
  pin count and width checked), matching real KiCad's own DIP
  pin-1-side indicator exactly — see
  `docs/superpowers/specs/2026-09-14-dip-notch-arc-design.md`. SOIC
  shares the same rectangle branch but has no such notch in real
  KiCad, so it doesn't declare `notch_radius`.
  QFP draws real corner-mark brackets instead of a rectangle
  (`body_size` in `data/kicad-fpdb.yaml`, both current variants sharing
  7.22mm since both are 7x7mm packages), matching real KiCad's own QFP
  silk convention except for a fixed 0.3mm bracket leg length shared by
  all QFP variants (real values vary — see
  `docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md`).
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

## TODO

This is a running list of everything yet planned, updated at the end of
each session, in roughly chronological order:

* Make QFP a formula family like DIP/SOIC (currently each QFP variant is a
  fully enumerated leaf in `data/kicad-fpdb.yaml` because `pad_offset`
  can't be derived from `pin_count` alone) — needs a declared body-size
  parameter to derive `pad_offset` from.
* Per-pad solder mask/paste margin modifier: none of the 12 reference
  footprints checked so far declare an explicit `solder_mask_margin`/
  `solder_paste_margin` override (all just opt into the board's default
  expansion via the pad's `layers` list, and the generated pads match
  that exactly), but a user may want to override this per footprint when
  selecting one. Would need a new `Pad` field threaded through the
  writer once a real reference case actually needs it.
* Generalize the pin-1 marker's "above pad 1" direction: every current
  generator places pin 1 at the top, so the marker just offsets in -Y.
  Real packages sometimes put pin 1 mid-side rather than at a corner
  (already handled, since the marker anchors to pad 1 directly — see
  memory `pin1-position-variation`), but a family with pin 1 on a
  different edge entirely (not top) would need the offset direction
  derived rather than assumed.
* Expand `data/kicad-fpdb.yaml` coverage: more DIP/SOIC pitches and
  widths, more chip passive sizes, additional package families (QFN, BGA,
  SOT, etc.) — each needs its own hand-verified real-footprint regression
  case per the existing pattern in `tests/test_pipeline_regression.py`.
* Descriptor grammar will need to grow to express more variation (see the
  spec's "Expected evolution" note) — grow it deliberately, not organically.
* Convert the entire existing KiCad footprint library into descriptor form
  (separate future spec, per the original design spec's non-goals).
* KiCad plugin/UI integration (separate future spec).
* Contribution/moderation server (separate future spec).
