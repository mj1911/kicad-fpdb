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
  `kicad_fpdb/visual_compare.py`.
* Pin-1 marker: a small filled silkscreen triangle, tip at the body
  corner nearest pad 1, pointing at pad 1's actual position — matches
  real KiCad's own convention (see `kicad_fpdb.pipeline._add_outline`).
* Generated footprints include Reference ("REF**", on `F.SilkS`) and Value
  (the footprint's own name, on `F.Fab`) text properties, placed above/
  below the pad bounding box — matches real KiCad's layer convention.
* Generated footprints have courtyard (`F.CrtYd`) and silkscreen body
  outline (`F.SilkS`, with a pin-1 corner marker) geometry (see
  `kicad_fpdb.pipeline._add_outline`). Courtyard is still generic
  (pad bounding box + margin) for every family. The F.SilkS rectangle
  is generic for QFP and chip passives (R/C), but for DIP and SOIC it's
  now derived from real physical body dimensions (`body_width`/
  `body_margin` in `data/kicad-fpdb.yaml`) instead of the pad bounding
  box — DIP's body_width is keyed by width class (narrow/regular/wide),
  matching real KiCad almost exactly (SOIC's margin is an averaged
  approximation, off by ~0.01-0.02mm from real values — see
  `docs/superpowers/specs/2026-09-14-real-body-silk-outline-design.md`).
  Verified visually via the review tool rather than an automated
  geometry diff, per the spec's stated approach for outline geometry.

## TODO

This is a running list of everything yet planned, updated at the end of
each session, in roughly chronological order:

* Fix `roundrect_rratio` for larger SMD pads (e.g. 0805): generators
  currently use a flat 0.25 ratio, but real KiCad clamps to an absolute
  0.25mm max corner radius — only visibly wrong once a pad's min dimension
  exceeds ~1mm. Known, parked issue from the final review.
* Make QFP a formula family like DIP/SOIC (currently each QFP variant is a
  fully enumerated leaf in `data/kicad-fpdb.yaml` because `pad_offset`
  can't be derived from `pin_count` alone) — needs a declared body-size
  parameter to derive `pad_offset` from.
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
